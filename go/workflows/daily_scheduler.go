package workflows

import (
	"fmt"
	"time"

	"go.temporal.io/sdk/workflow"
)

// DailySchedulerWorkflow checks system status, budget, and eligible channels,
// then fires one VideoProductionWorkflow child per channel.
// Task queue: "scheduler" (Go orchestration) + "video-production" for child workflows.
func DailySchedulerWorkflow(ctx workflow.Context, params map[string]interface{}) (map[string]interface{}, error) {
	log := workflow.GetLogger(ctx)

	// 1. System status check
	statusResult, err := execActivity(ctx, "check_system_status", 30*time.Second, retryStandard)
	if err != nil {
		return nil, err
	}
	if !getBool(statusResult, "ready") {
		log.Info("system not ready — skipping daily run", "reason", statusResult["reason"])
		return map[string]interface{}{"status": "skipped", "reason": statusResult["reason"]}, nil
	}

	// 2. Eligible channels
	ao := workflow.ActivityOptions{StartToCloseTimeout: 30 * time.Second, RetryPolicy: retryStandard}
	actCtx := workflow.WithActivityOptions(ctx, ao)
	var channels []map[string]interface{}
	if err := workflow.ExecuteActivity(actCtx, "get_eligible_channels").Get(actCtx, &channels); err != nil {
		return nil, err
	}
	if len(channels) == 0 {
		log.Info("no eligible channels — nothing to do")
		return map[string]interface{}{"status": "ok", "started": 0}, nil
	}

	// 3. Start one child VideoProductionWorkflow per channel
	started := 0
	ts := workflow.Now(ctx).Format("20060102-150405")

	for _, ch := range channels {
		channelID := getString(ch, "channel_id", getString(ch, "id", ""))
		if channelID == "" {
			continue
		}
		mode, _ := ch["content_mode"].(string)
		if mode == "" {
			mode = "long_form"
		}
		modePrefix := "L"
		if mode == "short_form" || mode == "short" {
			modePrefix = "S"
		}

		var topicCandidates []string
		if tc, ok := ch["topic_candidates"].([]interface{}); ok {
			for _, t := range tc {
				if s, ok := t.(string); ok {
					topicCandidates = append(topicCandidates, s)
				}
			}
		}
		maxCost := getFloat(ch, "max_cost_usd", 2.50)

		// Acquire channel lock before starting
		locked, err := execActivityBool(ctx, "acquire_channel_lock", 10*time.Second, retryStandard, channelID)
		if err != nil || !locked {
			log.Warn("failed to acquire lock — skipping channel", "channel_id", channelID)
			continue
		}

		childOpts := workflow.ChildWorkflowOptions{
			WorkflowID: fmt.Sprintf("video-%s-%s-%s", channelID, modePrefix, ts),
			TaskQueue:  "video-production",
		}
		childCtx := workflow.WithChildOptions(ctx, childOpts)

		childParams := VideoParams{
			ChannelID:       channelID,
			ContentMode:     mode,
			TopicCandidates: topicCandidates,
			MaxCostUSD:      maxCost,
			Environment:     "production",
		}

		// Fire-and-forget — don't block the scheduler on individual workflow completion
		workflow.ExecuteChildWorkflow(childCtx, VideoProductionWorkflow, childParams)
		started++
		log.Info("started child VideoProductionWorkflow", "channel_id", channelID, "mode", mode)
	}

	return map[string]interface{}{"status": "ok", "started": started}, nil
}
