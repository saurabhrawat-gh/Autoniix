package workflows

import (
	"time"

	"go.temporal.io/sdk/workflow"
)

// ChangeRequestExpiryWorkflow is a thin wrapper executed hourly by the
// change-request-expiry Temporal schedule.
func ChangeRequestExpiryWorkflow(ctx workflow.Context) (map[string]interface{}, error) {
	ao := workflow.ActivityOptions{
		ScheduleToCloseTimeout: 5 * time.Minute,
		StartToCloseTimeout:    5 * time.Minute,
	}
	actCtx := workflow.WithActivityOptions(ctx, ao)
	var result map[string]interface{}
	err := workflow.ExecuteActivity(actCtx, "expire_stale_change_requests").Get(actCtx, &result)
	return result, err
}
