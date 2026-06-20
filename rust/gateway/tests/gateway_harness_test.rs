//! Gateway integration tests using GatewayHarness.
//!
//! Per HARNESS-ENGINEERING-PLAN.md Week 2.
//! Replaces the manual setup previously in tests/*.rs.
//!
//! Run with: TEST_DATABASE_URL=postgresql://... cargo test -p gateway

mod common;
use common::GatewayHarness;

#[tokio::test]
async fn test_signup_creates_user_and_workspace() {
    let h = GatewayHarness::new().await;
    let email = GatewayHarness::unique_email("signup");

    let body = h.signup(&email, "Password123!", "Harness User", "Harness Workspace").await;

    assert!(body["access_token"].as_str().is_some(), "missing access_token");
    assert!(body["refresh_token"].as_str().is_some(), "missing refresh_token");
    assert_eq!(body["expires_in"], 3600);
    assert_eq!(body["user"]["email"], email);
    assert!(body["workspace"]["id"].as_i64().is_some(), "workspace.id must be i64");

    h.cleanup().await;
}

#[tokio::test]
async fn test_signin_with_valid_credentials() {
    let h = GatewayHarness::new().await;
    let email = GatewayHarness::unique_email("signin");

    h.signup(&email, "Password123!", "Signin User", "Signin Workspace").await;
    let body = h.signin(&email, "Password123!").await;

    assert!(body["access_token"].as_str().is_some());
    assert_eq!(body["user"]["email"], email);

    h.cleanup().await;
}

#[tokio::test]
async fn test_signin_wrong_password_returns_401() {
    let h = GatewayHarness::new().await;
    let email = GatewayHarness::unique_email("bad-pw");

    h.signup(&email, "CorrectPassword!", "Bad PW User", "Workspace").await;

    let resp = h
        .client
        .post(format!("{}/api/v2/auth/signin", h.base_url))
        .json(&serde_json::json!({ "email": email, "password": "WrongPassword!" }))
        .send()
        .await
        .unwrap();

    assert_eq!(resp.status().as_u16(), 401);
    h.cleanup().await;
}

#[tokio::test]
async fn test_refresh_rotates_token() {
    let h = GatewayHarness::new().await;
    let email = GatewayHarness::unique_email("refresh");

    let signup_body = h.signup(&email, "Password123!", "Refresh User", "Workspace").await;
    let refresh_token = signup_body["refresh_token"].as_str().unwrap();

    let refresh_body = h.refresh(refresh_token).await;
    assert!(refresh_body["access_token"].as_str().is_some(), "refresh must return new access_token");
    assert!(refresh_body["refresh_token"].as_str().is_some(), "refresh must rotate refresh_token");

    // Old refresh token should now be revoked
    let second_refresh = h.refresh(refresh_token).await;
    assert!(
        second_refresh.get("error").is_some() || second_refresh["access_token"].is_null(),
        "old refresh token must be invalid after rotation"
    );

    h.cleanup().await;
}

#[tokio::test]
async fn test_logout_revokes_session() {
    let h = GatewayHarness::new().await;
    let email = GatewayHarness::unique_email("logout");

    let body = h.signup(&email, "Password123!", "Logout User", "Workspace").await;
    let refresh_token = body["refresh_token"].as_str().unwrap();

    h.logout(refresh_token).await;

    // Refresh should now fail
    let after_logout = h.refresh(refresh_token).await;
    assert!(
        after_logout.get("error").is_some() || after_logout["access_token"].is_null(),
        "refresh must fail after logout"
    );

    h.cleanup().await;
}

#[tokio::test]
async fn test_me_returns_current_user() {
    let h = GatewayHarness::new().await;
    let email = GatewayHarness::unique_email("me");

    let token = h.signup_and_get_token(&email, "Password123!").await;
    let me = h.me(&token).await;

    assert_eq!(me["user"]["email"], email);
    assert!(me["user"]["id"].as_i64().is_some(), "user.id must be i64");
    assert!(me["user"]["role"].as_str().is_some(), "user must have role");
    assert!(me["workspace"]["id"].as_i64().is_some(), "workspace.id must be i64");

    h.cleanup().await;
}

#[tokio::test]
async fn test_me_without_token_returns_401() {
    let h = GatewayHarness::new().await;

    let resp = h.client
        .get(format!("{}/api/v2/me", h.base_url))
        .send()
        .await
        .unwrap();

    assert_eq!(resp.status().as_u16(), 401);
}

#[tokio::test]
async fn test_duplicate_email_returns_409() {
    let h = GatewayHarness::new().await;
    let email = GatewayHarness::unique_email("dup");

    h.signup(&email, "Password123!", "User One", "Workspace One").await;

    let resp = h
        .client
        .post(format!("{}/api/v2/auth/signup", h.base_url))
        .json(&serde_json::json!({
            "email": email,
            "password": "Password123!",
            "workspace_name": "Workspace Two"
        }))
        .send()
        .await
        .unwrap();

    assert_eq!(resp.status().as_u16(), 409, "duplicate email must return 409");
    h.cleanup().await;
}
