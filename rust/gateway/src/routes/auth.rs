use axum::{
    extract::State,
    http::{header::SET_COOKIE, HeaderMap, HeaderName, StatusCode},
    response::{AppendHeaders, IntoResponse},
    routing::{get, post, put},
    Json, Router,
};
use axum_extra::{headers::Cookie, TypedHeader};
use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

use crate::{
    auth::{AuthServiceImpl, SignInResult},
    error::{ApiError, ApiResult},
    extractors::AuthUser,
    middleware::{invite_rate_limit, InviteRateLimiter},
};

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
        (
            SET_COOKIE,
            build_cookie("access_token", access, ACCESS_MAX_AGE, true),
        ),
        (
            SET_COOKIE,
            build_cookie("refresh_token", refresh, REFRESH_MAX_AGE, true),
        ),
        (
            SET_COOKIE,
            build_cookie("auth_status", "1", REFRESH_MAX_AGE, false),
        ),
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

/// Extract the client IP from `X-Real-IP` (set by Traefik) or the first entry
/// of `X-Forwarded-For`. Returns `None` when neither header is present.
fn extract_ip(headers: &HeaderMap) -> Option<String> {
    headers
        .get("x-real-ip")
        .or_else(|| headers.get("x-forwarded-for"))
        .and_then(|v| v.to_str().ok())
        .map(|s| s.split(',').next().unwrap_or(s).trim().to_string())
}

/// Extract the `User-Agent` string, or `None` when absent.
fn extract_ua(headers: &HeaderMap) -> Option<String> {
    headers
        .get("user-agent")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string())
}

pub fn routes(auth_service: AuthServiceImpl) -> Router {
    let invite_limiter = InviteRateLimiter::new();

    Router::new()
        .route("/api/v2/auth/mode", get(auth_mode))
        .route("/api/v2/auth/signin", post(sign_in))
        .route("/api/v2/auth/register", post(register))
        .route("/api/v2/auth/signup", post(register))
        .route("/api/v2/auth/refresh", post(refresh_token))
        .route("/api/v2/auth/verify", post(verify_token))
        .route("/api/v2/auth/logout", post(logout))
        .route("/api/v2/auth/profile", put(update_profile))
        .route("/api/v2/auth/forgot", post(forgot_password))
        .route("/api/v2/auth/reset", post(reset_password))
        .route("/api/v2/auth/mfa/setup", post(mfa_setup))
        .route("/api/v2/auth/mfa/verify", post(mfa_verify))
        .route("/api/v2/auth/mfa/challenge", post(mfa_challenge))
        .route("/api/v2/auth/mfa/disable", post(mfa_disable))
        .route(
            "/api/v2/auth/accept-invite",
            post(accept_invite).layer(axum::middleware::from_fn_with_state(
                invite_limiter,
                invite_rate_limit,
            )),
        )
        .with_state(auth_service)
}

#[derive(Debug, Serialize, ToSchema)]
pub(crate) struct AuthModeResponse {
    v2_enabled: bool,
    legacy_enabled: bool,
}

/// Public endpoint: which auth backends are active. The login UI calls this on
/// mount. Mirrors Python `GET /auth/mode`.
#[utoipa::path(
    get,
    path = "/api/v2/auth/mode",
    responses(
        (status = 200, description = "Active auth backends", body = AuthModeResponse),
    ),
    tag = "auth",
)]
pub(crate) async fn auth_mode(State(auth_service): State<AuthServiceImpl>) -> impl IntoResponse {
    let (v2_enabled, legacy_enabled) = auth_service.auth_mode().await;
    Json(AuthModeResponse {
        v2_enabled,
        legacy_enabled,
    })
}

#[derive(Debug, Deserialize, ToSchema)]
pub(crate) struct UpdateProfileRequest {
    display_name: Option<String>,
    current_password: Option<String>,
    new_password: Option<String>,
}

#[derive(Debug, Serialize, ToSchema)]
pub(crate) struct UpdateProfileResponse {
    status: String,
    message: String,
}

