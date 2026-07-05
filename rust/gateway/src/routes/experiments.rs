//! Native Rust handlers for `/api/v2/experiments/**` (6 endpoints).
//! Previously proxied to Python BFF → admin:8009. All state is served
//! directly from the `experiments`, `experiment_assignments`, and
//! `experiment_outcomes` Postgres tables.

use axum::{
    extract::{Path, Query, State},
    http::HeaderMap,
    routing::{get, post},
    Json, Router,
};
use serde::Deserialize;
use serde_json::{json, Value};
use sqlx::PgPool;

use crate::{
    audit::{audit_log, AuditCtx},
    error::{ApiError, ApiResult},
    extractors::AuthUser,
};

pub fn routes(pool: PgPool) -> Router {
    Router::new()
        .route("/api/v2/experiments",                get(list_experiments).post(create_experiment))
        .route("/api/v2/experiments/:name/activate", post(activate))
        .route("/api/v2/experiments/:name/pause",    post(pause))
        .route("/api/v2/experiments/:name/complete", post(complete))
        .route("/api/v2/experiments/:name/results",  get(results))
        .with_state(pool)
}

// ─── helpers ──────────────────────────────────────────────────────────────────

fn require_write(actor: &crate::middleware::Principal) -> ApiResult<()> {
    if ["owner", "member"].contains(&actor.role.as_str()) || actor.global_role == "superadmin" {
        Ok(())
    } else {
        Err(ApiError::Forbidden)
    }
}

/// Complementary error function — Numerical Recipes §6.2 polynomial (max error 1.2e-7).
fn erfc_approx(x: f64) -> f64 {
    let t = 1.0 / (1.0 + 0.5 * x.abs());
    let inner = -x * x - 1.265_512_23
        + t * (1.000_023_68
        + t * (0.374_091_96
        + t * (0.096_784_18
        + t * (-0.186_288_06
        + t * (0.278_868_07
        + t * (-1.135_203_98
        + t * (1.488_515_87
        + t * (-0.822_152_23
        + t * 0.170_872_94))))))));
    t * inner.exp()
}

/// Welch t-test: returns (t_stat, df, two_tailed_p). Returns None if < 5 samples.
fn welch_t_p(a: &[f64], b: &[f64]) -> Option<(f64, f64, f64)> {
    if a.len() < 5 || b.len() < 5 { return None; }
    let mean = |v: &[f64]| v.iter().sum::<f64>() / v.len() as f64;
    let var  = |v: &[f64], m: f64| v.iter().map(|x| (x - m).powi(2)).sum::<f64>() / (v.len() as f64 - 1.0);
    let (na, nb) = (a.len() as f64, b.len() as f64);
    let (ma, mb) = (mean(a), mean(b));
    let (va, vb) = (var(a, ma), var(b, mb));
    let se = (va / na + vb / nb).sqrt();
    if se == 0.0 { return None; }
    let t = (ma - mb) / se;
    let df_num = (va / na + vb / nb).powi(2);
    let df_den = (va / na).powi(2) / (na - 1.0) + (vb / nb).powi(2) / (nb - 1.0);
    let df = if df_den > 0.0 { df_num / df_den } else { 1.0 };
    let p = erfc_approx(t.abs() / std::f64::consts::SQRT_2);
    Some((t, df, p))
}

// ── GET /experiments ───────────────────────────────────────────────────────────

