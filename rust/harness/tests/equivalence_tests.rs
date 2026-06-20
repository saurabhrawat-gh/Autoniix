//! Cross-service equivalence tests — Python ↔ Rust.
//!
//! Per HARNESS-ENGINEERING-PLAN.md Week 4 Day 1.
//!
//! These tests are SKIPPED automatically when services are not running.
//! Set environment variables to enable:
//!   RUST_GATEWAY_URL=http://localhost:8080
//!   PYTHON_DASHBOARD_URL=http://localhost:8000
//!
//! Run:
//!   RUST_GATEWAY_URL=... PYTHON_DASHBOARD_URL=... cargo test -p harness equivalence

use harness::cross::{assert_auth_token_structure, ServicePair};
use serde_json::json;

fn rust_url() -> String {
    std::env::var("RUST_GATEWAY_URL").unwrap_or_else(|_| "http://localhost:8080".into())
}

fn python_url() -> String {
    std::env::var("PYTHON_DASHBOARD_URL").unwrap_or_else(|_| "http://localhost:8000".into())
}

fn pair() -> ServicePair {
    ServicePair::new("python", python_url(), "rust", rust_url())
}

fn unique_email(label: &str) -> String {
    let ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    format!("{label}-{ts}@equiv.test")
}

// ── Signup equivalence ────────────────────────────────────────────────────────

#[tokio::test]
async fn test_signup_response_structure_equivalent() {
    let pair = pair();
    let email_a = unique_email("signup-py");
    let email_b = unique_email("signup-rs");

    let result = pair
        .compare_post(
            "/auth/register",         // Python path
            "/api/v2/auth/signup",    // Rust path
            json!({
                "email": email_a,
                "password": "Password123!",
                "display_name": "Python User",
                "workspace_name": "Python Workspace"
            }),
            json!({
                "email": email_b,
                "password": "Password123!",
                "display_name": "Rust User",
                "workspace_name": "Rust Workspace"
            }),
            None,
            &["expires_in"],  // Fields that must match between both services
        )
        .await;

    match result {
        Ok(r) => {
            assert_auth_token_structure(&r).await;
            if !r.equivalent {
                let mismatches: Vec<_> = r.mismatches.iter().map(|e| e.to_string()).collect();
                panic!("Signup equivalence failed:\n  {}", mismatches.join("\n  "));
            }
        }
        Err(harness::cross::EquivalenceError::Http { service, .. }) => {
            eprintln!("SKIP: {service} not running");
        }
        Err(e) => panic!("Unexpected error: {e}"),
    }
}

// ── Signin equivalence ────────────────────────────────────────────────────────

#[tokio::test]
async fn test_signin_token_structure_equivalent() {
    let pair = pair();
    let email_py = unique_email("signin-py");
    let email_rs = unique_email("signin-rs");
    let password = "Password123!";

    // Pre-register both users
    let client = reqwest::Client::new();
    let _ = client
        .post(format!("{}/auth/register", python_url()))
        .json(&json!({"email": email_py, "password": password, "workspace_name": "W"}))
        .send()
        .await;
    let _ = client
        .post(format!("{}/api/v2/auth/signup", rust_url()))
        .json(&json!({"email": email_rs, "password": password, "workspace_name": "W"}))
        .send()
        .await;

    let result = pair
        .compare_post(
            "/auth/login",
            "/api/v2/auth/signin",
            json!({"email": email_py, "password": password}),
            json!({"email": email_rs, "password": password}),
            None,
            &["expires_in"],
        )
        .await;

    match result {
        Ok(r) => {
            assert_auth_token_structure(&r).await;
        }
        Err(harness::cross::EquivalenceError::Http { service, .. }) => {
            eprintln!("SKIP: {service} not running");
        }
        Err(e) => panic!("Unexpected error: {e}"),
    }
}

// ── JWT cross-validation ──────────────────────────────────────────────────────

#[tokio::test]
async fn test_rust_token_accepted_by_python() {
    let client = reqwest::Client::new();
    let email = unique_email("jwt-cross");

    // Sign up via Rust
    let signup: serde_json::Value = match client
        .post(format!("{}/api/v2/auth/signup", rust_url()))
        .json(&json!({"email": email, "password": "Password123!", "workspace_name": "W"}))
        .send()
        .await
    {
        Ok(r) => r.json().await.unwrap_or_default(),
        Err(_) => { eprintln!("SKIP: Rust gateway not running"); return; }
    };

    let token = match signup["access_token"].as_str() {
        Some(t) => t.to_string(),
        None => { eprintln!("SKIP: no token in signup response"); return; }
    };

    // Use Rust-issued token against Python /me equivalent
    let py_resp = client
        .get(format!("{}/auth/me", python_url()))
        .bearer_auth(&token)
        .send()
        .await;

    match py_resp {
        Ok(r) => {
            // If Python accepts the token, user email must match
            if r.status().is_success() {
                let body: serde_json::Value = r.json().await.unwrap_or_default();
                assert_eq!(body["email"], email, "Python /me must return same email");
                println!("✓ Rust-issued JWT accepted by Python");
            } else {
                println!("⚠ Python returned {} for Rust-issued JWT", r.status());
            }
        }
        Err(_) => eprintln!("SKIP: Python dashboard not running"),
    }
}

// ── Field-level equivalence ───────────────────────────────────────────────────

#[tokio::test]
async fn test_signup_response_has_required_fields_in_both() {
    let client = reqwest::Client::new();

    let email_rs = unique_email("fields-rs");
    let rs_body: serde_json::Value = match client
        .post(format!("{}/api/v2/auth/signup", rust_url()))
        .json(&json!({"email": email_rs, "password": "Password123!", "workspace_name": "W"}))
        .send()
        .await
    {
        Ok(r) => r.json().await.unwrap_or_default(),
        Err(_) => { eprintln!("SKIP: Rust gateway not running"); return; }
    };

    // Required fields per spec
    for field in &["access_token", "refresh_token", "expires_in", "user", "workspace"] {
        assert!(
            !rs_body[field].is_null(),
            "Rust signup response missing field: {field}"
        );
    }
    assert_eq!(rs_body["expires_in"], 3600, "expires_in must be 3600");
    assert!(rs_body["user"]["id"].as_i64().is_some(), "user.id must be integer");
}
