//! GatewayHarness — ergonomic test helper for Rust gateway integration tests.
//!
//! Per HARNESS-ENGINEERING-PLAN.md Week 2 Day 1-2.
//!
//! Usage:
//! ```rust
//! #[tokio::test]
//! async fn test_register() {
//!     let h = GatewayHarness::new().await;
//!     let resp = h.register("test@ex.com", "password123", "Test User", "My Workspace").await;
//!     assert_eq!(resp["status"], "ok");
//!     h.cleanup().await;
//! }
//! ```

use axum::Router;
use serde_json::{json, Value};
use sqlx::{postgres::PgPoolOptions, PgPool};
use std::net::SocketAddr;
use tokio::net::TcpListener;

const TEST_JWT_SECRET: &str = "test-jwt-secret-key-must-be-long-enough";

/// Manages a live gateway instance with an isolated test database connection.
pub struct GatewayHarness {
    pub pool: PgPool,
    pub base_url: String,
    pub client: reqwest::Client,
    _server_handle: tokio::task::JoinHandle<()>,
}

impl GatewayHarness {
    /// Spin up a gateway bound to a random port against the test database.
    pub async fn new() -> Self {
        let database_url = std::env::var("TEST_DATABASE_URL")
            .unwrap_or_else(|_| "postgresql://localhost/autoniix_test".to_string());

        let pool = PgPoolOptions::new()
            .max_connections(5)
            .connect(&database_url)
            .await
            .expect("GatewayHarness: failed to connect to test database. Set TEST_DATABASE_URL.");

        let app: Router = gateway::create_app(pool.clone(), TEST_JWT_SECRET.to_string()).await;

        let listener = TcpListener::bind("127.0.0.1:0")
            .await
            .expect("GatewayHarness: failed to bind random port");
        let addr: SocketAddr = listener.local_addr().unwrap();
        let base_url = format!("http://{addr}");

        let server_handle = tokio::spawn(async move {
            axum::serve(listener, app).await.ok();
        });

        Self {
            pool,
            base_url,
            client: reqwest::Client::new(),
            _server_handle: server_handle,
        }
    }

    // ── Auth helpers ────────────────────────────────────────────────────────

    /// Register a new user via /register (#350). Returns onboarding metadata
    /// (status, user_id, workspace_id, role, onboarding_required) — NO tokens.
    pub async fn register(
        &self,
        email: &str,
        password: &str,
        display_name: &str,
        workspace_name: &str,
    ) -> Value {
        let resp = self
            .client
            .post(format!("{}/api/v2/auth/register", self.base_url))
            .json(&json!({
                "email": email,
                "password": password,
                "display_name": display_name,
                "workspace_name": workspace_name,
            }))
            .send()
            .await
            .expect("register request failed");

        assert!(
            resp.status().is_success(),
            "register returned {}: {}",
            resp.status(),
            resp.text().await.unwrap_or_default()
        );

        resp.json().await.expect("register response is not JSON")
    }

    /// Backward-compatible alias: register then sign in, returning the signin
    /// response (which includes access_token). Tests that need tokens should
    /// use `register_and_signin` or `register_and_get_token`.
    pub async fn signup(
        &self,
        email: &str,
        password: &str,
        display_name: &str,
        workspace_name: &str,
    ) -> Value {
        self.register(email, password, display_name, workspace_name)
            .await;
        self.signin(email, password).await
    }

    /// Sign in and return the full JSON response body (includes access_token).
    pub async fn signin(&self, email: &str, password: &str) -> Value {
        let resp = self
            .client
            .post(format!("{}/api/v2/auth/signin", self.base_url))
            .json(&json!({ "email": email, "password": password }))
            .send()
            .await
            .expect("signin request failed");

        assert!(
            resp.status().is_success(),
            "signin returned {}: {}",
            resp.status(),
            resp.text().await.unwrap_or_default()
        );

        resp.json().await.expect("signin response is not JSON")
    }

