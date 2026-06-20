use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;

#[derive(Debug, Clone, FromRow, Serialize, Deserialize)]
pub struct User {
    pub id: i64,
    pub email: String,
    pub password_hash: Option<String>,
    pub display_name: Option<String>,
    pub role: String,
    pub active_workspace_id: Option<i64>,
    pub disabled: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mfa_enabled: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub email_verified: Option<bool>,
}

#[derive(Debug, Clone, FromRow, Serialize, Deserialize)]
pub struct Workspace {
    pub id: i64,
    pub name: String,
    pub slug: String,
    pub plan: String,
    pub owner_user_id: i64,
}

#[derive(Debug, Clone, FromRow, Serialize, Deserialize)]
pub struct WorkspaceMember {
    pub workspace_id: i64,
    pub user_id: i64,
    pub role: String,
    pub joined_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, FromRow, Serialize, Deserialize)]
pub struct Session {
    pub id: i64,
    pub user_id: i64,
    pub refresh_token_hash: String,
    pub expires_at: DateTime<Utc>,
    pub revoked_at: Option<DateTime<Utc>>,
    pub rotated_at: Option<DateTime<Utc>>,
}

impl User {
    pub async fn find_by_email(pool: &sqlx::PgPool, email: &str) -> sqlx::Result<Option<Self>> {
        sqlx::query_as::<_, Self>(
            "SELECT id, email, password_hash, display_name, role, active_workspace_id, 
                    disabled, mfa_enabled, email_verified
             FROM users WHERE lower(email) = lower($1)"
        )
        .bind(email)
        .fetch_optional(pool)
        .await
    }
    
    pub async fn find_by_id(pool: &sqlx::PgPool, id: i64) -> sqlx::Result<Option<Self>> {
        sqlx::query_as::<_, Self>(
            "SELECT id, email, password_hash, display_name, role, active_workspace_id, 
                    disabled, mfa_enabled, email_verified
             FROM users WHERE id = $1"
        )
        .bind(id)
        .fetch_optional(pool)
        .await
    }
    
    pub async fn create<'e, E>(
        executor: E,
        email: &str,
        password_hash: &str,
        display_name: Option<&str>,
        role: &str,
    ) -> sqlx::Result<Self>
    where
        E: sqlx::PgExecutor<'e>,
    {
        sqlx::query_as::<_, Self>(
            "INSERT INTO users (email, password_hash, display_name, role, disabled, email_verified)
             VALUES (lower($1), $2, $3, $4, false, true)
             RETURNING id, email, password_hash, display_name, role, active_workspace_id, 
                       disabled, mfa_enabled, email_verified"
        )
        .bind(email)
        .bind(password_hash)
        .bind(display_name)
        .bind(role)
        .fetch_one(executor)
        .await
    }

    pub async fn update_active_workspace<'e, E>(
        executor: E,
        user_id: i64,
        workspace_id: i64,
    ) -> sqlx::Result<()>
    where
        E: sqlx::PgExecutor<'e>,
    {
        sqlx::query("UPDATE users SET active_workspace_id = $1 WHERE id = $2")
            .bind(workspace_id)
            .bind(user_id)
            .execute(executor)
            .await?;
        Ok(())
    }

    pub async fn update_last_login(pool: &sqlx::PgPool, user_id: i64) -> sqlx::Result<()> {
        sqlx::query("UPDATE users SET last_login_at = NOW() WHERE id = $1")
            .bind(user_id)
            .execute(pool)
            .await?;
        Ok(())
    }
    
    pub async fn get_workspace_role(
        pool: &sqlx::PgPool,
        user_id: i64,
        workspace_id: i64,
    ) -> sqlx::Result<Option<String>> {
        let row: Option<(String,)> = sqlx::query_as(
            "SELECT role FROM workspace_members WHERE workspace_id = $1 AND user_id = $2"
        )
        .bind(workspace_id)
        .bind(user_id)
        .fetch_optional(pool)
        .await?;
        
        Ok(row.map(|(role,)| role))
    }
}