/// PUT /api/v2/auth/profile — update display_name and/or password.
/// Mirrors Python `PUT /auth/profile`.
#[utoipa::path(
    put,
    path = "/api/v2/auth/profile",
    request_body = UpdateProfileRequest,
    responses(
        (status = 200, description = "Profile updated", body = UpdateProfileResponse),
        (status = 400, description = "Validation error"),
        (status = 401, description = "Unauthorized"),
    ),
    security(("cookie_auth" = [])),
    tag = "auth",
)]
pub(crate) async fn update_profile(
    State(auth_service): State<AuthServiceImpl>,
    AuthUser(principal): AuthUser,
    Json(req): Json<UpdateProfileRequest>,
) -> ApiResult<impl IntoResponse> {
    let user_id: i64 = principal
        .user_id
        .parse()
        .map_err(|_| ApiError::Unauthorized)?;

    auth_service
        .update_profile(
            user_id,
            req.display_name.as_deref(),
            req.current_password.as_deref(),
            req.new_password.as_deref(),
        )
        .await?;

    Ok(Json(UpdateProfileResponse {
        status: "ok".to_string(),
        message: "Profile updated".to_string(),
    }))
}

#[derive(Debug, Deserialize, ToSchema)]
pub(crate) struct ForgotRequest {
    email: String,
}

#[derive(Debug, Serialize, ToSchema)]
pub(crate) struct StatusResponse {
    status: String,
}

/// POST /api/v2/auth/forgot — public; never leaks whether email exists.
#[utoipa::path(
    post,
    path = "/api/v2/auth/forgot",
    request_body = ForgotRequest,
    responses(
        (status = 200, description = "Accepted (regardless of email existence)", body = StatusResponse),
    ),
    tag = "auth",
)]
pub(crate) async fn forgot_password(
    State(auth_service): State<AuthServiceImpl>,
    Json(req): Json<ForgotRequest>,
) -> Result<Json<StatusResponse>, ApiError> {
    auth_service.forgot_password(&req.email).await?;
    Ok(Json(StatusResponse {
        status: "ok".to_string(),
    }))
}

#[derive(Debug, Deserialize, ToSchema)]
pub(crate) struct ResetRequest {
    token: String,
    password: String,
}

/// POST /api/v2/auth/reset — public; validates the reset token and sets a new
/// password.
#[utoipa::path(
    post,
    path = "/api/v2/auth/reset",
    request_body = ResetRequest,
    responses(
        (status = 200, description = "Password reset", body = StatusResponse),
        (status = 400, description = "Invalid token or weak password"),
    ),
    tag = "auth",
)]
pub(crate) async fn reset_password(
    State(auth_service): State<AuthServiceImpl>,
    Json(req): Json<ResetRequest>,
) -> Result<Json<StatusResponse>, ApiError> {
    if req.password.len() < 8 {
        return Err(ApiError::Validation(
            "Password must be at least 8 characters".to_string(),
        ));
    }
    auth_service
        .reset_password(&req.token, &req.password)
        .await?;
    Ok(Json(StatusResponse {
        status: "ok".to_string(),
    }))
}

#[derive(Debug, Serialize, ToSchema)]
pub(crate) struct MfaSetupResponse {
    data: MfaSetupData,
}

#[derive(Debug, Serialize, ToSchema)]
pub(crate) struct MfaSetupData {
    otpauth_url: String,
    secret: String,
}

/// POST /api/v2/auth/mfa/setup — requires auth; generates a TOTP secret and
/// returns the otpauth URI.
#[utoipa::path(
    post,
    path = "/api/v2/auth/mfa/setup",
    responses(
        (status = 200, description = "TOTP secret and otpauth URI", body = MfaSetupResponse),
        (status = 401, description = "Unauthorized"),
    ),
    security(("cookie_auth" = [])),
    tag = "auth",
)]
pub(crate) async fn mfa_setup(
    State(auth_service): State<AuthServiceImpl>,
    AuthUser(principal): AuthUser,
) -> Result<Json<MfaSetupResponse>, ApiError> {
    let user_id: i64 = principal
        .user_id
        .parse()
        .map_err(|_| ApiError::Unauthorized)?;
    let (otpauth_url, secret) = auth_service.mfa_setup(user_id, &principal.email).await?;
    Ok(Json(MfaSetupResponse {
        data: MfaSetupData {
            otpauth_url,
            secret,
        },
    }))
}

