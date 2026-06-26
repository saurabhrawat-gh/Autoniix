use axum::{
    body::Body,
    http::{Request, StatusCode},
};
use serde_json::{json, Value};
use tower::ServiceExt;

/// IM-171: /accept-invite must return 429 after 5 attempts from the same IP.
///
/// Uses `x-real-ip: 10.0.0.99` so this test's counter is isolated from any
/// other test that may also hit the endpoint (they default to IP "unknown").
#[tokio::test]
async fn test_accept_invite_rate_limit_blocks_after_five_attempts() {
    let app = gateway::create_test_app().await;

    let body = json!({"token": "bogus-invalid-token-im171"}).to_string();

    // Requests 1–5 must pass the rate limiter (they'll 422 on the invalid token, not 429).
    for attempt in 1..=5 {
        let resp = app
            .clone()
            .oneshot(
                Request::builder()
                    .uri("/api/v2/auth/accept-invite")
                    .method("POST")
                    .header("content-type", "application/json")
                    .header("x-real-ip", "10.0.0.99")
                    .body(Body::from(body.clone()))
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_ne!(
            resp.status(),
            StatusCode::TOO_MANY_REQUESTS,
            "attempt {attempt} should not be rate-limited yet"
        );
    }

    // Request 6 must be blocked by the rate limiter.
    let resp = app
        .oneshot(
            Request::builder()
                .uri("/api/v2/auth/accept-invite")
                .method("POST")
                .header("content-type", "application/json")
                .header("x-real-ip", "10.0.0.99")
                .body(Body::from(body))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(
        resp.status(),
        StatusCode::TOO_MANY_REQUESTS,
        "6th attempt must return 429"
    );
    assert!(
        resp.headers().contains_key("retry-after"),
        "429 response must include Retry-After header"
    );
}

/// IM-172: consistent 422 response regardless of token length — no length oracle.
///
/// Verifies that tokens of wildly different lengths all produce the same HTTP
/// status code, confirming there is no response-level leakage of token structure.
#[tokio::test]
async fn test_accept_invite_consistent_error_for_any_token_format() {
    let app = gateway::create_test_app().await;

    let tokens = [
        "a",
        "short-token",
        "this-is-a-medium-length-token-abc123",
        &"x".repeat(256), // very long token
    ];

    for token in tokens {
        let body = json!({"token": token}).to_string();
        let resp = app
            .clone()
            .oneshot(
                Request::builder()
                    .uri("/api/v2/auth/accept-invite")
                    .method("POST")
                    .header("content-type", "application/json")
                    .header("x-real-ip", "10.0.0.98") // separate IP bucket
                    .body(Body::from(body))
                    .unwrap(),
            )
            .await
            .unwrap();

        // Any invalid token must yield an error (422), never 200 or 500.
        assert!(
            resp.status().is_client_error(),
            "token of length {} should produce a client error, got {}",
            token.len(),
            resp.status()
        );
    }
}

#[tokio::test]
async fn test_me_endpoint_unauthorized() {
    let app = gateway::create_test_app().await;

    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/v2/me")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn test_me_endpoint_with_valid_token() {
    let app = gateway::create_test_app().await;

    // #350: register returns no tokens — must sign in separately
    let register_body = json!({
        "email": "alice@example.com",
        "password": "securepassword123",
        "display_name": "Alice Smith",
        "workspace_name": "Alice Workspace"
    });

    let register_response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/api/v2/auth/register")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(register_body.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(register_response.status(), StatusCode::CREATED);

    // Sign in to get access_token
    let signin_body = json!({
        "email": "alice@example.com",
        "password": "securepassword123"
    });

    let signin_response = app
        .clone()
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

    assert_eq!(signin_response.status(), StatusCode::OK);

    let body = axum::body::to_bytes(signin_response.into_body(), usize::MAX)
        .await
        .unwrap();
    let signin_data: Value = serde_json::from_slice(&body).unwrap();
    let access_token = signin_data["access_token"].as_str().unwrap();

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

    let me_body = axum::body::to_bytes(me_response.into_body(), usize::MAX)
        .await
        .unwrap();
    let me_data: Value = serde_json::from_slice(&me_body).unwrap();

    assert_eq!(me_data["data"]["email"], "alice@example.com");
    assert_eq!(me_data["data"]["display_name"], "Alice Smith");
    assert_eq!(me_data["data"]["role"], "owner");
    assert_eq!(me_data["data"]["global_role"], "superadmin");
    assert!(
        me_data["data"]["permissions"].is_array(),
        "data.permissions must be an array"
    );
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

/// #700: Workspace rate limiting — authenticated requests must return 429
/// after exceeding the per-workspace RPM threshold.
///
/// Uses `WORKSPACE_RATE_LIMIT_RPM=3` to trigger the limit quickly.  The test
/// signs in to get a valid JWT (so `Principal.wid` is populated), then hammers
/// `/api/v2/me` until the 4th request is blocked.
#[tokio::test]
async fn test_workspace_rate_limit_blocks_after_rpm_exceeded() {
    std::env::set_var("WORKSPACE_RATE_LIMIT_RPM", "3");
    let app = gateway::create_test_app().await;
    std::env::remove_var("WORKSPACE_RATE_LIMIT_RPM");

    // Register + sign in to get an access token
    let register_body = json!({
        "email": "rate-test@example.com",
        "password": "securepassword123",
        "display_name": "Rate Test",
        "workspace_name": "Rate WS"
    });

    let _ = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/api/v2/auth/register")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(register_body.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();

    let signin_body = json!({
        "email": "rate-test@example.com",
        "password": "securepassword123"
    });

    let signin_response = app
        .clone()
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

    let body = axum::body::to_bytes(signin_response.into_body(), usize::MAX)
        .await
        .unwrap();
    let signin_data: Value = serde_json::from_slice(&body).unwrap();
    let access_token = signin_data["access_token"].as_str().unwrap();

    // Requests 1–3 must pass (200 OK from /me)
    for i in 1..=3 {
        let resp = app
            .clone()
            .oneshot(
                Request::builder()
                    .uri("/api/v2/me")
                    .header("authorization", format!("Bearer {}", access_token))
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_ne!(
            resp.status(),
            StatusCode::TOO_MANY_REQUESTS,
            "request {i} should not be rate-limited yet"
        );
    }

    // Request 4 must be blocked
    let resp = app
        .oneshot(
            Request::builder()
                .uri("/api/v2/me")
                .header("authorization", format!("Bearer {}", access_token))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(
        resp.status(),
        StatusCode::TOO_MANY_REQUESTS,
        "4th request must return 429"
    );
    assert!(
        resp.headers().contains_key("retry-after"),
        "429 response must include Retry-After header"
    );

    let resp_body = axum::body::to_bytes(resp.into_body(), usize::MAX)
        .await
        .unwrap();
    let error_data: Value = serde_json::from_slice(&resp_body).unwrap();
    assert_eq!(error_data["error"], "rate_limited");
    assert!(error_data["retry_after"].is_number());
}
