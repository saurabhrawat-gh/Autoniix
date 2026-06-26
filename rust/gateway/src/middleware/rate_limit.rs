/// IP-based sliding-window rate limiter for sensitive public endpoints.
///
/// Each IP is allowed at most `MAX_ATTEMPTS` requests within a `WINDOW` period.
/// On breach the middleware returns `429 Too Many Requests` with a `Retry-After`
/// header indicating how many seconds remain before the window resets.
///
/// Uses an in-memory `HashMap` protected by a `std::sync::Mutex`.  The lock is
/// held only for the duration of the bookkeeping (< 1 µs) so there is no
/// meaningful contention even under load.
use std::{
    collections::HashMap,
    sync::{Arc, Mutex},
    time::{Duration, Instant},
};

use axum::{
    body::Body,
    extract::{Request, State},
    http::{header, HeaderValue, StatusCode},
    middleware::Next,
    response::Response,
};

use super::Principal;

const MAX_ATTEMPTS: usize = 5;
const WINDOW: Duration = Duration::from_secs(15 * 60); // 15 minutes

const DEFAULT_WORKSPACE_RPM: usize = 100;
const WORKSPACE_WINDOW: Duration = Duration::from_secs(60);

#[derive(Clone, Default)]
pub struct InviteRateLimiter {
    inner: Arc<Mutex<HashMap<String, Vec<Instant>>>>,
}

impl InviteRateLimiter {
    pub fn new() -> Self {
        Self::default()
    }

    /// Record one attempt for `ip`.
    ///
    /// Returns `Ok(())` when allowed, or `Err(retry_after_secs)` when the IP
    /// has exhausted its quota for the current window.
    pub fn check_and_record(&self, ip: &str) -> Result<(), u64> {
        let mut map = self.inner.lock().expect("rate_limit lock poisoned");
        let now = Instant::now();

        let attempts = map.entry(ip.to_string()).or_default();

        // Prune timestamps that have fallen outside the sliding window.
        attempts.retain(|t| now.duration_since(*t) < WINDOW);

        if attempts.len() >= MAX_ATTEMPTS {
            let oldest = attempts[0];
            let elapsed = now.duration_since(oldest).as_secs();
            let retry_after = WINDOW.as_secs().saturating_sub(elapsed).max(1);
            return Err(retry_after);
        }

        attempts.push(now);
        Ok(())
    }
}

// ── Workspace-level rate limiter ───────────────────────────────────────────────
//
// Keys on `workspace_id` from the JWT `Principal`.  Applied to all authenticated
// routes after `require_auth_middleware` has populated the extension.

#[derive(Clone)]
pub struct WorkspaceRateLimiter {
    inner: Arc<Mutex<HashMap<i64, Vec<Instant>>>>,
    max_rpm: usize,
}

impl Default for WorkspaceRateLimiter {
    fn default() -> Self {
        Self::new()
    }
}

impl WorkspaceRateLimiter {
    pub fn new() -> Self {
        let rpm = std::env::var("WORKSPACE_RATE_LIMIT_RPM")
            .ok()
            .and_then(|v| v.parse::<usize>().ok())
            .unwrap_or(DEFAULT_WORKSPACE_RPM);
        Self {
            inner: Arc::new(Mutex::new(HashMap::new())),
            max_rpm: rpm,
        }
    }

    #[allow(dead_code)]
    pub fn with_rpm(rpm: usize) -> Self {
        Self {
            inner: Arc::new(Mutex::new(HashMap::new())),
            max_rpm: rpm,
        }
    }

    pub fn check_and_record(&self, workspace_id: i64) -> Result<(), u64> {
        let mut map = self.inner.lock().expect("workspace rate_limit lock poisoned");
        let now = Instant::now();

        let attempts = map.entry(workspace_id).or_default();
        attempts.retain(|t| now.duration_since(*t) < WORKSPACE_WINDOW);

        if attempts.len() >= self.max_rpm {
            let oldest = attempts[0];
            let elapsed = now.duration_since(oldest).as_secs();
            let retry_after = WORKSPACE_WINDOW.as_secs().saturating_sub(elapsed).max(1);
            return Err(retry_after);
        }

        attempts.push(now);
        Ok(())
    }
}