#[derive(Debug, Deserialize, ToSchema)]
pub(crate) struct MfaVerifyRequest {
    code: String,
}

/// POST /api/v2/auth/mfa/verify — requires auth; verifies the TOTP code and
/// enables MFA.
#[utoipa::path(
    post,
    path = "/api/v2/auth/mfa/verify",
    request_body = MfaVerifyRequest,
    responses(
        (status = 200, description = "MFA enabled", body = StatusResponse),
        (status = 400, description = "Invalid code"),
        (status = 401, description = "Unauthorized"),
    ),
    security(("cookie_auth" = [])),
    tag = "auth",
)]
pub(crate) async fn mfa_verify(
    State(auth_service): State<AuthServiceImpl>,
    AuthUser(principal): AuthUser,
    Json(req): Json<MfaVerifyRequest>,
) -> Result<Json<StatusResponse>, ApiError> {
    let user_id: i64 = principal
        .user_id
        .parse()
        .map_err(|_| ApiError::Unauthorized)?;
    auth_service.mfa_verify(user_id, &req.code).await?;
    Ok(Json(StatusResponse {
        status: "ok".to_string(),
    }))
}

#[derive(Debug, Deserialize, ToSchema)]
pub(crate) struct SignInRequest {
    email: String,
    password: String,
    workspace_id: Option<i64>,
}

#[derive(Debug, Serialize, ToSchema)]
pub(crate) struct SignInResponse {
    status: String,
    access_token: String,
    expires_in: i64,
    user: SignInUser,
    #[serde(skip_serializing_if = "Option::is_none")]
    setup_required: Option<bool>,
}

/// Signin user object, matching Python `/auth/login` (workspace-scoped `role`,
/// `workspace_id`).
#[derive(Debug, Serialize, ToSchema)]
pub(crate) struct SignInUser {
    id: i64,
    email: String,
    role: String,
    workspace_id: Option<i64>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub(crate) struct RegisterRequest {
    email: String,
    password: String,
    display_name: Option<String>,
    workspace_name: String,
}

/// #350: Register response — no tokens (no auto-login). Returns onboarding
/// metadata only, matching Python `POST /auth/register`.
#[derive(Debug, Serialize, ToSchema)]
pub(crate) struct RegisterResponse {
    status: String,
    user_id: i64,
    workspace_id: i64,
    role: String,
    onboarding_required: bool,
}

#[derive(Debug, Deserialize, ToSchema)]
pub(crate) struct RefreshTokenRequest {
    refresh_token: Option<String>,
}

#[derive(Debug, Serialize, ToSchema)]
pub(crate) struct RefreshTokenResponse {
    status: String,
    access_token: String,
    expires_in: i64,
}

#[derive(Debug, Deserialize, ToSchema)]
pub(crate) struct VerifyTokenRequest {
    token: String,
}

#[derive(Debug, Serialize, ToSchema)]
pub(crate) struct VerifyTokenResponse {
    valid: bool,
    user_id: Option<String>,
    wid: Option<i64>,
    email: Option<String>,
    role: Option<String>,
    global_role: Option<String>,
}

/// POST /api/v2/auth/signin — public; primary login endpoint.
/// Returns full session tokens + auth cookies on success. For MFA-enabled
/// accounts, returns a pending token instead and requires /mfa/challenge.
#[utoipa::path(
    post,
    path = "/api/v2/auth/signin",
    request_body = SignInRequest,
    responses(
        (status = 200, description = "Signed in (or MFA required)", body = SignInResponse),
        (status = 401, description = "Invalid credentials"),
    ),
    tag = "auth",
)]
pub(crate) async fn sign_in(
    State(auth_service): State<AuthServiceImpl>,
    headers: HeaderMap,
    Json(req): Json<SignInRequest>,
) -> ApiResult<impl IntoResponse> {
    let ip = extract_ip(&headers);
    let ua = extract_ua(&headers);
    match auth_service
        .sign_in(
            &req.email,
            &req.password,
            req.workspace_id,
            ip.as_deref(),
            ua.as_deref(),
        )
        .await?
    {
        SignInResult::MfaRequired { mfa_pending_token } => Ok((
            StatusCode::OK,
            Json(serde_json::json!({
                "status": "mfa_required",
                "mfa_required": true,
                "mfa_pending_token": mfa_pending_token,
            })),
        )
            .into_response()),

        SignInResult::Success {
            access_token,
            refresh_token,
            user,
            ws_role,
            wid,
        } => {
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
                setup_required: if workspace_id.is_none() {
                    Some(true)
                } else {
                    None
                },
            };
            Ok((
                StatusCode::OK,
                auth_cookies(&access_token, &refresh_token),
                Json(response),
            )
                .into_response())
        }
    }
}