#[derive(Deserialize)]
struct ListQ { #[serde(default)] status: String }

async fn list_experiments(
    AuthUser(_p): AuthUser,
    State(pool):  State<PgPool>,
    Query(q):     Query<ListQ>,
) -> ApiResult<Json<Value>> {
    let rows: Vec<Value> = if q.status.is_empty() {
        sqlx::query!(
            r#"SELECT experiment_name, description, status, traffic_pct, target_metric,
                      variants, winning_variant, started_at, ended_at, created_at, updated_at
               FROM experiments ORDER BY created_at DESC"#,
        )
        .fetch_all(&pool).await.map_err(ApiError::Database)?
        .into_iter().map(|r| json!({
            "name": r.experiment_name, "description": r.description, "status": r.status,
            "traffic_pct": r.traffic_pct, "target_metric": r.target_metric,
            "variants": r.variants, "winning_variant": r.winning_variant,
            "started_at": r.started_at, "ended_at": r.ended_at,
            "created_at": r.created_at, "updated_at": r.updated_at,
        })).collect()
    } else {
        sqlx::query!(
            r#"SELECT experiment_name, description, status, traffic_pct, target_metric,
                      variants, winning_variant, started_at, ended_at, created_at, updated_at
               FROM experiments WHERE status = $1 ORDER BY created_at DESC"#,
            q.status,
        )
        .fetch_all(&pool).await.map_err(ApiError::Database)?
        .into_iter().map(|r| json!({
            "name": r.experiment_name, "description": r.description, "status": r.status,
            "traffic_pct": r.traffic_pct, "target_metric": r.target_metric,
            "variants": r.variants, "winning_variant": r.winning_variant,
            "started_at": r.started_at, "ended_at": r.ended_at,
            "created_at": r.created_at, "updated_at": r.updated_at,
        })).collect()
    };

    Ok(Json(json!({ "data": rows })))
}

// ── POST /experiments ──────────────────────────────────────────────────────────

#[derive(Deserialize)]
struct CreateIn {
    name: String,
    #[serde(default)] description: String,
    #[serde(default)] variants: Vec<Value>,
    #[serde(default = "default_traffic")] traffic_pct: f64,
    #[serde(default = "default_metric")]  target_metric: String,
}
fn default_traffic() -> f64  { 100.0 }
fn default_metric()  -> String { "views".into() }

async fn create_experiment(
    AuthUser(actor): AuthUser,
    State(pool):     State<PgPool>,
    headers:         HeaderMap,
    Json(body):      Json<CreateIn>,
) -> ApiResult<Json<Value>> {
    require_write(&actor)?;
    let variants = serde_json::to_value(&body.variants).unwrap_or(json!([]));
    sqlx::query!(
        r#"INSERT INTO experiments (experiment_name, description, variants, traffic_pct, target_metric, status)
           VALUES ($1, $2, $3, $4, $5, 'draft')
           ON CONFLICT (experiment_name) DO UPDATE SET
               description=$2, variants=$3, traffic_pct=$4, target_metric=$5, updated_at=NOW()"#,
        body.name, body.description, variants, body.traffic_pct as f32, body.target_metric,
    ).execute(&pool).await.map_err(ApiError::Database)?;

    audit_log(&pool, AuditCtx {
        actor: &actor, action: "experiment.create", target_type: "experiment",
        target_id: Some(body.name.clone()), before: None,
        after: Some(json!({ "name": &body.name, "status": "draft" })),
        headers: Some(&headers),
    }).await;

    Ok(Json(json!({ "status": "ok", "data": { "name": body.name, "status": "draft" } })))
}

// ── POST /experiments/:name/activate ──────────────────────────────────────────

async fn activate(
    AuthUser(actor): AuthUser,
    State(pool):     State<PgPool>,
    headers:         HeaderMap,
    Path(name):      Path<String>,
) -> ApiResult<Json<Value>> {
    require_write(&actor)?;
    sqlx::query!(
        "UPDATE experiments SET status='active', started_at=NOW(), updated_at=NOW() WHERE experiment_name=$1",
        name,
    ).execute(&pool).await.map_err(ApiError::Database)?;
    audit_log(&pool, AuditCtx {
        actor: &actor, action: "experiment.activate", target_type: "experiment",
        target_id: Some(name.clone()), before: None, after: None, headers: Some(&headers),
    }).await;
    Ok(Json(json!({ "status": "ok", "data": { "name": name, "status": "active" } })))
}

// ── POST /experiments/:name/pause ─────────────────────────────────────────────

async fn pause(
    AuthUser(actor): AuthUser,
    State(pool):     State<PgPool>,
    headers:         HeaderMap,
    Path(name):      Path<String>,
) -> ApiResult<Json<Value>> {
    require_write(&actor)?;
    sqlx::query!(
        "UPDATE experiments SET status='paused', updated_at=NOW() WHERE experiment_name=$1",
        name,
    ).execute(&pool).await.map_err(ApiError::Database)?;
    audit_log(&pool, AuditCtx {
        actor: &actor, action: "experiment.pause", target_type: "experiment",
        target_id: Some(name.clone()), before: None, after: None, headers: Some(&headers),
    }).await;
    Ok(Json(json!({ "status": "ok", "data": { "name": name, "status": "paused" } })))
}

// ── POST /experiments/:name/complete ──────────────────────────────────────────

#[derive(Deserialize)]
struct WinnerQ { #[serde(default)] winner: String }

async fn complete(
    AuthUser(actor): AuthUser,
    State(pool):     State<PgPool>,
    headers:         HeaderMap,
    Path(name):      Path<String>,
    Query(q):        Query<WinnerQ>,
) -> ApiResult<Json<Value>> {
    require_write(&actor)?;
    sqlx::query!(
        "UPDATE experiments SET status='completed', ended_at=NOW(), winning_variant=$2, updated_at=NOW() WHERE experiment_name=$1",
        name, q.winner,
    ).execute(&pool).await.map_err(ApiError::Database)?;
    audit_log(&pool, AuditCtx {
        actor: &actor, action: "experiment.complete", target_type: "experiment",
        target_id: Some(name.clone()), before: None,
        after: Some(json!({ "winner": &q.winner })), headers: Some(&headers),
    }).await;
    Ok(Json(json!({ "status": "ok", "data": { "name": name, "status": "completed", "winner": q.winner } })))
}

// ── GET /experiments/:name/results ────────────────────────────────────────────

async fn results(
    AuthUser(_p): AuthUser,
    State(pool):  State<PgPool>,
    Path(name):   Path<String>,
) -> ApiResult<Json<Value>> {
    let exp = sqlx::query!(
        "SELECT experiment_name, target_metric, status FROM experiments WHERE experiment_name=$1",
        name,
    )
    .fetch_optional(&pool).await.map_err(ApiError::Database)?
    .ok_or_else(|| ApiError::NotFound("Experiment not found".into()))?;

    let outcomes = sqlx::query!(
        "SELECT variant_name, metrics FROM experiment_outcomes WHERE experiment_name=$1",
        name,
    )
    .fetch_all(&pool).await.map_err(ApiError::Database)?;

    let total = outcomes.len();
    if total < 10 {
        return Ok(Json(json!({
            "experiment": name, "status": "insufficient_data",
            "total_samples": total, "min_required": 10,
        })));
    }

    // Collect per-variant metric values
    let mut vdata: std::collections::HashMap<String, Vec<f64>> = Default::default();
    let metric: &str = exp.target_metric.as_deref().unwrap_or("views");
    for row in &outcomes {
        let val = row.metrics.get(metric)
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        vdata.entry(row.variant_name.clone()).or_default().push(val);
    }

    let mean = |v: &[f64]| v.iter().sum::<f64>() / v.len() as f64;
    let std_d = |v: &[f64], m: f64| (v.iter().map(|x| (x - m).powi(2)).sum::<f64>() / v.len().max(1) as f64).sqrt();
    let median = |v: &mut Vec<f64>| {
        v.sort_by(|a, b| a.partial_cmp(b).unwrap());
        if v.len() % 2 == 0 { (v[v.len()/2-1] + v[v.len()/2]) / 2.0 } else { v[v.len()/2] }
    };

    let mut vstats: std::collections::HashMap<String, Value> = Default::default();
    for (vn, values) in &vdata {
        let m = mean(values);
        let mut sv = values.clone();
        let med = median(&mut sv);
        vstats.insert(vn.clone(), json!({
            "count": values.len(),
            "mean":   (m * 1e6).round() / 1e6,
            "std":    (std_d(values, m) * 1e6).round() / 1e6,
            "median": (med * 1e6).round() / 1e6,
            "min": values.iter().cloned().fold(f64::INFINITY, f64::min),
            "max": values.iter().cloned().fold(f64::NEG_INFINITY, f64::max),
        }));
    }

    // Statistical significance (Welch t-test on first two variants)
    let mut significance = json!({});
    let names: Vec<&String> = vdata.keys().collect();
    if names.len() >= 2 {
        let a = &vdata[names[0]]; let b = &vdata[names[1]];
        if let Some((t, df, p)) = welch_t_p(a, b) {
            let (ma, mb) = (mean(a), mean(b));
            significance = json!({
                "test": "welch_t_test",
                "t_statistic": (t * 1e4).round() / 1e4,
                "degrees_of_freedom": (df * 10.0).round() / 10.0,
                "p_value": (p * 1e6).round() / 1e6,
                "significant_at_005": p < 0.05,
                "significant_at_001": p < 0.01,
                "effect_size": ((ma - mb) * 1e6).round() / 1e6,
                "relative_improvement": if ma != 0.0 { ((mb - ma) / ma * 100.0 * 100.0).round() / 100.0 } else { 0.0 },
            });
        }
    }

    let winner = vstats.iter()
        .max_by(|a, b| {
            let ma = a.1.get("mean").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let mb = b.1.get("mean").and_then(|v| v.as_f64()).unwrap_or(0.0);
            ma.partial_cmp(&mb).unwrap_or(std::cmp::Ordering::Equal)
        })
        .map(|(k, _)| k.clone())
        .unwrap_or_default();

    Ok(Json(json!({
        "experiment": name, "target_metric": exp.target_metric,
        "total_samples": total, "variant_stats": vstats,
        "significance": significance, "recommended_winner": winner,
        "status": exp.status,
    })))
}
