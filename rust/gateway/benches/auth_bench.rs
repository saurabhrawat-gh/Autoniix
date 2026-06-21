//! Criterion benchmarks for Rust gateway auth endpoints.
//!
//! Per HARNESS-ENGINEERING-PLAN.md Week 2 Day 3-4.
//!
//! Targets (p95, see Plan §11 Production Rollout Strategy):
//!   register < 50ms  (Argon2 + 2 DB transactions; bound by hashing)
//!   signin   < 25ms  (Argon2 verify + session insert)
//!   refresh  < 10ms  (sha256 lookup + session rotate)
//!   /me      < 5ms   (JWT verify + 1 DB lookup)
//!   verify   < 5ms   (JWT verify only, no DB)
//!
//! Run with:
//!   TEST_DATABASE_URL=postgresql://... cargo bench -p gateway
//!
//! Compare to Python baseline: `make bench-python-auth` (TODO).

use criterion::{criterion_group, criterion_main, Criterion};
use serde_json::json;
use std::time::Duration;
use tokio::runtime::Runtime;

// ── Shared setup ─────────────────────────────────────────────────────────────

struct BenchState {
    base_url: String,
    client: reqwest::Client,
    seeded_email: String,
    seeded_password: String,
    #[allow(dead_code)]
    seeded_refresh_token: String,
    seeded_access_token: String,
}

async fn setup() -> BenchState {
    let database_url = std::env::var("TEST_DATABASE_URL")
        .unwrap_or_else(|_| "postgresql://localhost/autoniix_test".to_string());

    let pool = sqlx::postgres::PgPoolOptions::new()
        .max_connections(10)
        .connect(&database_url)
        .await
        .expect("bench: failed to connect to test DB");

    let app = gateway::create_app(pool, "bench-jwt-secret-key-long-enough".to_string()).await;

    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    let base_url = format!("http://{addr}");

    tokio::spawn(async move {
        axum::serve(listener, app).await.ok();
    });

    let client = reqwest::Client::new();
    let ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let email = format!("bench-seed-{ts}@bench.test");
    let password = "BenchPassword123!";

    // Seed a user via /register (#350: no tokens returned), then /signin to
    // get tokens for the signin-dependent benchmarks (/me, refresh, verify).
    let register_resp = client
        .post(format!("{base_url}/api/v2/auth/register"))
        .json(&json!({
            "email": email,
            "password": password,
            "display_name": "Bench User",
            "workspace_name": "Bench Workspace"
        }))
        .send()
        .await
        .expect("bench seed register failed");
    assert!(
        register_resp.status().is_success(),
        "bench seed register returned {}",
        register_resp.status()
    );

    let signin_resp: serde_json::Value = client
        .post(format!("{base_url}/api/v2/auth/signin"))
        .json(&json!({ "email": email, "password": password }))
        .send()
        .await
        .expect("bench seed signin failed")
        .json()
        .await
        .expect("bench seed signin response is not JSON");

    let access_token = signin_resp["access_token"]
        .as_str()
        .expect("bench seed signin missing access_token")
        .to_string();
    // Refresh token is returned via HttpOnly cookie; for the bench we fetch
    // it from the Set-Cookie header on a second signin call.
    let signin_for_cookie = client
        .post(format!("{base_url}/api/v2/auth/signin"))
        .json(&json!({ "email": email, "password": password }))
        .send()
        .await
        .expect("bench seed signin (cookie) failed");
    let refresh_token = signin_for_cookie
        .headers()
        .get_all("set-cookie")
        .iter()
        .filter_map(|v| v.to_str().ok())
        .find_map(|s| {
            s.split(';')
                .next()
                .and_then(|kv| kv.trim().strip_prefix("refresh_token="))
                .map(|s| s.to_string())
        })
        .expect("bench seed: refresh_token cookie missing from signin response");

    BenchState {
        base_url,
        client,
        seeded_email: email,
        seeded_password: password.to_string(),
        seeded_refresh_token: refresh_token,
        seeded_access_token: access_token,
    }
}