#[derive(Debug, Deserialize, ToSchema)]
pub(crate) struct MfaChallengeRequest {
    mfa_pending_token: String,
    code: String,
}

/// POST /api/v2/auth/mfa/challenge — second factor for MFA-enabled accounts.
/// Accepts the short-lived pending token from /signin plus the TOTP code.
/// On success: issues full session tokens + auth cookies, identical to /signin.
#[utoipa::path(
    post,
    path = "/api/v2/auth/mfa/challenge",
    request_body = MfaChallengeRequest,
    responses(
        (status = 200, description = "MFA verified, session issued", body = SignInResponse),
        (status = 401, description = "Invalid pending token or code"),
    ),
    tag = "auth",
)]
pub(crate) async fn mfa_challenge(
    State(auth_service): State<AuthServiceImpl>,
    headers: HeaderMap,
    Json(req): Json<MfaChallengeRequest>,
) -> ApiResult<impl IntoResponse> {
    let ip = extract_ip(&headers);
    let ua = extract_ua(&headers);
    let (access_token, refresh_token, user, ws_role, wid) = auth_service
        .complete_mfa_signin(
            &req.mfa_pending_token,
            &req.code,
            ip.as_deref(),
            ua.as_deref(),
        )
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
        setup_required: None,
    };

    Ok((
        StatusCode::OK,
        auth_cookies(&access_token, &refresh_token),
        Json(response),
    ))
}

#[derive(Debug, Deserialize, ToSchema)]
pub(crate) struct MfaDisableRequest {
    code: String,
}

/// POST /api/v2/auth/mfa/disable — requires auth + valid TOTP code.
/// Disables MFA on the account and clears the stored secret.
#[utoipa::path(
    post,
    path = "/api/v2/auth/mfa/disable",
    request_body = MfaDisableRequest,
    responses(
        (status = 200, description = "MFA disabled", body = StatusResponse),
        (status = 401, description = "Unauthorized or invalid code"),
    ),
    security(("cookie_auth" = [])),
    tag = "auth",
)]
pub(crate) async fn mfa_disable(
    State(auth_service): State<AuthServiceImpl>,
    AuthUser(principal): AuthUser,
    Json(req): Json<MfaDisableRequest>,
) -> ApiResult<impl IntoResponse> {
    let user_id: i64 = principal
        .user_id
        .parse()
        .map_err(|_| ApiError::Unauthorized)?;
    auth_service.mfa_disable(user_id, &req.code).await?;
    Ok(Json(StatusResponse {
        status: "ok".to_string(),
    }))
}

/// POST /api/v2/auth/register — public self-serve signup (#350).
/// No auto-login: returns onboarding metadata only. The frontend calls
/// /signin separately after register. Mirrors Python `POST /auth/register`.
/// Also mounted at `/api/v2/auth/signup` (alias).
#[utoipa::path(
    post,
    path = "/api/v2/auth/register",
    request_body = RegisterRequest,
    responses(
        (status = 201, description = "Account and workspace created", body = RegisterResponse),
        (status = 400, description = "Validation error or duplicate email"),
    ),
    tag = "auth",
)]
pub(crate) async fn register(
    State(auth_service): State<AuthServiceImpl>,
    Json(req): Json<RegisterRequest>,
) -> ApiResult<impl IntoResponse> {
    if req.password.len() < 8 {
        return Err(crate::error::ApiError::Validation(
            "Password must be at least 8 characters".to_string(),
        ));
    }

    let (user_id, workspace_id, role) = auth_service
        .register(
            &req.email,
            &req.password,
            req.display_name.as_deref(),
            &req.workspace_name,
        )
        .await?;

    let response = RegisterResponse {
        status: "ok".to_string(),
        user_id,
        workspace_id,
        role,
        onboarding_required: true,
    };

    Ok((StatusCode::CREATED, Json(response)))
}

