use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use chrono::{Duration, Utc};
use rand::Rng;
use sha2::{Digest, Sha256};
use sqlx::PgPool;
use std::sync::Arc;
use totp_rs::{Algorithm, Secret, TOTP};

use super::{JwtManager, PasswordManager, Session, User, Workspace, WorkspaceMember};
use crate::error::{ApiError, ApiResult};

/// Result of a `sign_in()` call. When the user has MFA enabled the caller must
/// exchange the `mfa_pending_token` via `POST /auth/mfa/challenge` instead of
/// receiving full session tokens directly (#666).
pub enum SignInResult {
    Success {
        access_token: String,
        refresh_token: String,
        user: User,
        ws_role: String,
        wid: i64,
    },
    MfaRequired {
        mfa_pending_token: String,
    },
}

fn generate_refresh_token() -> (String, String) {
    let mut rng = rand::thread_rng();
    let random_bytes: Vec<u8> = (0..48).map(|_| rng.gen()).collect();
    let raw = URL_SAFE_NO_PAD.encode(&random_bytes);
    let mut hasher = Sha256::new();
    hasher.update(raw.as_bytes());
    let hashed = format!("{:x}", hasher.finalize());
    (raw, hashed)
}

#[derive(Clone)]
pub struct AuthServiceImpl {
    pool: PgPool,
    jwt_manager: Arc<JwtManager>,
}

impl AuthServiceImpl {
    pub fn new(pool: PgPool, jwt_manager: Arc<JwtManager>) -> Self {
        Self { pool, jwt_manager }
    }

    /// Return which auth backends are active, read from the `feature_flags`
    /// table. Mirrors Python `/auth/mode`: defaults to v2 enabled / legacy
    /// disabled, and degrades gracefully (same defaults) on any DB error.
    pub async fn auth_mode(&self) -> (bool, bool) {
        let rows: Vec<(String, bool)> = sqlx::query_as(
            "SELECT key, enabled FROM feature_flags \
             WHERE key IN ('auth.v2.enabled', 'auth.legacy.enabled')",
        )
        .fetch_all(&self.pool)
        .await
        .unwrap_or_default();

        let mut v2_enabled = true;
        let mut legacy_enabled = false;
        for (key, enabled) in rows {
            match key.as_str() {
                "auth.v2.enabled" => v2_enabled = enabled,
                "auth.legacy.enabled" => legacy_enabled = enabled,
                _ => {}
            }
        }
        (v2_enabled, legacy_enabled)
    }

    /// Update the current user's profile (display_name and/or password).
    /// Mirrors Python `PUT /auth/profile`: a password change requires the
    /// correct current password and revokes the user's other sessions. The
    /// whole update is transactional.
    pub async fn update_profile(
        &self,
        user_id: i64,
        display_name: Option<&str>,
        current_password: Option<&str>,
        new_password: Option<&str>,
    ) -> ApiResult<()> {
        let user = User::find_by_id(&self.pool, user_id)
            .await
            .map_err(ApiError::Database)?
            .ok_or_else(|| ApiError::NotFound("User not found".to_string()))?;

        if display_name.is_none() && new_password.is_none() {
            return Err(ApiError::Validation(
                "Nothing to update — provide display_name or new_password".to_string(),
            ));
        }

        let mut tx = self.pool.begin().await.map_err(ApiError::Database)?;

        if let Some(name) = display_name {
            sqlx::query("UPDATE users SET display_name = $1, updated_at = NOW() WHERE id = $2")
                .bind(name)
                .bind(user_id)
                .execute(&mut *tx)
                .await
                .map_err(ApiError::Database)?;
        }

        if let Some(new_pw) = new_password {
            let current = current_password.ok_or_else(|| {
                ApiError::Validation(
                    "current_password is required to change your password".to_string(),
                )
            })?;
            let hash = user.password_hash.as_deref().unwrap_or("");
            if !PasswordManager::verify_password(current, hash)? {
                return Err(ApiError::Unauthorized);
            }
            let new_hash = PasswordManager::hash_password(new_pw)?;
            sqlx::query("UPDATE users SET password_hash = $1, updated_at = NOW() WHERE id = $2")
                .bind(&new_hash)
                .bind(user_id)
                .execute(&mut *tx)
                .await
                .map_err(ApiError::Database)?;
            sqlx::query(
                "UPDATE sessions SET revoked_at = NOW() WHERE user_id = $1 AND revoked_at IS NULL",
            )
            .bind(user_id)
            .execute(&mut *tx)
            .await
            .map_err(ApiError::Database)?;
        }

        tx.commit().await.map_err(ApiError::Database)?;
        Ok(())
    }

