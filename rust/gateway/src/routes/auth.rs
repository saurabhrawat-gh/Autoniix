use axum::{
    extract::State,
    http::{header::SET_COOKIE, HeaderName, StatusCode},
    response::{AppendHeaders, IntoResponse},
    routing::post,
    Json, Router,
};
use axum_extra::{headers::Cookie, TypedHeader};
use serde::{Deserialize, Serialize};

use crate::{
    auth::AuthServiceImpl,
    error::{ApiError, ApiResult},
    extractors::AuthUser,
};

// Cookie lifetimes (seconds): access token 1h, refresh token 30d.
const ACCESS_MAX_AGE: i64 = 3600;
const REFRESH_MAX_AGE: i64 = 2_592_000;

/// Build a single `Set-Cookie` header value with the standard secure attributes.
/// Values handled here (JWTs, the literal "1") contain only cookie-safe chars.
fn build_cookie(name: &str, value: &str, max_age: i64, http_only: bool) -> String {
    let mut c = format!("{name}={value}; Path=/; Max-Age={max_age}; SameSite=Lax; Secure");
    if http_only {
        c.push_str("; HttpOnly");
    }
    c
}

/// Set-Cookie headers issued on successful auth: HttpOnly access + refresh
/// tokens, plus a JS-readable `auth_status` flag for the frontend.
fn auth_cookies(access: &str, refresh: &str) -> AppendHeaders<[(HeaderName, String); 3]> {
    AppendHeaders([
        (SET_COOKIE, build_cookie("access_token", access, ACCESS_MAX_AGE, true)),
        (SET_COOKIE, build_cookie("refresh_token", refresh, REFRESH_MAX_AGE, true)),
        (SET_COOKIE, build_cookie("auth_status", "1", ACCESS_MAX_AGE, false)),
    ])
}

/// Set-Cookie headers that clear all auth cookies (Max-Age=0).
fn clear_auth_cookies() -> AppendHeaders<[(HeaderName, String); 3]> {
    AppendHeaders([
        (SET_COOKIE, build_cookie("access_token", "", 0, true)),
        (SET_COOKIE, build_cookie("refresh_token", "", 0, true)),
        (SET_COOKIE, build_cookie("auth_status", "", 0, false)),
    ])
}

/// Resolve a refresh token from the `refresh_token` cookie first, falling back
/// to the JSON body (mirrors Python `v2/auth.py`).
fn resolve_refresh_token(
    cookie: &Option<TypedHeader<Cookie>>,
    body_token: Option<String>,
) -> Option<String> {
    cookie
        .as_ref()
        .and_then(|TypedHeader(c)| c.get("refresh_token").map(|s| s.to_string()))
        .or(body_token)
}

pub fn routes(auth_service: AuthServiceImpl) -> Router {
    Router::new()
        .route("/api/v2/auth/signin", post(sign_in))
        .route("/api/v2/auth/signup", post(sign_up))
        .route("/api/v2/auth/refresh", post(refresh_token))
        .route("/api/v2/auth/verify", post(verify_token))
        .route("/api/v2/auth/logout", post(logout))
        .with_state(auth_service)
}

#[derive(Debug, Deserialize)]
struct SignInRequest {
    email: String,
    password: String,
    workspace_id: Option<i64>,
}

#[derive(Debug, Serialize)]
struct SignInResponse {
    status: String,
    access_token: String,
    expires_in: i64,
    user: SignInUser,
    #[serde(skip_serializing_if = "Option::is_none")]
    setup_required: Option<bool>,
}

/// Signin user object, matching Python `/auth/login` (workspace-scoped `role`,
/// `workspace_id`).
#[derive(Debug, Serialize)]
struct SignInUser {
    id: i64,
    email: String,
    role: String,
    workspace_id: Option<i64>,
}

#[derive(Debug, Deserialize)]
struct SignUpRequest {
    email: String,
    password: String,
    display_name: Option<String>,
    workspace_name: String,
}

#[derive(Debug, Serialize)]
struct SignUpResponse {
    access_token: String,
    refresh_token: String,
    expires_in: i64,
    user: UserResponse,
    workspace: WorkspaceResponse,
}

#[derive(Debug, Deserialize)]
struct RefreshTokenRequest {
    refresh_token: Option<String>,
}

#[derive(Debug, Serialize)]
struct RefreshTokenResponse {
    status: String,
    access_token: String,
    expires_in: i64,
}

#[derive(Debug, Deserialize)]
struct VerifyTokenRequest {
    token: String,
}

#[derive(Debug, Serialize)]
struct VerifyTokenResponse {
    valid: bool,
    user_id: Option<String>,
    wid: Option<i64>,
    email: Option<String>,
    role: Option<String>,
    global_role: Option<String>,
}

