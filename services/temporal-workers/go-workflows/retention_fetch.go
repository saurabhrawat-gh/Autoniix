package workflows

import (
	"time"

	"go.temporal.io/sdk/workflow"
)

const defaultBatchLimit = 50

// RetentionFetchWorkflow pulls audience-retention curves for eligible videos.
// Task queue: "scheduler". Cron: daily 03:00 UTC.
func RetentionFetchWorkflow(ctx workflow.Context, params map[string]interface{}) (map[string]interface{}, error) {
	log := workflow.GetLogger(ctx)

	limit := defaultBatchLimit
	if params != nil {
		if l, ok := params["limit"].(float64); ok {
			limit = int(l)
		}
	}

	contentIDs, err := execActivityStringList(ctx, "list_videos_needing_retention", 30*time.Second, retryLight, limit)
	if err != nil {
		return nil, err
	}

	statusCounts := map[string]int{}
	for _, contentID := range contentIDs {
		summary, err := execActivity(ctx, "fetch_retention_for_video", 30*time.Second, retryLight, contentID)
		if err != nil {
			log.Warn("fetch_retention_for_video failed", "content_id", contentID, "error", err)
			statusCounts["error"]++
			continue
		}
		status := getString(summary, "status", "unknown")
		statusCounts[status]++
	}

	// Convert int counts to interface{} for JSON serialisation
	byStatus := map[string]interface{}{}
	for k, v := range statusCounts {
		byStatus[k] = v
	}

	return map[string]interface{}{
		"candidates": len(contentIDs),
		"by_status":  byStatus,
	}, nil
}
