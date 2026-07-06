"""Intelligence Observability — Track local-vs-LLM decisions and cost savings.

Every service calls `log_decision()` at each intelligence decision point.
The admin dashboard can then query aggregated stats.

Decision points:
- voice.emotion_mapping: local_prosody | local_keyword | llm_fallback
- thumbnail.qc: local_skip | vision_api
- direction.generation: script_v3_hint | llm_full
- assets.search: cache_hit | stock_search | dalle_fallback
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from typing import Any

import structlog

from core.db import get_pool

logger = structlog.get_logger()


async def log_decision(service_name: str, decision_point: str, path_taken: str,
                        content_id: str = "", channel_id: str = "",
                        local_score: float = 0, llm_cost_usd: float = 0,
                        cost_saved_usd: float = 0, latency_ms: int = 0,
                        model_version: str = "", metadata: dict = None) -> None:
    """Log an intelligence decision for observability."""
    try:
        pool = await get_pool()
        await pool.execute("""
            INSERT INTO intelligence_metrics (service_name, content_id, channel_id,
                decision_point, path_taken, local_score,
                llm_cost_usd, cost_saved_usd, latency_ms,
                model_version, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """, service_name, content_id, channel_id,
            decision_point, path_taken, local_score,
            llm_cost_usd, cost_saved_usd, latency_ms,
            model_version, json.dumps(metadata or {}))
    except Exception as e:
        logger.warning("observability.log_failed", error=str(e))


async def get_decision_summary(days: int = 30, service_name: str = "") -> dict:
    """Get aggregated decision stats for the dashboard."""
    pool = await get_pool()
    cutoff = datetime.utcnow() - timedelta(days=days)

    where = "WHERE created_at >= $1"
    params: list = [cutoff]
    if service_name:
        where += " AND service_name = $2"
        params.append(service_name)

    rows = await pool.fetch(f"""
        SELECT service_name, decision_point, path_taken,
               COUNT(*) as count,
               ROUND(AVG(local_score)::numeric, 3) as avg_local_score,
               ROUND(SUM(llm_cost_usd)::numeric, 4) as total_llm_cost,
               ROUND(SUM(cost_saved_usd)::numeric, 4) as total_saved,
               ROUND(AVG(latency_ms)::numeric, 0) as avg_latency_ms
        FROM intelligence_metrics
        {where}
        GROUP BY service_name, decision_point, path_taken
        ORDER BY service_name, decision_point, count DESC
    """, *params)

    summary: dict = {}
    for r in rows:
        svc = r["service_name"]
        dp = r["decision_point"]
        if svc not in summary:
            summary[svc] = {}
        if dp not in summary[svc]:
            summary[svc][dp] = {"paths": [], "total_decisions": 0}

        summary[svc][dp]["paths"].append({
            "path": r["path_taken"],
            "count": r["count"],
            "avg_local_score": float(r["avg_local_score"] or 0),
            "total_llm_cost": float(r["total_llm_cost"] or 0),
            "total_saved": float(r["total_saved"] or 0),
            "avg_latency_ms": int(r["avg_latency_ms"] or 0),
        })
        summary[svc][dp]["total_decisions"] += r["count"]

    for svc in summary.values():
        for dp in svc.values():
            total = dp["total_decisions"]
            local = sum(p["count"] for p in dp["paths"]
                        if "local" in p["path"] or "cache" in p["path"] or "skip" in p["path"]
                        or "hint" in p["path"])
            dp["local_rate_pct"] = round(local / total * 100, 1) if total else 0

    return summary


async def get_cost_savings(days: int = 30) -> dict:
    """Get total cost savings from intelligence layer."""
    pool = await get_pool()
    cutoff = datetime.utcnow() - timedelta(days=days)

    row = await pool.fetchrow("""
        SELECT COUNT(*) as total_decisions,
               ROUND(SUM(llm_cost_usd)::numeric, 4) as total_llm_cost,
               ROUND(SUM(cost_saved_usd)::numeric, 4) as total_saved,
               COUNT(CASE WHEN path_taken LIKE '%%local%%' OR path_taken LIKE '%%cache%%'
                          OR path_taken LIKE '%%skip%%' OR path_taken LIKE '%%hint%%'
                     THEN 1 END) as local_decisions,
               COUNT(CASE WHEN path_taken LIKE '%%llm%%' OR path_taken LIKE '%%api%%'
                          OR path_taken LIKE '%%vision%%'
                     THEN 1 END) as llm_decisions
        FROM intelligence_metrics
        WHERE created_at >= $1
    """, cutoff)

    total = row["total_decisions"] or 0
    local = row["local_decisions"] or 0
    llm = row["llm_decisions"] or 0

    return {
        "period_days": days,
        "total_decisions": total,
        "local_decisions": local,
        "llm_decisions": llm,
        "local_rate_pct": round(local / total * 100, 1) if total else 0,
        "total_llm_cost_usd": float(row["total_llm_cost"] or 0),
        "total_cost_saved_usd": float(row["total_saved"] or 0),
        "net_savings_usd": float((row["total_saved"] or 0) - (row["total_llm_cost"] or 0)),
    }


async def get_model_health_summary() -> list[dict]:
    """Get health status of all ML models."""
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT model_name, niche, training_rows, last_trained_at,
               accuracy_metric, drift_detected, drift_score,
               last_checked_at, status
        FROM model_health
        ORDER BY model_name, niche
    """)
    return [dict(r) for r in rows]


async def upsert_model_health(model_name: str, niche: str,
                                training_rows: int = 0,
                                accuracy_metric: float = 0,
                                drift_detected: bool = False,
                                drift_score: float = 0,
                                status: str = "trained") -> None:
    """Update model health record."""
    pool = await get_pool()
    await pool.execute("""
        INSERT INTO model_health (model_name, niche, training_rows,
            last_trained_at, accuracy_metric, drift_detected, drift_score,
            last_checked_at, status, updated_at)
        VALUES ($1, $2, $3, NOW(), $4, $5, $6, NOW(), $7, NOW())
        ON CONFLICT (model_name, niche) DO UPDATE SET
            training_rows = $3, last_trained_at = NOW(),
            accuracy_metric = $4, drift_detected = $5,
            drift_score = $6, last_checked_at = NOW(),
            status = $7, updated_at = NOW()
    """, model_name, niche, training_rows, accuracy_metric,
        drift_detected, drift_score, status)
