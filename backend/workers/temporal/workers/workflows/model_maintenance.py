"""ModelMaintenanceWorkflow — weekly ML model retraining & health checks.

Ported from ``go-workflows/model_maintenance.go``. Task queue: ``scheduler-v2``.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow

from .types import RETRY_LIGHT

# Each entry is the activity contract consumed by
# temporal_workers.activities.model (check_model_freshness / check_model_drift /
# retrain_model): which service to call, on which port, and how much new
# outcome data must exist before a retrain is worth running.
TRAINABLE_MODELS: list[dict[str, Any]] = [
    {
        "model_name": "voice_style_gbm",
        "service": "voice",
        "port": 8003,
        "train_endpoint": "/voice-train",
        "drift_endpoint": None,
        "min_new_rows_table": "voice_outcomes",
        "min_rows_for_train": 20,
    },
    {
        "model_name": "thumbnail_ctr_gbm",
        "service": "thumbnail",
        "port": 8005,
        "train_endpoint": "/thumbnail-train",
        "drift_endpoint": None,
        "min_new_rows_table": "thumbnail_outcomes",
        "min_rows_for_train": 20,
    },
    {
        "model_name": "research_gbm",
        "service": "research",
        "port": 8001,
        "train_endpoint": "/train",
        "drift_endpoint": "/drift",
        "min_new_rows_table": "performance_outcomes",
        "min_rows_for_train": 30,
    },
    {
        "model_name": "script_gbm",
        "service": "script",
        "port": 8002,
        "train_endpoint": "/script-train",
        "drift_endpoint": "/script-drift",
        "min_new_rows_table": "script_outcomes",
        "min_rows_for_train": 20,
    },
]


@workflow.defn(name="ModelMaintenanceWorkflow")
class ModelMaintenanceWorkflow:
    @workflow.run
    async def run(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        log = workflow.logger

        retrained = 0
        skipped = 0
        errors = 0
        model_results: dict[str, Any] = {}

        for model_cfg in TRAINABLE_MODELS:
            model_name = model_cfg["model_name"]
            log.info("checking model", extra={"model": model_name})

            # 1. Freshness check
            try:
                freshness = await workflow.execute_activity(
                    "check_model_freshness",
                    model_cfg,
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=RETRY_LIGHT,
                )
            except Exception as exc:  # noqa: BLE001
                log.warn(
                    "check_model_freshness failed",
                    extra={"model": model_name, "error": str(exc)},
                )
                errors += 1
                model_results[model_name] = {"action": "error", "error": str(exc)}
                continue

            if not freshness.get("has_new_data"):
                log.info("no new data — skipping model", extra={"model": model_name})
                skipped += 1
                model_results[model_name] = {"action": "skipped", "reason": "no_new_data"}
                continue

            # 2. Drift check
            try:
                drift = await workflow.execute_activity(
                    "check_model_drift",
                    model_cfg,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RETRY_LIGHT,
                )
            except Exception as exc:  # noqa: BLE001
                log.warn(
                    "check_model_drift failed",
                    extra={"model": model_name, "error": str(exc)},
                )
                errors += 1
                model_results[model_name] = {"action": "error", "error": str(exc)}
                continue

            needs_retrain = drift.get("drift_detected") or freshness.get("staleness_critical")

            if not needs_retrain:
                log.info("no drift — updating health only", extra={"model": model_name})
                await workflow.execute_activity(
                    "update_model_health",
                    {
                        "model_name": model_name,
                        "status": "healthy",
                        "drift": drift,
                        "freshness": freshness,
                    },
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RETRY_LIGHT,
                )
                skipped += 1
                model_results[model_name] = {"action": "health_updated"}
                continue

            # 3. Retrain
            log.info(
                "retraining model",
                extra={
                    "model": model_name,
                    "drift_detected": drift.get("drift_detected"),
                    "staleness_critical": freshness.get("staleness_critical"),
                },
            )
            try:
                retrain_result = await workflow.execute_activity(
                    "retrain_model",
                    model_cfg,
                    start_to_close_timeout=timedelta(minutes=30),
                    retry_policy=RETRY_LIGHT,
                )
            except Exception as exc:  # noqa: BLE001
                log.warn(
                    "retrain_model failed",
                    extra={"model": model_name, "error": str(exc)},
                )
                errors += 1
                model_results[model_name] = {"action": "error", "error": str(exc)}
                continue

            # 4. Health metrics
            await workflow.execute_activity(
                "update_model_health",
                {
                    "model_name": model_name,
                    "status": "retrained",
                    "retrain_result": retrain_result,
                    "drift": drift,
                },
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RETRY_LIGHT,
            )

            retrained += 1
            model_results[model_name] = {
                "action": "retrained",
                "metrics_before": drift.get("metrics_before"),
                "metrics_after": retrain_result.get("metrics_after"),
            }
            log.info("model retrained", extra={"model": model_name})

        return {
            "models_total": len(TRAINABLE_MODELS),
            "retrained": retrained,
            "skipped": skipped,
            "errors": errors,
            "model_results": model_results,
        }
