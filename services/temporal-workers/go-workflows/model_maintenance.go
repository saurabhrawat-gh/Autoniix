package workflows

import (
	"time"

	"go.temporal.io/sdk/workflow"
)

// trainableModels mirrors the TRAINABLE_MODELS constant in model_maintenance.py.
var trainableModels = []string{
	"script_quality",
	"thumbnail_ctr",
	"voice_engagement",
	"retention_predictor",
	"title_optimizer",
}

// ModelMaintenanceWorkflow automates weekly retraining and health checks of ML models.
// Task queue: "scheduler". Cron: weekly.
func ModelMaintenanceWorkflow(ctx workflow.Context, params map[string]interface{}) (map[string]interface{}, error) {
	log := workflow.GetLogger(ctx)

	retrained := 0
	skipped := 0
	errors := 0
	modelResults := map[string]interface{}{}

	for _, modelName := range trainableModels {
		log.Info("checking model", "model", modelName)

		// 1. Check data freshness
		freshnessResult, err := execActivity(ctx, "check_model_freshness", 2*time.Minute, retryLight, modelName)
		if err != nil {
			log.Warn("check_model_freshness failed", "model", modelName, "error", err)
			errors++
			modelResults[modelName] = map[string]interface{}{"action": "error", "error": err.Error()}
			continue
		}

		if !getBool(freshnessResult, "has_new_data") {
			log.Info("no new data — skipping model", "model", modelName)
			skipped++
			modelResults[modelName] = map[string]interface{}{"action": "skipped", "reason": "no_new_data"}
			continue
		}

		// 2. Check for drift
		driftResult, err := execActivity(ctx, "check_model_drift", 5*time.Minute, retryLight, modelName)
		if err != nil {
			log.Warn("check_model_drift failed", "model", modelName, "error", err)
			errors++
			modelResults[modelName] = map[string]interface{}{"action": "error", "error": err.Error()}
			continue
		}

		needsRetrain := getBool(driftResult, "drift_detected") ||
			getBool(freshnessResult, "staleness_critical")

		if !needsRetrain {
			log.Info("no drift detected — updating health only", "model", modelName)
			_, _ = execActivity(ctx, "update_model_health", 30*time.Second, retryLight,
				map[string]interface{}{
					"model_name": modelName,
					"status":     "healthy",
					"drift":      driftResult,
					"freshness":  freshnessResult,
				})
			skipped++
			modelResults[modelName] = map[string]interface{}{"action": "health_updated"}
			continue
		}

		// 3. Retrain
		log.Info("retraining model", "model", modelName,
			"drift_detected", driftResult["drift_detected"],
			"staleness_critical", freshnessResult["staleness_critical"])

		retrainResult, err := execActivity(ctx, "retrain_model", 30*time.Minute, retryLight, modelName)
		if err != nil {
			log.Warn("retrain_model failed", "model", modelName, "error", err)
			errors++
			modelResults[modelName] = map[string]interface{}{"action": "error", "error": err.Error()}
			continue
		}

		// 4. Update health metrics
		_, _ = execActivity(ctx, "update_model_health", 30*time.Second, retryLight,
			map[string]interface{}{
				"model_name":     modelName,
				"status":         "retrained",
				"retrain_result": retrainResult,
				"drift":          driftResult,
			})

		retrained++
		modelResults[modelName] = map[string]interface{}{
			"action":         "retrained",
			"metrics_before": driftResult["metrics_before"],
			"metrics_after":  retrainResult["metrics_after"],
		}
		log.Info("model retrained", "model", modelName)
	}

	return map[string]interface{}{
		"models_total":  len(trainableModels),
		"retrained":     retrained,
		"skipped":       skipped,
		"errors":        errors,
		"model_results": modelResults,
	}, nil
}
