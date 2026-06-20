use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use chrono::{Duration, Utc};
use sha2::{Digest, Sha256};
use sqlx::PgPool;
use std::sync::Arc;

use crate::error::{ApiError, ApiResult};
use super::{JwtManager, PasswordManager, Session, User, Workspace, WorkspaceMember};

fn generate_refresh_token() -> (String, String) {
    use rand::Rng;
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
            // Revoke all other sessions when the password changes.
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
    
    pub async fn sign_in(
        &self,
        email: &str,
        password: &str,
        workspace_id: Option<i64>,
        ip: Option<&str>,
        user_agent: Option<&str>,
    ) -> ApiResult<(String, String, User, String, i64)> {
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
        
        User::update_last_login(&self.pool, user.id)
            .await
            .map_err(|e| ApiError::Database(e))?;
        
        let wid = if let Some(requested_wid) = workspace_id {
            requested_wid
        } else {
            user.active_workspace_id.unwrap_or(0)
        };
        
        let ws_role = if wid > 0 {
            User::get_workspace_role(&self.pool, user.id, wid)
                .await
                .map_err(|e| ApiError::Database(e))?
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
        
        Session::create(&self.pool, user.id, &refresh_hash, expires_at, ip, user_agent)
            .await
            .map_err(|e| {
                tracing::error!("Failed to create session: {:?}", e);
                ApiError::Database(e)
            })?;
        
        // Return the workspace-scoped role and active workspace id so the route
        // can build a Python-matching signin response (#646).
        Ok((access_token, refresh_raw, user, ws_role, wid))
    }
    
    pub async fn sign_up(
        &self,
        email: &str,
        password: &str,
        display_name: Option<&str>,
        workspace_name: &str,
        ip: Option<&str>,
        user_agent: Option<&str>,
    ) -> ApiResult<(String, String, User, Workspace)> {
        let existing = User::find_by_email(&self.pool, email)
            .await
            .map_err(|e| ApiError::Database(e))?;
        
        if existing.is_some() {
            return Err(ApiError::Validation("Email already exists".to_string()));
        }
        
        let password_hash = PasswordManager::hash_password(password)?;
        
        let mut tx = self.pool.begin().await.map_err(|e| ApiError::Database(e))?;
        
        let user_count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM users")
            .fetch_one(&mut *tx)
            .await
            .map_err(|e| ApiError::Database(e))?;
        
        let global_role = if user_count == 0 {
            "superadmin"
        } else {
            "user"
        };
        
        let user = User::create(
            &mut *tx,
            email,
            &password_hash,
            display_name,
            global_role,
        )
        .await
        .map_err(|e| {
            tracing::error!("Failed to create user: {:?}", e);
            ApiError::Database(e)
        })?;
        
        let ws_slug = workspace_name
            .trim()
            .to_lowercase()
            .replace(" ", "-")
            .chars()
            .take(60)
            .collect::<String>();
        
        let workspace = Workspace::create(
            &mut *tx,
            workspace_name,
            &ws_slug,
            "starter",
            user.id,
        )
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
            .map_err(|e| ApiError::Database(e))?;
        
        tx.commit().await.map_err(|e| ApiError::Database(e))?;
        
        let access_token = self.jwt_manager.create_access_token(
            user.id.to_string(),
            workspace.id,
            user.email.clone(),
            "owner".to_string(),
            global_role.to_string(),
        )?;
        
        let (refresh_raw, refresh_hash) = generate_refresh_token();
        let expires_at = Utc::now() + Duration::days(30);
        
        Session::create(&self.pool, user.id, &refresh_hash, expires_at, ip, user_agent)
            .await
            .map_err(|e| {
                tracing::error!("Failed to create session: {:?}", e);
                ApiError::Database(e)
            })?;
        
        Ok((access_token, refresh_raw, user, workspace))
    }
    
    pub async fn refresh_token(&self, refresh_token: &str) -> ApiResult<(String, String)> {
        let mut hasher = Sha256::new();
        hasher.update(refresh_token.as_bytes());
        let token_hash = format!("{:x}", hasher.finalize());
        
        let session = Session::find_by_token_hash(&self.pool, &token_hash)
            .await
            .map_err(|e| ApiError::Database(e))?
            .ok_or(ApiError::Unauthorized)?;
        
        if !session.is_valid() {
            return Err(ApiError::Unauthorized);
        }
        
        let user = User::find_by_id(&self.pool, session.user_id)
            .await
            .map_err(|e| ApiError::Database(e))?
            .ok_or(ApiError::Unauthorized)?;
        
        if user.disabled {
            return Err(ApiError::Unauthorized);
        }
        
        let wid = user.active_workspace_id.unwrap_or(0);
        let ws_role = if wid > 0 {
            User::get_workspace_role(&self.pool, user.id, wid)
                .await
                .map_err(|e| ApiError::Database(e))?
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
        
        Session::rotate(&self.pool, session.id, user.id, &new_refresh_hash, expires_at)
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
            .map_err(|e| ApiError::Database(e))?;
        
        Ok(())
    }
    
    pub fn verify_token(&self, token: &str) -> ApiResult<super::jwt::Claims> {
        self.jwt_manager.verify_token(token)
    }
}