impl Workspace {
    pub async fn find_by_id(pool: &sqlx::PgPool, id: i64) -> sqlx::Result<Option<Self>> {
        sqlx::query_as::<_, Self>(
            "SELECT id, name, slug, plan, owner_user_id FROM workspaces WHERE id = $1"
        )
        .bind(id)
        .fetch_optional(pool)
        .await
    }
    
    pub async fn create<'e, E>(
        executor: E,
        name: &str,
        slug: &str,
        plan: &str,
        owner_user_id: i64,
    ) -> sqlx::Result<Self>
    where
        E: sqlx::PgExecutor<'e>,
    {
        sqlx::query_as::<_, Self>(
            "INSERT INTO workspaces (name, slug, plan, mode, owner_user_id)
             VALUES ($1, $2, $3, 'solo', $4)
             RETURNING id, name, slug, plan, owner_user_id"
        )
        .bind(name)
        .bind(slug)
        .bind(plan)
        .bind(owner_user_id)
        .fetch_one(executor)
        .await
    }
}

impl WorkspaceMember {
    pub async fn create<'e, E>(
        executor: E,
        workspace_id: i64,
        user_id: i64,
        role: &str,
    ) -> sqlx::Result<()>
    where
        E: sqlx::PgExecutor<'e>,
    {
        sqlx::query(
            "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES ($1, $2, $3)"
        )
        .bind(workspace_id)
        .bind(user_id)
        .bind(role)
        .execute(executor)
        .await?;
        Ok(())
    }
}

impl Session {
    pub async fn create(
        pool: &sqlx::PgPool,
        user_id: i64,
        refresh_token_hash: &str,
        expires_at: DateTime<Utc>,
        ip: Option<&str>,
        user_agent: Option<&str>,
    ) -> sqlx::Result<Self> {
        sqlx::query_as::<_, Self>(
            "INSERT INTO sessions (user_id, refresh_token_hash, expires_at, ip, user_agent)
             VALUES ($1, $2, $3, $4, $5)
             RETURNING id, user_id, refresh_token_hash, expires_at, revoked_at, rotated_at"
        )
        .bind(user_id)
        .bind(refresh_token_hash)
        .bind(expires_at)
        .bind(ip)
        .bind(user_agent)
        .fetch_one(pool)
        .await
    }

    pub async fn find_by_token_hash(
        pool: &sqlx::PgPool,
        token_hash: &str,
    ) -> sqlx::Result<Option<Self>> {
        sqlx::query_as::<_, Self>(
            "SELECT id, user_id, refresh_token_hash, expires_at, revoked_at, rotated_at
             FROM sessions WHERE refresh_token_hash = $1"
        )
        .bind(token_hash)
        .fetch_optional(pool)
        .await
    }

    pub async fn rotate(
        pool: &sqlx::PgPool,
        old_session_id: i64,
        user_id: i64,
        new_token_hash: &str,
        expires_at: DateTime<Utc>,
    ) -> sqlx::Result<Self> {
        let mut tx = pool.begin().await?;
        
        sqlx::query("UPDATE sessions SET rotated_at = NOW() WHERE id = $1")
            .bind(old_session_id)
            .execute(&mut *tx)
            .await?;
        
        let new_session = sqlx::query_as::<_, Self>(
            "INSERT INTO sessions (user_id, refresh_token_hash, expires_at)
             VALUES ($1, $2, $3)
             RETURNING id, user_id, refresh_token_hash, expires_at, revoked_at, rotated_at"
        )
        .bind(user_id)
        .bind(new_token_hash)
        .bind(expires_at)
        .fetch_one(&mut *tx)
        .await?;
        
        tx.commit().await?;
        Ok(new_session)
    }

    pub async fn revoke(pool: &sqlx::PgPool, token_hash: &str) -> sqlx::Result<()> {
        sqlx::query("UPDATE sessions SET revoked_at = NOW() WHERE refresh_token_hash = $1")
            .bind(token_hash)
            .execute(pool)
            .await?;
        Ok(())
    }

    pub fn is_valid(&self) -> bool {
        self.revoked_at.is_none() 
            && self.rotated_at.is_none() 
            && self.expires_at > Utc::now()
    }
}
