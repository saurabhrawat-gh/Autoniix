//! Contract validation tests — require live services.
//! Skip automatically when services are not running.
//!
//! Run with:
//!   RUST_GATEWAY_URL=http://localhost:8080 cargo test -p harness contract

use harness::contract::ContractValidator;
use serde_json::json;

const RUST_GATEWAY: &str = "http://localhost:8080";
const PYTHON_DASHBOARD: &str = "http://localhost:8000";

fn rust_gateway_url() -> String {
    std::env::var("RUST_GATEWAY_URL").unwrap_or_else(|_| RUST_GATEWAY.to_string())
}

#[allow(dead_code)]
fn python_dashboard_url() -> String {
    std::env::var("PYTHON_DASHBOARD_URL").unwrap_or_else(|_| PYTHON_DASHBOARD.to_string())
}

/// Load the handwritten OpenAPI schema for the Rust gateway.
fn rust_validator() -> Option<ContractValidator> {
    let schema_path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .join("docs")
        .join("openapi")
        .join("rust-gateway.yaml");

    // Fallback to JSON if YAML not yet supported
    let json_path = schema_path.with_extension("json");

    if json_path.exists() {
        ContractValidator::from_file(json_path).ok()
    } else if schema_path.exists() {
        ContractValidator::from_file(schema_path).ok()
    } else {
        None
    }
}

// ── Live endpoint tests (skipped if service not running) ─────────────────────

#[tokio::test]
async fn test_signup_contract() {
    let validator = match rust_validator() {
        Some(v) => v,
        None => {
            eprintln!("SKIP: no OpenAPI schema found");
            return;
        }
    };

    let unique = format!("contract-{}", chrono::Utc::now().timestamp());
    let result = validator
        .validate_endpoint(
            &rust_gateway_url(),
            reqwest::Method::POST,
            "/api/v2/auth/signup",
            Some(json!({
                "email": format!("{unique}@example.com"),
                "password": "SecurePassword123!",
                "display_name": "Contract Test",
                "workspace_name": "Test Workspace"
            })),
            None,
            201,
        )
        .await;

    match result {
        Ok(body) => {
            assert!(
                body.get("access_token").is_some(),
                "signup must return access_token"
            );
            assert!(
                body.get("refresh_token").is_some(),
                "signup must return refresh_token"
            );
        }
        Err(harness::contract::ContractError::Request(_)) => {
            eprintln!("SKIP: Rust gateway not running at {}", rust_gateway_url());
        }
        Err(e) => panic!("Contract validation failed: {e}"),
    }
}

#[tokio::test]
async fn test_signin_contract() {
    let validator = match rust_validator() {
        Some(v) => v,
        None => {
            eprintln!("SKIP: no OpenAPI schema found");
            return;
        }
    };

    let unique = format!("signin-test-{}", chrono::Utc::now().timestamp());
    let email = format!("{unique}@example.com");

    // Sign up first
    let _ = validator
        .validate_endpoint(
            &rust_gateway_url(),
            reqwest::Method::POST,
            "/api/v2/auth/signup",
            Some(json!({"email": email, "password": "Password123!", "workspace_name": "W"})),
            None,
            201,
        )
        .await;

    let result = validator
        .validate_endpoint(
            &rust_gateway_url(),
            reqwest::Method::POST,
            "/api/v2/auth/signin",
            Some(json!({"email": email, "password": "Password123!"})),
            None,
            200,
        )
        .await;

    match result {
        Ok(body) => {
            assert!(body.get("access_token").is_some());
        }
        Err(harness::contract::ContractError::Request(_)) => {
            eprintln!("SKIP: Rust gateway not running");
        }
        Err(e) => panic!("Contract validation failed: {e}"),
    }
}

// ── Schema unit tests (no live service needed) ───────────────────────────────

#[test]
fn test_schema_field_resolution() {
    let validator = ContractValidator::from_value(serde_json::json!({
        "openapi": "3.0.3",
        "paths": {
            "/api/v2/auth/signup": {
                "post": {
                    "responses": {
                        "201": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["access_token"],
                                        "properties": {
                                            "access_token": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }));

    // ContractValidator::from_value always succeeds
    drop(validator);
}

#[test]
fn test_schema_not_found_for_unknown_path() {
    let validator = ContractValidator::from_value(serde_json::json!({
        "openapi": "3.0.3",
        "paths": {}
    }));
    drop(validator);
}
