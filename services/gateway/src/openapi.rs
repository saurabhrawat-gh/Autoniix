//! OpenAPI schema generation for the Autoniix Gateway (Story A1 / IM-188).
//!
//! Every route handler in `routes/*.rs` is annotated with `#[utoipa::path]`
//! and every request/response type that is meaningful to expose derives
//! `ToSchema`. Those attributes feed into [`ApiDoc`] which is exposed at:
//!
//! - Runtime: `GET /openapi.json` (mounted by [`routes`]).
//! - Build time: `cargo run -p gateway --bin openapi-dump` writes
//!   `rust/gateway/openapi.json` on disk (checked into the repo, regenerated
//!   in CI per Story A5).
//!
//! The harness contract validator (`rust/harness/src/contract/mod.rs`) uses
//! the on-disk `openapi.json` as its source of truth for the Rust API surface.
//!
//! Note: For modules other than `auth`, we intentionally omit `ToSchema`
//! derives on request/response bodies in this first pass — the schemas are
//! still valid, they just document their payloads as `Object`. Follow-up
//! stories (A5) will tighten the schemas incrementally once the harness
//! is wired.

use axum::{routing::get, Json, Router};
use utoipa::{
    openapi::security::{ApiKey, ApiKeyValue, SecurityScheme},
    Modify, OpenApi,
};

use crate::routes::{
    auth, channels, flags, lookup_values, notifications, system, user, voice, workspace,
};

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
        // auth (14)
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
        // channels (39)
        channels::list_channels,
        channels::create_channel,
        channels::list_presets,
        channels::get_stats,
        channels::get_channel,
        channels::patch_channel,
        channels::delete_channel,
        channels::upsert_profile,
        channels::export_channel,
        channels::enable_channel,
        channels::disable_channel,
        channels::archive_channel,
        channels::restore_channel,
        channels::list_pillars,
        channels::add_pillar,
        channels::update_pillar,
        channels::delete_pillar,
        channels::list_topic_rules,
        channels::add_topic_rule,
        channels::delete_topic_rule,
        channels::list_references,
        channels::add_reference,
        channels::delete_reference,
        channels::list_memory,
        channels::add_memory,
        channels::list_drafts,
        channels::create_draft,
        channels::get_draft,
        channels::save_draft,
        channels::field_suggest,
        channels::resolve_config,
        channels::resolve_provider_chain,
        channels::proxy_trigger,
        channels::proxy_clone,
        channels::proxy_get_brand_kit,
        channels::proxy_put_brand_kit,
        channels::proxy_pause_job,
        channels::proxy_resume_job,
        channels::proxy_stop_job,
        // flags (2)
        flags::list_flags,
        flags::set_flag,
        // lookup_values (5)
        lookup_values::list_lookup_values,
        lookup_values::create_global_value,
        lookup_values::create_workspace_value,
        lookup_values::update_lookup_value,
        lookup_values::deactivate_lookup_value,
        // notifications (8)
        notifications::list_notifications,
        notifications::create_notification,
        notifications::mark_read,
        notifications::list_routes,
        notifications::create_route,
        notifications::update_route,
        notifications::delete_route,
        notifications::list_deliveries,
        // system (12)
        system::get_config,
        system::update_config,
        system::emergency_stop,
        system::emergency_resume,
        system::fleet_health,
        system::get_environment,
        system::set_environment,
        system::clean_slate,
        system::list_system_entity_settings,
        system::upsert_system_entity_setting,
        system::list_workspace_entity_settings,
        system::upsert_workspace_entity_setting,
        // user (8)
        user::get_current_user,
        user::list_sessions,
        user::revoke_session,
        user::list_users,
        user::transfer_superadmin,
        user::disable_user,
        user::enable_user,
        user::delete_user,
        // voice (2)
        voice::list_voices,
        voice::preview_voice,
        // workspace (3)
        workspace::delete_workspace,
        workspace::cancel_deletion,
        workspace::deletion_status,
    ),
    components(schemas(
        // auth schemas (only module with ToSchema in first pass)
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
    Router::new().route("/openapi.json", get(|| async { Json(ApiDoc::openapi()) }))
}
