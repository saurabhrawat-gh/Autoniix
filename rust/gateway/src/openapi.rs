//! OpenAPI schema generation for the Autoniix Gateway (Story A1 / IM-188).
//!
//! Every route handler in `routes/*.rs` is annotated with `#[utoipa::path]`
//! and every request/response type derives `ToSchema`. Those attributes feed
//! into [`ApiDoc`] which is exposed at:
//!
//! - Runtime: `GET /openapi.json` (mounted by [`routes`]).
//! - Build time: `cargo run -p gateway --bin openapi-dump` writes
//!   `rust/gateway/openapi.json` on disk (checked into the repo, regenerated
//!   in CI per Story A5).
//!
//! The harness contract validator (`rust/harness/src/contract/mod.rs`) uses
//! the on-disk `openapi.json` as its source of truth for the Rust API surface.

use axum::{routing::get, Json, Router};
use utoipa::{
    openapi::security::{ApiKey, ApiKeyValue, SecurityScheme},
    Modify, OpenApi,
};

// Only import modules that have been annotated so far.
// TODO(A1 remaining checkpoints): add channels, system, user, flags,
// notifications, workspace, voice, lookup_values as each is annotated.
use crate::routes::auth;

/// Injects the `cookie_auth` security scheme used by protected endpoints.
///
/// utoipa can't infer security requirements from the axum middleware layers,
/// so we register the scheme once here and reference it by name in each
/// handler's `security(("cookie_auth" = []))` attribute.
pub struct SecurityAddon;

impl Modify for SecurityAddon {
    fn modify(&self, openapi: &mut utoipa::openapi::OpenApi) {
        let components = openapi
            .components
            .as_mut()
            .expect("OpenAPI components should be present");
        components.add_security_scheme(
            "cookie_auth",
            SecurityScheme::ApiKey(ApiKey::Cookie(ApiKeyValue::new("access_token"))),
        );
    }
}

#[derive(OpenApi)]
#[openapi(
    info(
        title = "Autoniix Gateway API",
        version = "0.1.0",
        description = "Rust gateway API surface. This is the source of truth used by the harness contract validator (Story A1 / IM-188).",
        contact(
            name = "Autoniix",
            url = "https://autoniix.com",
        ),
    ),
    servers(
        (url = "http://localhost:8080", description = "Local dev"),
        (url = "https://dash.autoniix.com", description = "Production"),
    ),
    tags(
        (name = "auth", description = "Authentication and session management"),
        (name = "channels", description = "Channel CRUD, publishing, cadence"),
        (name = "system", description = "System-level admin endpoints"),
        (name = "users", description = "User management within a workspace"),
        (name = "flags", description = "Feature flags"),
        (name = "notifications", description = "In-app notifications"),
        (name = "workspace", description = "Workspace lifecycle"),
        (name = "voice", description = "Voice generation and providers"),
        (name = "lookup", description = "Static lookup value lists"),
    ),
    paths(
        // auth (14 unique handlers — /signup mounted as alias of /register)
        auth::auth_mode,
        auth::sign_in,
        auth::register,
        auth::refresh_token,
        auth::verify_token,
        auth::logout,
        auth::update_profile,
        auth::forgot_password,
        auth::reset_password,
        auth::mfa_setup,
        auth::mfa_verify,
        auth::mfa_challenge,
        auth::mfa_disable,
        auth::accept_invite,
    ),
    components(schemas(
        // auth
        auth::AuthModeResponse,
        auth::SignInRequest,
        auth::SignInResponse,
        auth::SignInUser,
        auth::RegisterRequest,
        auth::RegisterResponse,
        auth::RefreshTokenRequest,
        auth::RefreshTokenResponse,
        auth::VerifyTokenRequest,
        auth::VerifyTokenResponse,
        auth::LogoutRequest,
        auth::LogoutResponse,
        auth::UpdateProfileRequest,
        auth::UpdateProfileResponse,
        auth::ForgotRequest,
        auth::ResetRequest,
        auth::StatusResponse,
        auth::MfaSetupResponse,
        auth::MfaSetupData,
        auth::MfaVerifyRequest,
        auth::MfaChallengeRequest,
        auth::MfaDisableRequest,
        auth::AcceptInviteRequest,
    )),
    modifiers(&SecurityAddon),
)]
pub struct ApiDoc;

/// Route: `GET /openapi.json` — serves the live OpenAPI 3.1 document.
pub fn routes() -> Router {
    Router::new().route(
        "/openapi.json",
        get(|| async {
            Json(ApiDoc::openapi())
        }),
    )
}