#[derive(Debug, Serialize)]
struct UserResponse {
    id: i64,
    email: String,
    display_name: Option<String>,
    active_workspace_id: Option<i64>,
    role: String,
}

#[derive(Debug, Serialize)]
struct WorkspaceResponse {
    id: i64,
    name: String,
    slug: String,
    owner_user_id: i64,
}

async fn sign_in(
    State(auth_service): State<AuthServiceImpl>,
    Json(req): Json<SignInRequest>,
) -> ApiResult<impl IntoResponse> {
    let (access_token, refresh_token, user, ws_role, wid) = auth_service
        .sign_in(&req.email, &req.password, req.workspace_id, None, None)
        .await?;
    
    let workspace_id = if wid > 0 { Some(wid) } else { None };
    let response = SignInResponse {
        status: "ok".to_string(),
        access_token: access_token.clone(),
        expires_in: 3600,
        user: SignInUser {
            id: user.id,
            email: user.email,
            role: ws_role,
            workspace_id,
        },
        setup_required: if workspace_id.is_none() { Some(true) } else { None },
    };
    
    Ok((StatusCode::OK, auth_cookies(&access_token, &refresh_token), Json(response)))
}

async fn sign_up(
    State(auth_service): State<AuthServiceImpl>,
    Json(req): Json<SignUpRequest>,
) -> ApiResult<impl IntoResponse> {
    if req.password.len() < 8 {
        return Err(crate::error::ApiError::Validation(
            "Password must be at least 8 characters".to_string(),
        ));
    }
    
    let (access_token, refresh_token, user, workspace) = auth_service
        .sign_up(
            &req.email,
            &req.password,
            req.display_name.as_deref(),
            &req.workspace_name,
            None,
            None,
        )
        .await?;
    
    let response = SignUpResponse {
        access_token,
        refresh_token,
        expires_in: 3600,
        user: UserResponse {
            id: user.id,
            email: user.email,
            display_name: user.display_name,
            active_workspace_id: user.active_workspace_id,
            role: user.role,
        },
        workspace: WorkspaceResponse {
            id: workspace.id,
            name: workspace.name,
            slug: workspace.slug,
            owner_user_id: workspace.owner_user_id,
        },
    };
    
    Ok((StatusCode::CREATED, Json(response)))
}

async fn refresh_token(
    State(auth_service): State<AuthServiceImpl>,
    cookie: Option<TypedHeader<Cookie>>,
    body: Option<Json<RefreshTokenRequest>>,
) -> ApiResult<impl IntoResponse> {
    let token = resolve_refresh_token(&cookie, body.and_then(|Json(b)| b.refresh_token))
        .ok_or(ApiError::Unauthorized)?;
    
    let (access_token, new_refresh_token) = auth_service.refresh_token(&token).await?;
    
    let response = RefreshTokenResponse {
        status: "ok".to_string(),
        access_token: access_token.clone(),
        expires_in: 3600,
    };
    
    Ok((StatusCode::OK, auth_cookies(&access_token, &new_refresh_token), Json(response)))
}

async fn verify_token(
    State(auth_service): State<AuthServiceImpl>,
    Json(req): Json<VerifyTokenRequest>,
) -> ApiResult<impl IntoResponse> {
    match auth_service.verify_token(&req.token) {
        Ok(claims) => {
            let response = VerifyTokenResponse {
                valid: true,
                user_id: Some(claims.sub),
                wid: Some(claims.wid),
                email: Some(claims.email),
                role: Some(claims.role),
                global_role: Some(claims.global_role),
            };
            Ok(Json(response))
        }
        Err(_) => {
            let response = VerifyTokenResponse {
                valid: false,
                user_id: None,
                wid: None,
                email: None,
                role: None,
                global_role: None,
            };
            Ok(Json(response))
        }
    }
}

#[derive(Debug, Deserialize)]
struct LogoutRequest {
    refresh_token: Option<String>,
}

#[derive(Debug, Serialize)]
struct LogoutResponse {
    status: String,
}

async fn logout(
    _user: AuthUser,
    State(auth_service): State<AuthServiceImpl>,
    cookie: Option<TypedHeader<Cookie>>,
    body: Option<Json<LogoutRequest>>,
) -> ApiResult<impl IntoResponse> {
    // Authentication is required (AuthUser). Revoke the session identified by the
    // refresh token from the cookie or body, then clear all auth cookies.
    if let Some(token) = resolve_refresh_token(&cookie, body.and_then(|Json(b)| b.refresh_token)) {
        auth_service.logout(&token).await?;
    }
    
    let response = LogoutResponse {
        status: "ok".to_string(),
    };
    
    Ok((StatusCode::OK, clear_auth_cookies(), Json(response)))
}