    /// Initiate a password reset. Generates a random token, stores its SHA-256
    /// hash in `password_resets` (1-hour expiry), and best-effort sends a reset
    /// email via the Resend API. Mirrors Python `POST /auth/forgot` — never
    /// leaks whether the email exists.
    pub async fn forgot_password(&self, email: &str) -> ApiResult<()> {
        let user = User::find_by_email(&self.pool, email)
            .await
            .map_err(ApiError::Database)?;

        let Some(user) = user else { return Ok(()) };

        let token_bytes: Vec<u8> = (0..32).map(|_| rand::random::<u8>()).collect();
        let raw_token = URL_SAFE_NO_PAD.encode(&token_bytes);

        let mut hasher = Sha256::new();
        hasher.update(raw_token.as_bytes());
        let token_hash = format!("{:x}", hasher.finalize());

        let expires_at = Utc::now() + Duration::hours(1);

        sqlx::query(
            "INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES ($1, $2, $3)",
        )
        .bind(user.id)
        .bind(&token_hash)
        .bind(expires_at)
        .execute(&self.pool)
        .await
        .map_err(ApiError::Database)?;

        let frontend_url =
            std::env::var("FRONTEND_URL").unwrap_or_else(|_| "http://localhost:3000".to_string());
        let reset_link = format!("{frontend_url}/reset-password?token={raw_token}");

        let api_key = std::env::var("RESEND_API_KEY").ok();
        if let Some(api_key) = api_key {
            let subject_prefix = std::env::var("MAIL_SUBJECT_PREFIX")
                .unwrap_or_default()
                .trim()
                .to_string();
            let subject = if subject_prefix.is_empty() {
                "Reset your Autoniix password".to_string()
            } else {
                format!("{subject_prefix} Reset your Autoniix password")
            };

            let text_body = format!("To reset your password, open this link (expires in 1 hour):\n\n{reset_link}\n");
            let html_body = format!(r#"<p>To reset your password, click the link below (expires in 1 hour):</p><p><a href="{reset_link}">{reset_link}</a></p>"#);

            let email_addr = email.to_string();
            tokio::spawn(async move {
                let client = reqwest::Client::new();
                let _ = client
                    .post("https://api.resend.com/emails")
                    .bearer_auth(&api_key)
                    .json(&serde_json::json!({
                        "from": "noreply@autoniix.com",
                        "to": email_addr,
                        "subject": subject,
                        "text": text_body,
                        "html": html_body,
                    }))
                    .send()
                    .await;
            });
        }

        Ok(())
    }

    /// Reset a password using a token from `forgot`. Validates the token hash,
    /// checks expiry/used, updates the password, marks the token used, and
    /// revokes all sessions. Transactional. Mirrors Python `POST /auth/reset`.
    pub async fn reset_password(&self, token: &str, new_password: &str) -> ApiResult<()> {
        let mut hasher = Sha256::new();
        hasher.update(token.as_bytes());
        let token_hash = format!("{:x}", hasher.finalize());

        type ResetRow = (
            i64,
            i64,
            chrono::DateTime<Utc>,
            Option<chrono::DateTime<Utc>>,
        );
        let row: Option<ResetRow> = sqlx::query_as(
            "SELECT id, user_id, expires_at, used_at FROM password_resets WHERE token_hash = $1",
        )
        .bind(&token_hash)
        .fetch_optional(&self.pool)
        .await
        .map_err(ApiError::Database)?;

        let Some((reset_id, user_id, expires_at, used_at)) = row else {
            return Err(ApiError::Validation("Invalid or expired token".to_string()));
        };

        if used_at.is_some() || expires_at < Utc::now() {
            return Err(ApiError::Validation("Invalid or expired token".to_string()));
        }

        let new_hash = PasswordManager::hash_password(new_password)?;

        let mut tx = self.pool.begin().await.map_err(ApiError::Database)?;

        sqlx::query("UPDATE users SET password_hash = $1, updated_at = NOW() WHERE id = $2")
            .bind(&new_hash)
            .bind(user_id)
            .execute(&mut *tx)
            .await
            .map_err(ApiError::Database)?;

        sqlx::query("UPDATE password_resets SET used_at = NOW() WHERE id = $1")
            .bind(reset_id)
            .execute(&mut *tx)
            .await
            .map_err(ApiError::Database)?;

        sqlx::query(
            "UPDATE sessions SET revoked_at = NOW() WHERE user_id = $1 AND revoked_at IS NULL",
        )
        .bind(user_id)
        .execute(&mut *tx)
        .await
        .map_err(ApiError::Database)?;

        tx.commit().await.map_err(ApiError::Database)?;
        Ok(())
    }

    /// Set up MFA for the current user: generate a TOTP secret, store it, and
    /// return the otpauth URI + secret. Mirrors Python `POST /auth/mfa/setup`.
    pub async fn mfa_setup(&self, user_id: i64, email: &str) -> ApiResult<(String, String)> {
        let secret = Secret::generate_secret();
        let secret_bytes = secret
            .to_bytes()
            .map_err(|_| ApiError::Internal("Failed to decode secret".to_string()))?;
        let secret_b32 = secret.to_encoded().to_string();

        let totp = TOTP::new(
            Algorithm::SHA1,
            6,
            1,
            30,
            secret_bytes,
            Some("yt-automation".to_string()),
            email.to_string(),
        )
        .map_err(|_| ApiError::Internal("Failed to generate TOTP".to_string()))?;

        let uri = totp.get_url();

        sqlx::query("UPDATE users SET mfa_secret = $1 WHERE id = $2")
            .bind(&secret_b32)
            .bind(user_id)
            .execute(&self.pool)
            .await
            .map_err(ApiError::Database)?;

        Ok((uri, secret_b32))
    }

    /// Verify a TOTP code and enable MFA if valid. Mirrors Python
    /// `POST /auth/mfa/verify`.
    pub async fn mfa_verify(&self, user_id: i64, code: &str) -> ApiResult<()> {
        let secret_b32: Option<String> =
            sqlx::query_scalar("SELECT mfa_secret FROM users WHERE id = $1")
                .bind(user_id)
                .fetch_one(&self.pool)
                .await
                .map_err(ApiError::Database)?;

        let secret_b32 =
            secret_b32.ok_or_else(|| ApiError::Validation("MFA not initialized".to_string()))?;

        let secret_bytes = Secret::Encoded(secret_b32)
            .to_bytes()
            .map_err(|_| ApiError::Validation("MFA not initialized".to_string()))?;

        let totp = TOTP::new(Algorithm::SHA1, 6, 1, 30, secret_bytes, None, String::new())
            .map_err(|_| ApiError::Internal("Failed to parse TOTP secret".to_string()))?;

        let now = Utc::now();
        let timestamp = now.timestamp() as u64;
        let valid =
            (-1i64..=1).any(|offset| totp.generate(timestamp + (offset as u64 * 30)) == code);
        if !valid {
            return Err(ApiError::Unauthorized);
        }

        sqlx::query("UPDATE users SET mfa_enabled = TRUE WHERE id = $1")
            .bind(user_id)
            .execute(&self.pool)
            .await
            .map_err(ApiError::Database)?;

        Ok(())
    }

    /// Disable MFA for the current user. Requires a valid TOTP code to confirm.
    /// Clears `mfa_enabled` and `mfa_secret`. Mirrors the inverse of `mfa_verify`.
    pub async fn mfa_disable(&self, user_id: i64, code: &str) -> ApiResult<()> {
        let secret_b32: Option<String> =
            sqlx::query_scalar("SELECT mfa_secret FROM users WHERE id = $1 AND mfa_enabled = TRUE")
                .bind(user_id)
                .fetch_optional(&self.pool)
                .await
                .map_err(ApiError::Database)?;

        let secret_b32 = secret_b32.ok_or_else(|| {
            ApiError::Validation("MFA is not enabled on this account".to_string())
        })?;

        let secret_bytes = Secret::Encoded(secret_b32)
            .to_bytes()
            .map_err(|_| ApiError::Unauthorized)?;

        let totp = TOTP::new(Algorithm::SHA1, 6, 1, 30, secret_bytes, None, String::new())
            .map_err(|_| ApiError::Internal("Failed to parse TOTP secret".to_string()))?;

        let timestamp = Utc::now().timestamp() as u64;
        let valid = (-1i64..=1)
            .any(|offset| totp.generate(timestamp.wrapping_add((offset * 30) as u64)) == code);
        if !valid {
            return Err(ApiError::Unauthorized);
        }

        sqlx::query("UPDATE users SET mfa_enabled = FALSE, mfa_secret = NULL WHERE id = $1")
            .bind(user_id)
            .execute(&self.pool)
            .await
            .map_err(ApiError::Database)?;

        Ok(())
    }

    pub async fn sign_in(
        &self,
        email: &str,
        password: &str,
        workspace_id: Option<i64>,
        ip: Option<&str>,
        user_agent: Option<&str>,
    ) -> ApiResult<SignInResult> {
        let user = User::find_by_email(&self.pool, email)
            .await
            .map_err(|e| {
                tracing::error!("Database error during sign in: {:?}", e);
                ApiError::Database(e)
            })?
            .ok_or(ApiError::Unauthorized)?;

        if user.disabled {
            return Err(ApiError::Unauthorized);
        }

        let password_hash = user.password_hash.as_ref().ok_or(ApiError::Unauthorized)?;
        let password_valid = PasswordManager::verify_password(password, password_hash)?;

        if !password_valid {
            return Err(ApiError::Unauthorized);
        }

        let wid = workspace_id.unwrap_or_else(|| user.active_workspace_id.unwrap_or(0));

        if user.mfa_enabled.unwrap_or(false) {
            let mfa_pending_token = self.jwt_manager.create_mfa_pending_token(
                user.id.to_string(),
                wid,
                user.email.clone(),
                user.role.clone(),
            )?;
            return Ok(SignInResult::MfaRequired { mfa_pending_token });
        }

        User::update_last_login(&self.pool, user.id)
            .await
            .map_err(ApiError::Database)?;

        let ws_role = if wid > 0 {
            User::get_workspace_role(&self.pool, user.id, wid)
                .await
                .map_err(ApiError::Database)?
                .unwrap_or_else(|| "viewer".to_string())
        } else {
            "viewer".to_string()
        };

        let access_token = self.jwt_manager.create_access_token(
            user.id.to_string(),
            wid,
            user.email.clone(),
            ws_role.clone(),
            user.role.clone(),
        )?;

        let (refresh_raw, refresh_hash) = generate_refresh_token();
        let expires_at = Utc::now() + Duration::days(30);

        Session::create(
            &self.pool,
            user.id,
            &refresh_hash,
            expires_at,
            ip,
            user_agent,
        )
        .await
        .map_err(|e| {
            tracing::error!("Failed to create session: {:?}", e);
            ApiError::Database(e)
        })?;

        Ok(SignInResult::Success {
            access_token,
            refresh_token: refresh_raw,
            user,
            ws_role,
            wid,
        })
    }

    /// Complete sign-in after a successful MFA TOTP challenge (#666).
    /// Validates the pending token, verifies the TOTP code, then creates a
    /// session and issues full access + refresh tokens.
    pub async fn complete_mfa_signin(
        &self,
        mfa_pending_token: &str,
        code: &str,
        ip: Option<&str>,
        user_agent: Option<&str>,
    ) -> ApiResult<(String, String, User, String, i64)> {
        let pending = self
            .jwt_manager
            .verify_mfa_pending_token(mfa_pending_token)?;

        let user_id: i64 = pending.sub.parse().map_err(|_| ApiError::Unauthorized)?;

        let user = User::find_by_id(&self.pool, user_id)
            .await
            .map_err(ApiError::Database)?
            .ok_or(ApiError::Unauthorized)?;

        if user.disabled {
            return Err(ApiError::Unauthorized);
        }

        let secret_b32: Option<String> =
            sqlx::query_scalar("SELECT mfa_secret FROM users WHERE id = $1")
                .bind(user_id)
                .fetch_one(&self.pool)
                .await
                .map_err(ApiError::Database)?;

        let secret_b32 =
            secret_b32.ok_or_else(|| ApiError::Validation("MFA not configured".to_string()))?;

        let secret_bytes = Secret::Encoded(secret_b32)
            .to_bytes()
            .map_err(|_| ApiError::Unauthorized)?;

        let totp = TOTP::new(Algorithm::SHA1, 6, 1, 30, secret_bytes, None, String::new())
            .map_err(|_| ApiError::Internal("Failed to parse TOTP secret".to_string()))?;

        let timestamp = Utc::now().timestamp() as u64;
        let valid = (-1i64..=1)
            .any(|offset| totp.generate(timestamp.wrapping_add((offset * 30) as u64)) == code);
        if !valid {
            return Err(ApiError::Unauthorized);
        }

        User::update_last_login(&self.pool, user.id)
            .await
            .map_err(ApiError::Database)?;

        let wid = pending.wid;
        let ws_role = if wid > 0 {
            User::get_workspace_role(&self.pool, user.id, wid)
                .await
                .map_err(ApiError::Database)?
                .unwrap_or_else(|| "viewer".to_string())
        } else {
            "viewer".to_string()
        };

        let access_token = self.jwt_manager.create_access_token(
            user.id.to_string(),
            wid,
            user.email.clone(),
            ws_role.clone(),
            user.role.clone(),
        )?;

        let (refresh_raw, refresh_hash) = generate_refresh_token();
        let expires_at = Utc::now() + Duration::days(30);

        Session::create(
            &self.pool,
            user.id,
            &refresh_hash,
            expires_at,
            ip,
            user_agent,
        )
        .await
        .map_err(|e| {
            tracing::error!("Failed to create MFA session: {:?}", e);
            ApiError::Database(e)
        })?;

        Ok((access_token, refresh_raw, user, ws_role, wid))
    }

    /// Register a new user and create their first workspace. Mirrors Python
    /// `POST /auth/register` (#350): public self-serve signup, no auto-login
    /// (no tokens issued), returns onboarding metadata only. The first user
    /// bootstraps as platform superadmin; subsequent users get `role='user'`.
    /// Workspace-level ownership is via `workspace_members.role='owner'`.
    pub async fn register(
        &self,
        email: &str,
        password: &str,
        display_name: Option<&str>,
        workspace_name: &str,
    ) -> ApiResult<(i64, i64, String)> {
        let existing = User::find_by_email(&self.pool, email)
            .await
            .map_err(ApiError::Database)?;

        if existing.is_some() {
            return Err(ApiError::Conflict(
                "An account with this email already exists".to_string(),
            ));
        }

        let password_hash = PasswordManager::hash_password(password)?;

        let mut tx = self.pool.begin().await.map_err(ApiError::Database)?;

        let user_count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM users")
            .fetch_one(&mut *tx)
            .await
            .map_err(ApiError::Database)?;

        if user_count > 0 {
            let invite_only: bool = sqlx::query_scalar(
                "SELECT enabled FROM feature_flags WHERE key = 'auth.register.invite_only'",
            )
            .fetch_optional(&mut *tx)
            .await
            .unwrap_or(None)
            .unwrap_or(false);

            if invite_only {
                return Err(ApiError::ForbiddenWith(
                    "Registration is closed".to_string(),
                ));
            }
        }

        let global_role = if user_count == 0 {
            "superadmin"
        } else {
            "user"
        };

        let user = User::create(&mut *tx, email, &password_hash, display_name, global_role)
            .await
            .map_err(|e| {
                tracing::error!("Failed to create user: {:?}", e);
                ApiError::Database(e)
            })?;

        let base_slug = workspace_name
            .trim()
            .to_lowercase()
            .replace(" ", "-")
            .chars()
            .take(60)
            .collect::<String>();

        let mut ws_slug = base_slug.clone();
        let mut suffix = 0;
        loop {
            let exists: Option<i64> =
                sqlx::query_scalar("SELECT id FROM workspaces WHERE slug = $1")
                    .bind(&ws_slug)
                    .fetch_optional(&mut *tx)
                    .await
                    .map_err(ApiError::Database)?;

            if exists.is_none() {
                break;
            }
            suffix += 1;
            ws_slug = format!("{base_slug}-{suffix}");
        }

        let workspace = Workspace::create(&mut *tx, workspace_name, &ws_slug, "starter", user.id)
            .await
            .map_err(|e| {
                tracing::error!("Failed to create workspace: {:?}", e);
                ApiError::Database(e)
            })?;

        WorkspaceMember::create(&mut *tx, workspace.id, user.id, "owner")
            .await
            .map_err(|e| {
                tracing::error!("Failed to create workspace member: {:?}", e);
                ApiError::Database(e)
            })?;

        User::update_active_workspace(&mut *tx, user.id, workspace.id)
            .await
            .map_err(ApiError::Database)?;

        tx.commit().await.map_err(ApiError::Database)?;

        Ok((user.id, workspace.id, "owner".to_string()))
    }

    /// Accept a workspace invitation. For new users: creates an account with the
    /// provided password. For existing users: adds them to the workspace. In both
    /// cases auto-issues session tokens (mirrors Python `POST /auth/accept-invite`).
    pub async fn accept_invite(
        &self,
        token: &str,
        password: Option<&str>,
        display_name: Option<&str>,
        ip: Option<&str>,
        user_agent: Option<&str>,
    ) -> ApiResult<(String, String, User, String, i64)> {
        let mut hasher = Sha256::new();
        hasher.update(token.as_bytes());
        let token_hash = format!("{:x}", hasher.finalize());

        type InviteRow = (
            i64,
            i64,
            String,
            String,
            chrono::DateTime<Utc>,
            Option<chrono::DateTime<Utc>>,
        );
        let row: Option<InviteRow> = sqlx::query_as(
            "SELECT id, workspace_id, email, role, expires_at, accepted_at \
             FROM workspace_invitations WHERE token_hash = $1",
        )
        .bind(&token_hash)
        .fetch_optional(&self.pool)
        .await
        .map_err(ApiError::Database)?;

        let Some((invite_id, workspace_id, invite_email, invite_role, expires_at, accepted_at)) =
            row
        else {
            return Err(ApiError::Validation(
                "Invalid or expired invitation".to_string(),
            ));
        };

        if accepted_at.is_some() || expires_at < Utc::now() {
            return Err(ApiError::Validation(
                "Invitation has already been used or has expired".to_string(),
            ));
        }

        let workspace_exists =
            sqlx::query_scalar::<_, bool>("SELECT EXISTS(SELECT 1 FROM workspaces WHERE id = $1)")
                .bind(workspace_id)
                .fetch_one(&self.pool)
                .await
                .map_err(ApiError::Database)?;

        if !workspace_exists {
            return Err(ApiError::Gone(
                "This invitation is no longer valid — the workspace has been removed.".to_string(),
            ));
        }

        let existing_user = User::find_by_email(&self.pool, &invite_email)
            .await
            .map_err(ApiError::Database)?;

        if let Some(ref u) = existing_user {
            if u.disabled {
                return Err(ApiError::Unauthorized);
            }
        }

        let mut tx = self.pool.begin().await.map_err(ApiError::Database)?;

        let user = match existing_user {
            Some(u) => u,
            None => {
                let pw = password.ok_or_else(|| {
                    ApiError::Validation(
                        "password is required for new accounts accepting an invite".to_string(),
                    )
                })?;
                if pw.len() < 8 {
                    return Err(ApiError::Validation(
                        "Password must be at least 8 characters".to_string(),
                    ));
                }
                let pw_hash = PasswordManager::hash_password(pw)?;
                User::create(&mut *tx, &invite_email, &pw_hash, display_name, "user")
                    .await
                    .map_err(ApiError::Database)?
            }
        };

        sqlx::query(
            "INSERT INTO workspace_members (workspace_id, user_id, role) \
             VALUES ($1, $2, $3) \
             ON CONFLICT (workspace_id, user_id) DO UPDATE SET role = EXCLUDED.role",
        )
        .bind(workspace_id)
        .bind(user.id)
        .bind(&invite_role)
        .execute(&mut *tx)
        .await
        .map_err(ApiError::Database)?;

        sqlx::query(
            "UPDATE users SET active_workspace_id = $1 \
             WHERE id = $2 AND active_workspace_id IS NULL",
        )
        .bind(workspace_id)
        .bind(user.id)
        .execute(&mut *tx)
        .await
        .map_err(ApiError::Database)?;

        sqlx::query("UPDATE workspace_invitations SET accepted_at = NOW() WHERE id = $1")
            .bind(invite_id)
            .execute(&mut *tx)
            .await
            .map_err(ApiError::Database)?;

        tx.commit().await.map_err(ApiError::Database)?;

        User::update_last_login(&self.pool, user.id)
            .await
            .map_err(ApiError::Database)?;

        let ws_role = User::get_workspace_role(&self.pool, user.id, workspace_id)
            .await
            .map_err(ApiError::Database)?
            .unwrap_or_else(|| invite_role.clone());

        let access_token = self.jwt_manager.create_access_token(
            user.id.to_string(),
            workspace_id,
            user.email.clone(),
            ws_role.clone(),
            user.role.clone(),
        )?;

        let (refresh_raw, refresh_hash) = generate_refresh_token();
        let session_expires = Utc::now() + Duration::days(30);

        Session::create(
            &self.pool,
            user.id,
            &refresh_hash,
            session_expires,
            ip,
            user_agent,
        )
        .await
        .map_err(|e| {
            tracing::error!("Failed to create session for invite accept: {:?}", e);
            ApiError::Database(e)
        })?;

        Ok((access_token, refresh_raw, user, ws_role, workspace_id))
    }

    pub async fn refresh_token(&self, refresh_token: &str) -> ApiResult<(String, String)> {
        let mut hasher = Sha256::new();
        hasher.update(refresh_token.as_bytes());
        let token_hash = format!("{:x}", hasher.finalize());

        let session = Session::find_by_token_hash(&self.pool, &token_hash)
            .await
            .map_err(ApiError::Database)?
            .ok_or(ApiError::Unauthorized)?;

        if !session.is_valid() {
            return Err(ApiError::Unauthorized);
        }

        let user = User::find_by_id(&self.pool, session.user_id)
            .await
            .map_err(ApiError::Database)?
            .ok_or(ApiError::Unauthorized)?;

        if user.disabled {
            return Err(ApiError::Unauthorized);
        }

        let wid = user.active_workspace_id.unwrap_or(0);
        let ws_role = if wid > 0 {
            User::get_workspace_role(&self.pool, user.id, wid)
                .await
                .map_err(ApiError::Database)?
                .unwrap_or_else(|| "viewer".to_string())
        } else {
            "viewer".to_string()
        };

        let access_token = self.jwt_manager.create_access_token(
            user.id.to_string(),
            wid,
            user.email.clone(),
            ws_role,
            user.role.clone(),
        )?;

        let (new_refresh_raw, new_refresh_hash) = generate_refresh_token();
        let expires_at = Utc::now() + Duration::days(30);

        Session::rotate(
            &self.pool,
            session.id,
            user.id,
            &new_refresh_hash,
            expires_at,
        )
        .await
        .map_err(|e| {
            tracing::error!("Failed to rotate session: {:?}", e);
            ApiError::Database(e)
        })?;

        Ok((access_token, new_refresh_raw))
    }

    pub async fn logout(&self, refresh_token: &str) -> ApiResult<()> {
        let mut hasher = Sha256::new();
        hasher.update(refresh_token.as_bytes());
        let token_hash = format!("{:x}", hasher.finalize());

        Session::revoke(&self.pool, &token_hash)
            .await
            .map_err(ApiError::Database)?;

        Ok(())
    }

    pub fn verify_token(&self, token: &str) -> ApiResult<super::jwt::Claims> {
        self.jwt_manager.verify_token(token)
    }

    /// `GET /api/v2/auth/workspaces` — all workspaces the user is a member of.
    pub async fn list_workspaces(&self, user_id: i64) -> ApiResult<Vec<serde_json::Value>> {
        let rows = sqlx::query!(
            r#"SELECT w.id, w.name, w.slug, w.plan, wm.role,
                      (w.id = u.active_workspace_id) AS active,
                      COALESCE(
                          (es.value->>'completed')::boolean,
                          FALSE
                      ) AS onboarding_completed
                 FROM workspace_members wm
                 JOIN workspaces w  ON w.id = wm.workspace_id
                 JOIN users u       ON u.id = wm.user_id
                 LEFT JOIN entity_settings es
                        ON es.scope    = 'workspace'
                       AND es.scope_id = w.id::text
                       AND es.key      = 'onboarding'
                WHERE wm.user_id = $1
                ORDER BY w.name"#,
            user_id
        )
        .fetch_all(&self.pool)
        .await
        .map_err(ApiError::Database)?;

        Ok(rows
            .into_iter()
            .map(|r| {
                serde_json::json!({
                    "id": r.id, "name": r.name, "slug": r.slug, "plan": r.plan,
                    "role": r.role, "active": r.active, "onboarding_completed": r.onboarding_completed,
                })
            })
            .collect())
    }

    /// `POST /api/v2/auth/switch-workspace` — re-issue JWT for a different workspace.
    pub async fn switch_workspace(
        &self,
        user_id: i64,
        workspace_id: i64,
    ) -> ApiResult<(String, String, i64, String)> {
        let member = sqlx::query!(
            "SELECT role FROM workspace_members WHERE workspace_id=$1 AND user_id=$2",
            workspace_id,
            user_id
        )
        .fetch_optional(&self.pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::ForbiddenWith("Not a member of that workspace".into()))?;

        let user = sqlx::query!(
            "SELECT id, email, role, disabled FROM users WHERE id=$1",
            user_id
        )
        .fetch_optional(&self.pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or(ApiError::Unauthorized)?;

        if user.disabled {
            return Err(ApiError::ForbiddenWith("User disabled".into()));
        }

        sqlx::query!(
            "UPDATE users SET active_workspace_id=$1 WHERE id=$2",
            workspace_id,
            user_id
        )
        .execute(&self.pool)
        .await
        .map_err(ApiError::Database)?;

        let (refresh_raw, refresh_hash) = generate_refresh_token();
        let expires_at = Utc::now() + Duration::days(30);
        sqlx::query!(
            "INSERT INTO sessions (user_id, refresh_token_hash, expires_at) VALUES ($1,$2,$3)",
            user_id,
            refresh_hash,
            expires_at
        )
        .execute(&self.pool)
        .await
        .map_err(ApiError::Database)?;

        let access_token = self.jwt_manager.create_access_token(
            user.id.to_string(),
            workspace_id,
            user.email,
            member.role.clone(),
            user.role,
        )?;

        Ok((access_token, refresh_raw, workspace_id, member.role))
    }

    /// `POST /api/v2/auth/create-workspace` — create additional workspace, re-issue JWT.
    pub async fn create_workspace(
        &self,
        user_id: i64,
        workspace_name: String,
    ) -> ApiResult<(String, String, i64, String)> {
        let user = sqlx::query!(
            "SELECT id, email, role FROM users WHERE id=$1",
            user_id
        )
        .fetch_optional(&self.pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or(ApiError::Unauthorized)?;

        let owned_count: i64 = sqlx::query_scalar!(
            "SELECT COUNT(*) FROM workspaces WHERE owner_user_id=$1",
            user_id
        )
        .fetch_one(&self.pool)
        .await
        .map_err(ApiError::Database)?
        .unwrap_or(0);

        // starter plan: 1 workspace
        if owned_count >= 1 && user.role != "superadmin" {
            return Err(ApiError::ForbiddenWith(
                "Workspace limit reached for your plan. Upgrade to create more.".into(),
            ));
        }

        let ws_name = workspace_name.trim().to_string();
        let base_slug = ws_name.to_lowercase().replace(' ', "-");
        let base_slug = &base_slug[..base_slug.len().min(60)];

        let mut slug = base_slug.to_string();
        let mut suffix = 0u32;
        loop {
            let exists: bool = sqlx::query_scalar!(
                "SELECT EXISTS(SELECT 1 FROM workspaces WHERE slug=$1)",
                slug
            )
            .fetch_one(&self.pool)
            .await
            .map_err(ApiError::Database)?
            .unwrap_or(false);
            if !exists {
                break;
            }
            suffix += 1;
            slug = format!("{base_slug}-{suffix}");
        }

        let mut tx = self.pool.begin().await.map_err(ApiError::Database)?;
        let wid: i64 = sqlx::query_scalar!(
            r#"INSERT INTO workspaces (name, slug, plan, owner_user_id, billing_email)
               VALUES ($1,$2,'starter',$3,$4) RETURNING id"#,
            ws_name,
            slug,
            user_id,
            user.email
        )
        .fetch_one(&mut *tx)
        .await
        .map_err(ApiError::Database)?;

        sqlx::query!(
            "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES ($1,$2,'owner')",
            wid,
            user_id
        )
        .execute(&mut *tx)
        .await
        .map_err(ApiError::Database)?;

        sqlx::query!(
            "UPDATE users SET active_workspace_id=$1 WHERE id=$2",
            wid,
            user_id
        )
        .execute(&mut *tx)
        .await
        .map_err(ApiError::Database)?;

        tx.commit().await.map_err(ApiError::Database)?;

        let (refresh_raw, refresh_hash) = generate_refresh_token();
        let expires_at = Utc::now() + Duration::days(30);
        sqlx::query!(
            "INSERT INTO sessions (user_id, refresh_token_hash, expires_at) VALUES ($1,$2,$3)",
            user_id,
            refresh_hash,
            expires_at
        )
        .execute(&self.pool)
        .await
        .map_err(ApiError::Database)?;

        let access_token = self.jwt_manager.create_access_token(
            user.id.to_string(),
            wid,
            user.email,
            "owner".to_string(),
            user.role,
        )?;

        Ok((access_token, refresh_raw, wid, "owner".to_string()))
    }

    /// `DELETE /api/v2/auth/account` — soft-delete the current user account.
    pub async fn delete_account(&self, user_id: i64, password: String) -> ApiResult<()> {
        let user = sqlx::query!(
            "SELECT id, password_hash, role FROM users WHERE id=$1",
            user_id
        )
        .fetch_optional(&self.pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::NotFound("user".into()))?;

        let pw_hash = user.password_hash.unwrap_or_default();
        let ok = PasswordManager::verify_password(&password, &pw_hash)
            .unwrap_or(false);
        if !ok {
            return Err(ApiError::Unauthorized);
        }
        if user.role == "superadmin" {
            let count: i64 = sqlx::query_scalar!(
                "SELECT COUNT(*) FROM users WHERE role='superadmin' AND disabled=FALSE"
            )
            .fetch_one(&self.pool)
            .await
            .map_err(ApiError::Database)?
            .unwrap_or(0);
            if count <= 1 {
                return Err(ApiError::ForbiddenWith(
                    "Cannot delete the last superadmin account".into(),
                ));
            }
        }

        let mut tx = self.pool.begin().await.map_err(ApiError::Database)?;
        sqlx::query!(
            "UPDATE sessions SET revoked_at=NOW() WHERE user_id=$1 AND revoked_at IS NULL",
            user_id
        )
        .execute(&mut *tx)
        .await
        .map_err(ApiError::Database)?;
        sqlx::query!(
            "DELETE FROM workspace_members WHERE user_id=$1",
            user_id
        )
        .execute(&mut *tx)
        .await
        .map_err(ApiError::Database)?;
        sqlx::query!(
            r#"UPDATE users SET email=$1, password_hash=NULL, display_name='Deleted User',
                      disabled=TRUE, mfa_enabled=FALSE, mfa_secret=NULL
               WHERE id=$2"#,
            format!("deleted-{user_id}@deleted.local"),
            user_id
        )
        .execute(&mut *tx)
        .await
        .map_err(ApiError::Database)?;
        tx.commit().await.map_err(ApiError::Database)?;
        Ok(())
    }

    /// `GET /api/v2/auth/invite-info?token=…` — public, no auth required.
    pub async fn invite_info(&self, token: String) -> ApiResult<serde_json::Value> {
        let mut hasher = Sha256::new();
        hasher.update(token.as_bytes());
        let token_hash = format!("{:x}", hasher.finalize());

        let invite = sqlx::query!(
            r#"SELECT email, role, workspace_id, accepted_at, expires_at, cancelled_at
                 FROM workspace_invitations WHERE token_hash=$1"#,
            token_hash
        )
        .fetch_optional(&self.pool)
        .await
        .map_err(ApiError::Database)?
        .ok_or_else(|| ApiError::Validation("Invalid invitation token".into()))?;

        if invite.accepted_at.is_some() {
            return Err(ApiError::Validation("Invitation already used".into()));
        }
        if invite.cancelled_at.is_some() {
            return Err(ApiError::Validation("Invitation has been cancelled".into()));
        }
        if invite.expires_at < Utc::now() {
            return Err(ApiError::Validation("Invitation has expired".into()));
        }

        let user_exists: bool = sqlx::query_scalar!(
            "SELECT EXISTS(SELECT 1 FROM users WHERE lower(email)=lower($1))",
            invite.email
        )
        .fetch_one(&self.pool)
        .await
        .map_err(ApiError::Database)?
        .unwrap_or(false);

        let ws_name: Option<String> = sqlx::query_scalar!(
            "SELECT name FROM workspaces WHERE id=$1",
            invite.workspace_id
        )
        .fetch_optional(&self.pool)
        .await
        .map_err(ApiError::Database)?;

        Ok(serde_json::json!({
            "email": invite.email,
            "role": invite.role,
            "workspace_name": ws_name.unwrap_or_else(|| "Unknown workspace".to_string()),
            "user_exists": user_exists,
        }))
    }
}