/// Axum middleware that enforces `WorkspaceRateLimiter` on authenticated routes.
///
/// Must be applied **after** `require_auth_middleware` so that `Principal` is
/// available in the request extensions.
pub async fn workspace_rate_limit(
    State(limiter): State<WorkspaceRateLimiter>,
    request: Request,
    next: Next,
) -> Response {
    let workspace_id = request
        .extensions()
        .get::<Principal>()
        .map(|p| p.wid)
        .unwrap_or(-1);

    match limiter.check_and_record(workspace_id) {
        Ok(()) => next.run(request).await,
        Err(retry_after) => {
            let body = format!(
                r#"{{"error":"rate_limited","message":"Workspace rate limit exceeded. Retry after {} seconds.","retry_after":{}}}"#,
                retry_after, retry_after
            );
            let mut resp = Response::new(Body::from(body));
            *resp.status_mut() = StatusCode::TOO_MANY_REQUESTS;
            resp.headers_mut().insert(
                header::CONTENT_TYPE,
                HeaderValue::from_static("application/json"),
            );
            if let Ok(v) = HeaderValue::from_str(&retry_after.to_string()) {
                resp.headers_mut().insert(header::RETRY_AFTER, v);
            }
            resp
        }
    }
}

/// Extract the best-effort client IP.  Prefers `X-Real-IP` (set by Traefik /
/// Nginx reverse proxies) then the first token of `X-Forwarded-For`.
fn client_ip(request: &Request) -> String {
    request
        .headers()
        .get("x-real-ip")
        .or_else(|| request.headers().get("x-forwarded-for"))
        .and_then(|v| v.to_str().ok())
        .map(|s| s.split(',').next().unwrap_or(s).trim().to_string())
        .unwrap_or_else(|| "unknown".to_string())
}

/// Axum middleware that enforces `InviteRateLimiter` on the route it wraps.
///
/// Apply it per-route (not globally) so only sensitive endpoints are gated:
/// ```text
/// .route(
///     "/api/v2/auth/accept-invite",
///     post(accept_invite).layer(
///         axum::middleware::from_fn_with_state(InviteRateLimiter::new(), invite_rate_limit),
///     ),
/// )
/// ```
pub async fn invite_rate_limit(
    State(limiter): State<InviteRateLimiter>,
    request: Request,
    next: Next,
) -> Response {
    let ip = client_ip(&request);

    match limiter.check_and_record(&ip) {
        Ok(()) => next.run(request).await,
        Err(retry_after) => {
            let body = format!(
                r#"{{"error":"Too many invite attempts from this address. Retry after {} seconds."}}"#,
                retry_after
            );
            let mut resp = Response::new(Body::from(body));
            *resp.status_mut() = StatusCode::TOO_MANY_REQUESTS;
            resp.headers_mut().insert(
                header::CONTENT_TYPE,
                HeaderValue::from_static("application/json"),
            );
            if let Ok(v) = HeaderValue::from_str(&retry_after.to_string()) {
                resp.headers_mut().insert(header::RETRY_AFTER, v);
            }
            resp
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn allows_up_to_max_attempts() {
        let limiter = InviteRateLimiter::new();
        for _ in 0..MAX_ATTEMPTS {
            assert!(limiter.check_and_record("1.2.3.4").is_ok());
        }
    }

    #[test]
    fn blocks_on_exceeded_attempts() {
        let limiter = InviteRateLimiter::new();
        for _ in 0..MAX_ATTEMPTS {
            let _ = limiter.check_and_record("10.0.0.1");
        }
        let result = limiter.check_and_record("10.0.0.1");
        assert!(result.is_err(), "should be rate-limited after MAX_ATTEMPTS");
        let retry_after = result.unwrap_err();
        assert!(retry_after > 0 && retry_after <= WINDOW.as_secs());
    }

    #[test]
    fn different_ips_are_tracked_independently() {
        let limiter = InviteRateLimiter::new();
        for _ in 0..MAX_ATTEMPTS {
            let _ = limiter.check_and_record("192.168.1.1");
        }
        assert!(
            limiter.check_and_record("192.168.1.2").is_ok(),
            "different IP must not be affected"
        );
    }

    // ── WorkspaceRateLimiter tests ──────────────────────────────────────────

    #[test]
    fn workspace_allows_up_to_rpm() {
        let limiter = WorkspaceRateLimiter::with_rpm(5);
        for _ in 0..5 {
            assert!(limiter.check_and_record(42).is_ok());
        }
    }

    #[test]
    fn workspace_blocks_on_exceeded() {
        let limiter = WorkspaceRateLimiter::with_rpm(3);
        for _ in 0..3 {
            let _ = limiter.check_and_record(7);
        }
        let result = limiter.check_and_record(7);
        assert!(result.is_err());
        let retry_after = result.unwrap_err();
        assert!(retry_after > 0 && retry_after <= WORKSPACE_WINDOW.as_secs());
    }

    #[test]
    fn workspace_different_ids_tracked_independently() {
        let limiter = WorkspaceRateLimiter::with_rpm(2);
        for _ in 0..2 {
            let _ = limiter.check_and_record(1);
        }
        assert!(
            limiter.check_and_record(2).is_ok(),
            "different workspace must not be affected"
        );
    }
}
