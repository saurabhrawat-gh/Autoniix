//! Criterion benchmarks for Rust gateway auth endpoints.
//!
//! Per HARNESS-ENGINEERING-PLAN.md Week 2 Day 3-4.
//!
//! Targets (p95):
//!   signup  < 30ms
//!   signin  < 25ms
//!   refresh < 10ms
//!   /me     < 5ms
//!
//! Run with:
//!   TEST_DATABASE_URL=postgresql://... cargo bench -p gateway

use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion};
use serde_json::json;
use std::time::Duration;
use tokio::runtime::Runtime;

// ── Shared setup ─────────────────────────────────────────────────────────────

struct BenchState {
    base_url: String,
    client: reqwest::Client,
    seeded_email: String,
    seeded_password: String,
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

    // Seed a user for signin/refresh/me benchmarks
    let signup_resp: serde_json::Value = client
        .post(format!("{base_url}/api/v2/auth/signup"))
        .json(&json!({
            "email": email,
            "password": password,
            "display_name": "Bench User",
            "workspace_name": "Bench Workspace"
        }))
        .send()
        .await
        .expect("bench seed signup failed")
        .json()
        .await
        .unwrap();

    let access_token = signup_resp["access_token"]
        .as_str()
        .unwrap_or("")
        .to_string();
    let refresh_token = signup_resp["refresh_token"]
        .as_str()
        .unwrap_or("")
        .to_string();

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

fn bench_signup(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();
    let state = rt.block_on(setup());

    let mut group = c.benchmark_group("auth");
    group.measurement_time(Duration::from_secs(10));
    group.sample_size(20);

    group.bench_function("signup", |b| {
        b.to_async(&rt).iter(|| async {
            let ts = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let email = format!("bench-{ts}@bench.test");

            state
                .client
                .post(format!("{}/api/v2/auth/signup", state.base_url))
                .json(&json!({
                    "email": email,
                    "password": "BenchPassword123!",
                    "display_name": "Bench",
                    "workspace_name": "Bench Workspace"
                }))
                .send()
                .await
                .expect("bench signup failed");
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

criterion_group!(benches, bench_signup, bench_signin, bench_me, bench_verify);
criterion_main!(benches);
