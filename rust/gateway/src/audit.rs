//! Best-effort audit logging into `audit_log_v2`.
//!
//! Mirrors Python `src/services/dashboard/v2/_deps.py::audit`. The Python
//! version is wrapped in a try/except and never raises; we keep the same
//! contract here so a misconfigured audit table can't break the actual
//! business logic of an endpoint.
//!
//! Use:
//! ```ignore
//! use crate::audit::{audit_log, AuditCtx};
//! audit_log(&pool, AuditCtx {
//!     actor: &principal,
//!     action: "user.disable",
//!     target_type: "user",
//!     target_id: Some(user_id.to_string()),
//!     ..Default::default()
//! }).await;
//! ```
use axum::http::HeaderMap;
use serde_json::Value;
use sqlx::PgPool;

use crate::middleware::Principal;

/// Context for one audit row. `actor` is required; the rest mirror Python's
/// keyword-only signature so callers explicitly opt in to whatever payload
/// makes sense for their endpoint.
pub struct AuditCtx<'a> {
    pub actor: &'a Principal,
    pub action: &'a str,
    pub target_type: &'a str,
    pub target_id: Option<String>,
    pub before: Option<Value>,
    pub after: Option<Value>,
    pub headers: Option<&'a HeaderMap>,
}

impl<'a> AuditCtx<'a> {
    pub fn new(actor: &'a Principal, action: &'a str, target_type: &'a str) -> Self {
        Self {
            actor,
            action,
            target_type,
            target_id: None,
            before: None,
            after: None,
            headers: None,
        }
    }
}

/// Append a single audit row. Failures are logged at warn-level and swallowed
/// — never raised — so a write error to `audit_log_v2` can't bubble up and
/// turn a successful 200 into a 500.
pub async fn audit_log(pool: &PgPool, ctx: AuditCtx<'_>) {
    let actor_user_id: Option<i64> = ctx.actor.user_id.parse().ok();
    let actor_label = if ctx.actor.email.is_empty() {
        "unknown".to_string()
    } else {
        ctx.actor.email.clone()
    };

    let source = match ctx.headers.and_then(|h| h.get("x-source")) {
        Some(v) if v.to_str().map(|s| s == "ui").unwrap_or(false) => "ui",
        _ => "api",
    };

    let request_id = ctx
        .headers
        .and_then(|h| h.get("x-request-id"))
        .and_then(|v| v.to_str().ok())
        .map(str::to_owned);
    let ip: Option<String> = None;
    let user_agent = ctx
        .headers
        .and_then(|h| h.get("user-agent"))
        .and_then(|v| v.to_str().ok())
        .map(str::to_owned);

    let res = sqlx::query(
        r#"INSERT INTO audit_log_v2
               (actor_user_id, actor_label, action, target_type, target_id,
                before, after, source, request_id, ip, user_agent)
           VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, $9, $10, $11)"#,
    )
    .bind(actor_user_id)
    .bind(actor_label)
    .bind(ctx.action)
    .bind(ctx.target_type)
    .bind(ctx.target_id)
    .bind(ctx.before)
    .bind(ctx.after)
    .bind(source)
    .bind(request_id)
    .bind(ip)
    .bind(user_agent)
    .execute(pool)
    .await;

    if let Err(e) = res {
        tracing::warn!(
            action = ctx.action,
            target_type = ctx.target_type,
            error = %e,
            "audit.write_failed"
        );
    }
}
