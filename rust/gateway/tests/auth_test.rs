use axum::{
    body::Body,
    http::{Request, StatusCode},
};
use serde_json::{json, Value};
use tower::ServiceExt;

#[tokio::test]
async fn test_health_check() {
    let app = gateway::create_test_app().await;
    
    let response = app
        .oneshot(Request::builder().uri("/health/live").body(Body::empty()).unwrap())
        .await
        .unwrap();
    
    assert_eq!(response.status(), StatusCode::OK);
}

#[tokio::test]
async fn test_auth_mode_is_public() {
    let app = gateway::create_test_app().await;
    
    let response = app
        .oneshot(Request::builder().uri("/api/v2/auth/mode").body(Body::empty()).unwrap())
        .await
        .unwrap();
    
    // Public endpoint — no auth required.
    assert_eq!(response.status(), StatusCode::OK);
    
    let body = axum::body::to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let data: Value = serde_json::from_slice(&body).unwrap();
    assert!(data["v2_enabled"].is_boolean(), "v2_enabled must be a bool");
    assert!(data["legacy_enabled"].is_boolean(), "legacy_enabled must be a bool");
}

#[tokio::test]
async fn test_sign_up_and_sign_in() {
    let app = gateway::create_test_app().await;
    
    let signup_body = json!({
        "email": "test@example.com",
        "password": "securepassword123",
        "full_name": "Test User",
        "workspace_name": "Test Workspace"
    });
    
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/api/v2/auth/signup")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(signup_body.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    
    assert_eq!(response.status(), StatusCode::CREATED);
    
    let body = axum::body::to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let signup_response: Value = serde_json::from_slice(&body).unwrap();
    
    assert!(signup_response["access_token"].is_string());
    assert!(signup_response["refresh_token"].is_string());
    assert_eq!(signup_response["user"]["email"], "test@example.com");
    
    let signin_body = json!({
        "email": "test@example.com",
        "password": "securepassword123"
    });
    
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/v2/auth/signin")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(signin_body.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    
    assert_eq!(response.status(), StatusCode::OK);
}

#[tokio::test]
async fn test_sign_in_invalid_credentials() {
    let app = gateway::create_test_app().await;
    
    let signin_body = json!({
        "email": "nonexistent@example.com",
        "password": "wrongpassword"
    });
    
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/v2/auth/signin")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(signin_body.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    
    assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn test_forgot_password_is_public() {
    let app = gateway::create_test_app().await;
    
    let body = json!({"email": "nonexistent@example.com"});
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/v2/auth/forgot")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(body.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    
    // Always returns 200 — never leaks whether email exists.
    assert_eq!(response.status(), StatusCode::OK);
    let body = axum::body::to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let data: Value = serde_json::from_slice(&body).unwrap();
    assert_eq!(data["status"], "ok");
}

#[tokio::test]
async fn test_reset_password_rejects_invalid_token() {
    let app = gateway::create_test_app().await;
    
    let body = json!({"token": "invalid-token", "password": "newpassword123"});
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/v2/auth/reset")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(body.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
}

#[tokio::test]
async fn test_reset_password_validates_min_length() {
    let app = gateway::create_test_app().await;
    
    let body = json!({"token": "some-token", "password": "short"});
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/v2/auth/reset")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(body.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
}

#[tokio::test]
async fn test_mfa_setup_requires_auth() {
    let app = gateway::create_test_app().await;
    
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/v2/auth/mfa/setup")
                .method("POST")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    
    assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn test_mfa_verify_requires_auth() {
    let app = gateway::create_test_app().await;
    
    let body = json!({"code": "123456"});
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/v2/auth/mfa/verify")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(body.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    
    assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
}
