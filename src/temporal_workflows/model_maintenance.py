"""Model Maintenance Workflow — Automated retraining and health checks.

Runs on a weekly schedule via Temporal cron.
For each ML model (voice, thumbnail, research, script):
1. Check data freshness — enough new rows since last train?
2. Run drift detection — has feature distribution shifted?
3. Retrain if needed — call the /train endpoint on the service
4. Update model_health table
5. Log summary to intelligence_metrics

Cron schedule: weekly (Sunday 03:00 UTC)
"""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    pass

RETRY_LIGHT = RetryPolicy(
    maximum_attempts=2,
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
)

# Service endpoints for training
TRAINABLE_MODELS = [
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


@workflow.defn
class ModelMaintenanceWorkflow:
    """Weekly model maintenance: check health → detect drift → retrain."""

    @workflow.run
    async def run(self, params: dict | None = None) -> dict:
        results = {}

        for model_cfg in TRAINABLE_MODELS:
            model_name = model_cfg["model_name"]

            try:
                # Step 1: Check data freshness
                freshness = await workflow.execute_activity(
                    "check_model_freshness",
                    args=[model_cfg],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RETRY_LIGHT,
                )

                new_rows = freshness.get("new_rows_since_last_train", 0)
                min_rows = model_cfg["min_rows_for_train"]

                if new_rows < min_rows:
                    results[model_name] = {
                        "action": "skipped",
                        "reason": f"Only {new_rows} new rows (need {min_rows})",
                    }
                    continue

                # Step 2: Drift detection (if endpoint exists)
                drift_detected = False
                if model_cfg.get("drift_endpoint"):
                    drift_result = await workflow.execute_activity(
                        "check_model_drift",
                        args=[model_cfg],
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=RETRY_LIGHT,
                    )
                    drift_detected = drift_result.get("drift_detected", False)

                # Step 3: Retrain
                train_result = await workflow.execute_activity(
                    "retrain_model",
                    args=[model_cfg],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RETRY_LIGHT,
                )

                # Step 4: Update model health
                await workflow.execute_activity(
                    "update_model_health",
                    args=[{
                        "model_name": model_name,
                        "training_rows": new_rows,
                        "drift_detected": drift_detected,
                        "train_result": train_result,
                    }],
                    start_to_close_timeout=timedelta(seconds=15),
                    retry_policy=RETRY_LIGHT,
                )

                results[model_name] = {
                    "action": "retrained",
                    "new_rows": new_rows,
                    "drift_detected": drift_detected,
                    "train_status": train_result.get("status", "unknown"),
                }

            except Exception as exc:
                results[model_name] = {
                    "action": "error",
                    "error": str(exc),
                }

        return {"models_processed": len(TRAINABLE_MODELS), "results": results}