#[derive(Debug, Deserialize, ToSchema)]
pub(crate) struct AcceptInviteRequest {
    token: String,
    password: Option<String>,
    display_name: Option<String>,
}

/// POST /api/v2/auth/accept-invite — accept a workspace invitation.
/// For new users: `password` is required to set credentials.
/// For existing users: `password` is ignored.
/// On success: issues full session tokens + auth cookies (auto-login).
#[utoipa::path(
    post,
    path = "/api/v2/auth/accept-invite",
    request_body = AcceptInviteRequest,
    responses(
        (status = 200, description = "Invitation accepted, session issued", body = SignInResponse),
        (status = 400, description = "Invalid token or missing password for new user"),
        (status = 410, description = "Invitation expired or workspace deleted"),
    ),
    tag = "auth",
)]
pub(crate) async fn accept_invite(
    State(auth_service): State<AuthServiceImpl>,
    headers: HeaderMap,
    Json(req): Json<AcceptInviteRequest>,
) -> ApiResult<impl IntoResponse> {
    let ip = extract_ip(&headers);
    let ua = extract_ua(&headers);
    let (access_token, refresh_token, user, ws_role, wid) = auth_service
        .accept_invite(
            &req.token,
            req.password.as_deref(),
            req.display_name.as_deref(),
            ip.as_deref(),
            ua.as_deref(),
        )
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
        setup_required: None,
    };

    Ok((
        StatusCode::OK,
        auth_cookies(&access_token, &refresh_token),
        Json(response),
    ))
}

/// POST /api/v2/auth/refresh — rotate refresh token and issue new access token.
/// Reads refresh token from cookie first, then request body.
#[utoipa::path(
    post,
    path = "/api/v2/auth/refresh",
    request_body = RefreshTokenRequest,
    responses(
        (status = 200, description = "New access token issued", body = RefreshTokenResponse),
        (status = 401, description = "Refresh token missing or invalid"),
    ),
    tag = "auth",
)]
pub(crate) async fn refresh_token(
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

    Ok((
        StatusCode::OK,
        auth_cookies(&access_token, &new_refresh_token),
        Json(response),
    ))
}

/// POST /api/v2/auth/verify — Rust-only extension (no Python equivalent).
/// Lightweight token introspection for SDK clients. Returns `valid: false`
/// instead of 401 when the token is expired or malformed.
#[utoipa::path(
    post,
    path = "/api/v2/auth/verify",
    request_body = VerifyTokenRequest,
    responses(
        (status = 200, description = "Token introspection result", body = VerifyTokenResponse),
    ),
    tag = "auth",
)]
pub(crate) async fn verify_token(
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

#[derive(Debug, Deserialize, ToSchema)]
pub(crate) struct LogoutRequest {
    refresh_token: Option<String>,
}

#[derive(Debug, Serialize, ToSchema)]
pub(crate) struct LogoutResponse {
    status: String,
}

/// POST /api/v2/auth/logout — revoke refresh token and clear auth cookies.
#[utoipa::path(
    post,
    path = "/api/v2/auth/logout",
    request_body = LogoutRequest,
    responses(
        (status = 200, description = "Logged out", body = LogoutResponse),
        (status = 401, description = "Unauthorized"),
    ),
    security(("cookie_auth" = [])),
    tag = "auth",
)]
pub(crate) async fn logout(
    _user: AuthUser,
    State(auth_service): State<AuthServiceImpl>,
    cookie: Option<TypedHeader<Cookie>>,
    body: Option<Json<LogoutRequest>>,
) -> ApiResult<impl IntoResponse> {
    if let Some(token) = resolve_refresh_token(&cookie, body.and_then(|Json(b)| b.refresh_token)) {
        auth_service.logout(&token).await?;
    }

    let response = LogoutResponse {
        status: "ok".to_string(),
    };

    Ok((StatusCode::OK, clear_auth_cookies(), Json(response)))
}
