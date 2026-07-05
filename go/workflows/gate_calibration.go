package workflows

import (
	"time"

	"go.temporal.io/sdk/workflow"
)

// GateCalibrationWorkflow runs weekly per-niche quality-gate threshold tuning.
// Task queue: "scheduler". Cron: weekly Sunday 04:00 UTC.
func GateCalibrationWorkflow(ctx workflow.Context, params map[string]interface{}) (map[string]interface{}, error) {
	log := workflow.GetLogger(ctx)

	niches, err := execActivityStringList(ctx, "list_niches_with_outcomes", 30*time.Second, retryLight)
	if err != nil {
		return nil, err
	}

	results := map[string]interface{}{}
	for _, niche := range niches {
		nicheResult, err := execActivity(ctx, "calibrate_gate_for_niche", 2*time.Minute, retryLight, niche)
		if err != nil {
			log.Warn("calibrate_gate_for_niche failed", "niche", niche, "error", err)
			results[niche] = map[string]interface{}{"action": "error", "error": err.Error()}
			continue
		}
		results[niche] = nicheResult
	}

	return map[string]interface{}{
		"niches_processed": len(niches),
		"results":          results,
	}, nil
}
