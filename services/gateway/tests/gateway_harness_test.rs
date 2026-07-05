//! Gateway integration tests using GatewayHarness.
//!
//! Per HARNESS-ENGINEERING-PLAN.md Week 2.
//! Replaces the manual setup previously in tests/*.rs.
//!
//! Run with: TEST_DATABASE_URL=postgresql://... cargo test -p gateway

mod common;
use common::GatewayHarness;

#[tokio::test]
async fn test_register_creates_user_and_workspace() {
    let h = GatewayHarness::new().await;
    let email = GatewayHarness::unique_email("register");

    // #350: register returns onboarding metadata, NOT tokens
    let body = h
        .register(&email, "Password123!", "Harness User", "Harness Workspace")
        .await;

    assert_eq!(body["status"], "ok");
    assert!(body["user_id"].is_i64(), "must return user_id");
    assert!(body["workspace_id"].is_i64(), "must return workspace_id");
    assert_eq!(body["role"], "owner");
    assert_eq!(body["onboarding_required"], true);
    assert!(
        body.get("access_token").is_none(),
        "must NOT return access_token"
    );

    h.cleanup().await;
}

#[tokio::test]
async fn test_signin_with_valid_credentials() {
    let h = GatewayHarness::new().await;
    let email = GatewayHarness::unique_email("signin");

    h.signup(&email, "Password123!", "Signin User", "Signin Workspace")
        .await;
    let body = h.signin(&email, "Password123!").await;

    assert!(body["access_token"].as_str().is_some());
    assert_eq!(body["user"]["email"], email);

    h.cleanup().await;
}

#[tokio::test]
async fn test_signin_wrong_password_returns_401() {
    let h = GatewayHarness::new().await;
    let email = GatewayHarness::unique_email("bad-pw");

    h.signup(&email, "CorrectPassword!", "Bad PW User", "Workspace")
        .await;

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

    // signup() calls signin() internally, which sets the refresh_token as an
    // HttpOnly cookie. The harness client has cookie_store(true), so the
    // cookie is stored automatically for subsequent requests.
    h.signup(&email, "Password123!", "Refresh User", "Workspace")
        .await;

    // Use the stored cookie to refresh (the refresh_token is NOT in the JSON body)
    let refresh_body = h.refresh_via_cookie().await;
    assert!(
        refresh_body["access_token"].as_str().is_some(),
        "refresh must return new access_token"
    );

    h.cleanup().await;
}

#[tokio::test]
async fn test_logout_revokes_session() {
    let h = GatewayHarness::new().await;
    let email = GatewayHarness::unique_email("logout");

    // signup() signs in and sets refresh_token as an HttpOnly cookie.
    // The harness client stores it automatically (cookie_store=true).
    let body = h
        .signup(&email, "Password123!", "Logout User", "Workspace")
        .await;
    let access_token = body["access_token"].as_str().unwrap();

    // Logout using the stored cookie (refresh_token is NOT in the JSON body)
    h.logout_via_cookie(access_token).await;

    // After logout the server clears the cookie; refresh must fail
    let after_logout = h.refresh_via_cookie().await;
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

    assert_eq!(me["data"]["email"], email);
    assert!(
        me["data"]["user_id"].as_i64().is_some(),
        "data.user_id must be i64"
    );
    assert!(me["data"]["role"].as_str().is_some(), "data must have role");
    assert!(
        me["data"]["workspace_id"].as_i64().is_some(),
        "data.workspace_id must be i64"
    );
    assert!(
        me["data"]["permissions"].is_array(),
        "data.permissions must be an array"
    );

    h.cleanup().await;
}

#[tokio::test]
async fn test_me_without_token_returns_401() {
    let h = GatewayHarness::new().await;

    let resp = h
        .client
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

    h.register(&email, "Password123!", "User One", "Workspace One")
        .await;

    let resp = h
        .client
        .post(format!("{}/api/v2/auth/register", h.base_url))
        .json(&serde_json::json!({
            "email": email,
            "password": "Password123!",
            "workspace_name": "Workspace Two"
        }))
        .send()
        .await
        .unwrap();

    assert_eq!(
        resp.status().as_u16(),
        409,
        "duplicate email must return 409"
    );
    h.cleanup().await;
}