// ── Benchmarks ────────────────────────────────────────────────────────────────

fn bench_register(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();
    let state = rt.block_on(setup());

    let mut group = c.benchmark_group("auth");
    group.measurement_time(Duration::from_secs(10));
    group.sample_size(20);

    group.bench_function("register", |b| {
        b.to_async(&rt).iter(|| async {
            let ts = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let email = format!("bench-{ts}@bench.test");

            state
                .client
                .post(format!("{}/api/v2/auth/register", state.base_url))
                .json(&json!({
                    "email": email,
                    "password": "BenchPassword123!",
                    "display_name": "Bench",
                    "workspace_name": "Bench Workspace"
                }))
                .send()
                .await
                .expect("bench register failed");
        });
    });

    group.finish();
}

fn bench_signin(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();
    let state = rt.block_on(setup());

    let mut group = c.benchmark_group("auth");
    group.measurement_time(Duration::from_secs(10));
    group.sample_size(30);

    group.bench_function("signin", |b| {
        b.to_async(&rt).iter(|| async {
            state
                .client
                .post(format!("{}/api/v2/auth/signin", state.base_url))
                .json(&json!({
                    "email": state.seeded_email,
                    "password": state.seeded_password
                }))
                .send()
                .await
                .expect("bench signin failed");
        });
    });

    group.finish();
}

fn bench_me(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();
    let state = rt.block_on(setup());

    let mut group = c.benchmark_group("auth");
    group.measurement_time(Duration::from_secs(10));
    group.sample_size(50);

    group.bench_function("me", |b| {
        b.to_async(&rt).iter(|| async {
            state
                .client
                .get(format!("{}/api/v2/me", state.base_url))
                .bearer_auth(&state.seeded_access_token)
                .send()
                .await
                .expect("bench /me failed");
        });
    });

    group.finish();
}

fn bench_verify(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();
    let state = rt.block_on(setup());

    let mut group = c.benchmark_group("auth");
    group.measurement_time(Duration::from_secs(10));
    group.sample_size(50);

    group.bench_function("verify_token", |b| {
        b.to_async(&rt).iter(|| async {
            state
                .client
                .post(format!("{}/api/v2/auth/verify", state.base_url))
                .json(&json!({ "token": state.seeded_access_token }))
                .send()
                .await
                .expect("bench verify failed");
        });
    });

    group.finish();
}

fn bench_refresh(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();
    let state = rt.block_on(setup());

    let mut group = c.benchmark_group("auth");
    group.measurement_time(Duration::from_secs(10));
    group.sample_size(30);

    // We need a fresh refresh token per iteration because /refresh rotates
    // (revokes) the previous one. We sign in once per iteration to mint one
    // — this is the closest we can get without modeling the actual refresh
    // request in isolation. The signin cost dominates and is reported in
    // bench_signin; this measures the refresh roundtrip itself.
    group.bench_function("refresh", |b| {
        b.to_async(&rt).iter(|| async {
            // Mint a fresh refresh token by signing in
            let signin = state
                .client
                .post(format!("{}/api/v2/auth/signin", state.base_url))
                .json(&json!({
                    "email": state.seeded_email,
                    "password": state.seeded_password
                }))
                .send()
                .await
                .expect("bench refresh: signin failed");
            let refresh = signin
                .headers()
                .get_all("set-cookie")
                .iter()
                .filter_map(|v| v.to_str().ok())
                .find_map(|s| {
                    s.split(';')
                        .next()
                        .and_then(|kv| kv.trim().strip_prefix("refresh_token="))
                        .map(|s| s.to_string())
                })
                .expect("bench refresh: missing refresh cookie");

            state
                .client
                .post(format!("{}/api/v2/auth/refresh", state.base_url))
                .json(&json!({ "refresh_token": refresh }))
                .send()
                .await
                .expect("bench refresh failed");
        });
    });

    group.finish();
}

criterion_group!(
    benches,
    bench_register,
    bench_signin,
    bench_refresh,
    bench_me,
    bench_verify
);
criterion_main!(benches);
