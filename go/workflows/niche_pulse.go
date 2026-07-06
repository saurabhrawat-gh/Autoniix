package workflows

import (
	"time"

	"go.temporal.io/sdk/workflow"
)

// NichePulseRefreshWorkflow refreshes per-niche competitor-video snapshots weekly.
// Task queue: "scheduler". Cron: weekly Sunday 05:00 UTC.
func NichePulseRefreshWorkflow(ctx workflow.Context, params map[string]interface{}) (map[string]interface{}, error) {
	log := workflow.GetLogger(ctx)

	niches, err := execActivityStringList(ctx, "list_niches_with_outcomes", 30*time.Second, retryLight)
	if err != nil {
		return nil, err
	}

	results := map[string]interface{}{}
	for _, niche := range niches {
		summary, err := execActivity(ctx, "refresh_niche_pulse", 5*time.Minute, retryLight, niche)
		if err != nil {
			log.Warn("refresh_niche_pulse failed", "niche", niche, "error", err)
			results[niche] = map[string]interface{}{"action": "error", "error": err.Error()}
			continue
		}
		results[niche] = summary
	}

	return map[string]interface{}{
		"niches_processed": len(niches),
		"results":          results,
	}, nil
}
