//! Test fixtures — pre-seeded data helpers for gateway integration tests.
//!
//! Per HARNESS-ENGINEERING-PLAN.md Appendix.
//!
//! Provides commonly-needed test seeds (owner user, viewer user, tokens) so
//! test bodies stay focused on what they're asserting rather than setup.
//!
//! Usage:
//! ```rust
//! #[tokio::test]
//! async fn test_me_returns_owner_role() {
//!     let h = GatewayHarness::new().await;
//!     let fix = AuthFixture::owner(&h).await;
//!     let me = h.me(&fix.access_token).await;
//!     assert_eq!(me["data"]["role"], "owner");
//!     h.cleanup().await;
//! }
//! ```

#![allow(dead_code)]

use serde_json::Value;

use super::GatewayHarness;

// ── Single-user fixtures ─────────────────────────────────────────────────────

/// Pre-seeded authenticated user with a valid access token.
pub struct AuthFixture {
    pub email: String,
    pub password: String,
    pub access_token: String,
    pub user_id: i64,
    pub workspace_id: i64,
}

impl AuthFixture {
    /// Seed an owner user (register + sign in). Cleanup via `harness.cleanup()`.
    pub async fn owner(harness: &GatewayHarness) -> Self {
        let email = GatewayHarness::unique_email("fixture-owner");
        let password = "Fixture-Pass-123!";
        Self::seed(
            harness,
            &email,
            password,
            "Fixture Owner",
            "Fixture Workspace",
        )
        .await
    }

    /// Seed a second independent user (acts as viewer — no workspace membership yet).
    pub async fn second_user(harness: &GatewayHarness) -> Self {
        let email = GatewayHarness::unique_email("fixture-second");
        let password = "Second-Pass-123!";
        Self::seed(harness, &email, password, "Second User", "Second Workspace").await
    }

    /// Register + sign in and capture all fixture fields.
    async fn seed(
        harness: &GatewayHarness,
        email: &str,
        password: &str,
        display_name: &str,
        workspace_name: &str,
    ) -> Self {
        let reg: Value = harness
            .register(email, password, display_name, workspace_name)
            .await;

        let workspace_id = reg["workspace_id"].as_i64().unwrap_or(0);
        let user_id = reg["user_id"].as_i64().unwrap_or(0);

        let signin = harness.signin(email, password).await;
        let access_token = signin["access_token"]
            .as_str()
            .expect("AuthFixture: signin missing access_token")
            .to_string();

        Self {
            email: email.to_string(),
            password: password.to_string(),
            access_token,
            user_id,
            workspace_id,
        }
    }

    /// Re-sign in with the stored credentials and return a fresh access token.
    pub async fn refresh_token(&self, harness: &GatewayHarness) -> String {
        let signin = harness.signin(&self.email, &self.password).await;
        signin["access_token"]
            .as_str()
            .expect("refresh_token: missing access_token")
            .to_string()
    }
}

// ── Two-user workspace fixture ───────────────────────────────────────────────

/// Two users (owner + a second independent user) ready for RBAC / workspace tests.
pub struct WorkspaceFixture {
    pub owner: AuthFixture,
    pub second: AuthFixture,
}

impl WorkspaceFixture {
    /// Seed owner and a second user. Both are fully authenticated.
    ///
    /// Note: The second user registers their own workspace (single-owner model).
    /// For workspace-member tests, add the invite-accept flow on top of this.
    pub async fn two_users(harness: &GatewayHarness) -> Self {
        let owner = AuthFixture::owner(harness).await;
        let second = AuthFixture::second_user(harness).await;
        Self { owner, second }
    }
}

// ── Token-only fixture ───────────────────────────────────────────────────────

/// Fastest fixture: just a token string. Use when you only need a valid Bearer.
pub async fn bearer_token(harness: &GatewayHarness) -> String {
    harness
        .signup_and_get_token(
            &GatewayHarness::unique_email("token-only"),
            "TokenOnly-Pass-123!",
        )
        .await
}

// ── Expired / tampered token helpers ────────────────────────────────────────

/// Returns a syntactically valid but semantically invalid JWT.
/// Use to assert 401 on protected endpoints.
pub fn invalid_token() -> &'static str {
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\
     .eyJzdWIiOiItMSIsImVtYWlsIjoiZmFrZUBleC5jb20iLCJleHAiOjE3MDAwMDAwMDB9\
     .invalid-signature"
}

/// Returns an expired token stub (not a real JWT — just triggers 401).
pub fn expired_token() -> &'static str {
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\
     .eyJzdWIiOiIxIiwiZXhwIjoxfQ\
     .expired"
}
