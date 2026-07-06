package workflows

import (
	"time"

	"go.temporal.io/sdk/workflow"
)

// HealthBeatWorkflow is a thin wrapper executed by the provider-health-beat
// Temporal schedule every 5 minutes.
func HealthBeatWorkflow(ctx workflow.Context) (map[string]interface{}, error) {
	ao := workflow.ActivityOptions{
		ScheduleToCloseTimeout: 4 * time.Minute,
		StartToCloseTimeout:    4 * time.Minute,
	}
	actCtx := workflow.WithActivityOptions(ctx, ao)
	var result map[string]interface{}
	err := workflow.ExecuteActivity(actCtx, "check_all_provider_health").Get(actCtx, &result)
	return result, err
}
