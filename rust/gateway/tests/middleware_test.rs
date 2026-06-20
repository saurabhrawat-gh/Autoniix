use axum::{
    body::Body,
    http::{Request, StatusCode},
};
use serde_json::{json, Value};
use tower::ServiceExt;

#[tokio::test]
async fn test_me_endpoint_unauthorized() {
    let app = gateway::create_test_app().await;
    
    let response = app
        .oneshot(Request::builder().uri("/api/v2/me").body(Body::empty()).unwrap())
        .await
        .unwrap();
    
    assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn test_me_endpoint_with_valid_token() {
    let app = gateway::create_test_app().await;
    
    let signup_body = json!({
        "email": "alice@example.com",
        "password": "securepassword123",
        "display_name": "Alice Smith",
        "workspace_name": "Alice Workspace"
    });
    
    let signup_response = app
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
    
    let body = axum::body::to_bytes(signup_response.into_body(), usize::MAX).await.unwrap();
    let signup_data: Value = serde_json::from_slice(&body).unwrap();
    let access_token = signup_data["access_token"].as_str().unwrap();
    
    let me_response = app
        .oneshot(
            Request::builder()
                .uri("/api/v2/me")
                .header("authorization", format!("Bearer {}", access_token))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    
    assert_eq!(me_response.status(), StatusCode::OK);
    
    let me_body = axum::body::to_bytes(me_response.into_body(), usize::MAX).await.unwrap();
    let me_data: Value = serde_json::from_slice(&me_body).unwrap();
    
    assert_eq!(me_data["data"]["email"], "alice@example.com");
    assert_eq!(me_data["data"]["display_name"], "Alice Smith");
    assert_eq!(me_data["data"]["role"], "owner");
    assert_eq!(me_data["data"]["global_role"], "superadmin");
    assert!(me_data["data"]["permissions"].is_array(), "data.permissions must be an array");
}

#[tokio::test]
async fn test_invalid_bearer_token() {
    let app = gateway::create_test_app().await;
    
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/v2/me")
                .header("authorization", "Bearer invalid.token.here")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    
    assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn test_malformed_auth_header() {
    let app = gateway::create_test_app().await;
    
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/v2/me")
                .header("authorization", "NotBearer token")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    
    assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
}
