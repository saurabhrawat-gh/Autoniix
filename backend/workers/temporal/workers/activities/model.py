"""Activities for the ModelMaintenanceWorkflow.

These are called by the Temporal workflow to:
- Check data freshness (count new rows since last train)
- Call drift detection endpoints
- Call retrain endpoints
- Update model_health table
"""

from __future__ import annotations

import httpx
import structlog
from temporalio import activity

from core.db import get_pool
from services_api.experiments.observability import upsert_model_health

logger = structlog.get_logger()


@activity.defn(name="check_model_freshness")
async def check_model_freshness(model_cfg: dict) -> dict:
    """Count new rows in the model's training table since last train."""
    pool = await get_pool()
    table = model_cfg["min_new_rows_table"]
    model_name = model_cfg["model_name"]

    row = await pool.fetchrow(
        """
        SELECT last_trained_at FROM model_health
        WHERE model_name = $1 LIMIT 1
    """,
        model_name,
    )

    last_trained = row["last_trained_at"] if row else None

    if last_trained:
        count = await pool.fetchval(
            f"""
            SELECT COUNT(*) FROM {table}
            WHERE created_at > $1
        """,
            last_trained,
        )
    else:
        count = await pool.fetchval(f"SELECT COUNT(*) FROM {table}")

    total = await pool.fetchval(f"SELECT COUNT(*) FROM {table}")

    return {
        "model_name": model_name,
        "new_rows_since_last_train": count,
        "total_rows": total,
        "last_trained_at": last_trained.isoformat() if last_trained else None,
    }


@activity.defn(name="check_model_drift")
async def check_model_drift(model_cfg: dict) -> dict:
    """Call the service's drift detection endpoint."""
    service = model_cfg["service"]
    port = model_cfg["port"]
    drift_endpoint = model_cfg.get("drift_endpoint")

    if not drift_endpoint:
        return {"drift_detected": False, "reason": "No drift endpoint"}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(f"http://{service}:{port}{drift_endpoint}")
            resp.raise_for_status()
            data = resp.json()
            return {
                "drift_detected": data.get("data", {}).get("drift_detected", False),
                "drift_score": data.get("data", {}).get("drift_score", 0),
            }
    except Exception as e:
        logger.warning("model_maintenance.drift_check_failed", model=model_cfg["model_name"], error=str(e))
        return {"drift_detected": False, "error": str(e)}


@activity.defn(name="retrain_model")
async def retrain_model(model_cfg: dict) -> dict:
    """Call the service's train endpoint to retrain the model."""
    service = model_cfg["service"]
    port = model_cfg["port"]
    train_endpoint = model_cfg["train_endpoint"]

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(f"http://{service}:{port}{train_endpoint}")
            resp.raise_for_status()
            data = resp.json()

            return {
                "status": data.get("status", "unknown"),
                "data": data.get("data", {}),
            }
    except Exception as e:
        logger.error("model_maintenance.retrain_failed", model=model_cfg["model_name"], error=str(e))
        return {"status": "error", "error": str(e)}


@activity.defn(name="update_model_health")
async def update_model_health_activity(params: dict) -> dict:
    """Update the model_health table after a train/check cycle."""
    model_name = params["model_name"]
    training_rows = params.get("training_rows", 0)
    drift_detected = params.get("drift_detected", False)
    train_result = params.get("train_result", {})

    status = "trained" if train_result.get("status") == "success" else "error"
    accuracy = train_result.get("data", {}).get("accuracy", 0)

    pool = await get_pool()
    niches = await pool.fetch("""
        SELECT DISTINCT niche FROM channels WHERE status = 'active'
    """)

    for row in niches:
        niche = row["niche"]
        await upsert_model_health(
            model_name=model_name,
            niche=niche,
            training_rows=training_rows,
            accuracy_metric=accuracy,
            drift_detected=drift_detected,
            drift_score=params.get("drift_score", 0),
            status=status,
        )

    return {"model_name": model_name, "status": status, "niches_updated": len(niches)}