    /// Shortcut: register, sign in, and return the access token string.
    pub async fn signup_and_get_token(&self, email: &str, password: &str) -> String {
        self.register(email, password, "Test User", "Test Workspace")
            .await;
        let body = self.signin(email, password).await;
        body["access_token"]
            .as_str()
            .expect("signin response missing access_token")
            .to_string()
    }

    /// Shortcut: sign in and return the access token string.
    pub async fn signin_and_get_token(&self, email: &str, password: &str) -> String {
        let body = self.signin(email, password).await;
        body["access_token"]
            .as_str()
            .expect("signin response missing access_token")
            .to_string()
    }

    /// Refresh an access token. Returns the full JSON response.
    pub async fn refresh(&self, refresh_token: &str) -> Value {
        let resp = self
            .client
            .post(format!("{}/api/v2/auth/refresh", self.base_url))
            .json(&json!({ "refresh_token": refresh_token }))
            .send()
            .await
            .expect("refresh request failed");

        resp.json().await.expect("refresh response is not JSON")
    }

    /// Logout (revoke session). Requires authentication (Bearer access token);
    /// the refresh token to revoke is sent in the body (or read from a cookie).
    pub async fn logout(&self, access_token: &str, refresh_token: &str) {
        self.client
            .post(format!("{}/api/v2/auth/logout", self.base_url))
            .bearer_auth(access_token)
            .json(&json!({ "refresh_token": refresh_token }))
            .send()
            .await
            .expect("logout request failed");
    }

    // ── Authenticated helpers ───────────────────────────────────────────────

    /// GET /api/v2/me with a bearer token.
    pub async fn me(&self, access_token: &str) -> Value {
        let resp = self
            .client
            .get(format!("{}/api/v2/me", self.base_url))
            .bearer_auth(access_token)
            .send()
            .await
            .expect("me request failed");

        assert!(
            resp.status().is_success(),
            "/me returned {}: {}",
            resp.status(),
            resp.text().await.unwrap_or_default()
        );

        resp.json().await.expect("/me response is not JSON")
    }

    /// Make an arbitrary authenticated GET request.
    pub async fn get_auth(&self, path: &str, access_token: &str) -> reqwest::Response {
        self.client
            .get(format!("{}{}", self.base_url, path))
            .bearer_auth(access_token)
            .send()
            .await
            .expect("authenticated GET failed")
    }

    /// Make an arbitrary authenticated POST request.
    pub async fn post_auth(
        &self,
        path: &str,
        body: Value,
        access_token: &str,
    ) -> reqwest::Response {
        self.client
            .post(format!("{}{}", self.base_url, path))
            .bearer_auth(access_token)
            .json(&body)
            .send()
            .await
            .expect("authenticated POST failed")
    }

    // ── Seed helpers ────────────────────────────────────────────────────────

    /// Create a unique test email using a timestamp to avoid conflicts.
    pub fn unique_email(label: &str) -> String {
        let ts = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        format!("{label}-{ts}@harness.test")
    }

    // ── Cleanup ─────────────────────────────────────────────────────────────

    /// Drop test data created during this test run.
    ///
    /// Note: Since Rust reads Python's shared schema, we only clean rows
    /// inserted via harness helpers (identified by the `@harness.test` email suffix).
    pub async fn cleanup(&self) {
        // Clean sessions first (FK constraint), then workspace_members, workspaces, users.
        let _ = sqlx::query(
            r#"
            DELETE FROM sessions s
            USING users u
            WHERE s.user_id = u.id AND u.email LIKE '%@harness.test'
            "#,
        )
        .execute(&self.pool)
        .await;

        let _ = sqlx::query(
            r#"
            DELETE FROM workspace_members wm
            USING users u
            WHERE wm.user_id = u.id AND u.email LIKE '%@harness.test'
            "#,
        )
        .execute(&self.pool)
        .await;

        let _ = sqlx::query(
            "DELETE FROM workspaces WHERE owner_user_id IN (SELECT id FROM users WHERE email LIKE '%@harness.test')"
        )
        .execute(&self.pool)
        .await;

        let _ = sqlx::query("DELETE FROM users WHERE email LIKE '%@harness.test'")
            .execute(&self.pool)
            .await;
    }
}
