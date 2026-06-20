use axum::{
    extract::State,
    http::StatusCode,
    response::IntoResponse,
    routing::post,
    Json, Router,
};
use serde::{Deserialize, Serialize};

use crate::{
    auth::AuthServiceImpl,
    error::ApiResult,
};

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
    access_token: String,
    refresh_token: String,
    expires_in: i64,
    user: UserResponse,
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
    refresh_token: String,
}

#[derive(Debug, Serialize)]
struct RefreshTokenResponse {
    access_token: String,
    refresh_token: String,
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
    let (access_token, refresh_token, user) = auth_service
        .sign_in(&req.email, &req.password, req.workspace_id, None, None)
        .await?;
    
    let response = SignInResponse {
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
    };
    
    Ok((StatusCode::OK, Json(response)))
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
    Json(req): Json<RefreshTokenRequest>,
) -> ApiResult<impl IntoResponse> {
    let (access_token, new_refresh_token) = auth_service.refresh_token(&req.refresh_token).await?;
    
    let response = RefreshTokenResponse {
        access_token,
        refresh_token: new_refresh_token,
        expires_in: 3600,
    };
    
    Ok(Json(response))
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
    refresh_token: String,
}

#[derive(Debug, Serialize)]
struct LogoutResponse {
    status: String,
}

async fn logout(
    State(auth_service): State<AuthServiceImpl>,
    Json(req): Json<LogoutRequest>,
) -> ApiResult<impl IntoResponse> {
    auth_service.logout(&req.refresh_token).await?;
    
    let response = LogoutResponse {
        status: "ok".to_string(),
    };
    
    Ok(Json(response))
}
