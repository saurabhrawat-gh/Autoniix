// Package workflows contains Temporal workflow definitions for the Autoniix
// video-production pipeline. Workflows orchestrate work; all activities
// (AI/ML, DB writes, provider calls) remain on the Python activity worker.
package workflows

import (
	"fmt"
	"strings"
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

// ── Input/Output types (mirror src/schemas/common.py dataclasses) ─────────────

// VideoParams is the input to VideoProductionWorkflow.
type VideoParams struct {
	ChannelID           string   `json:"channel_id"`
	ContentMode         string   `json:"content_mode"`
	TopicCandidates     []string `json:"topic_candidates"`
	MaxCostUSD          float64  `json:"max_cost_usd"`
	HumanReviewRequired bool     `json:"human_review_required"`
	ResumeFrom          string   `json:"resume_from,omitempty"`
	OriginalContentID   string   `json:"original_content_id,omitempty"`
	ContentID           string   `json:"content_id,omitempty"`
	Environment         string   `json:"environment"`
}

// VideoResult is the output of VideoProductionWorkflow.
type VideoResult struct {
	Status         string  `json:"status"`
	ContentID      string  `json:"content_id,omitempty"`
	YoutubeVideoID string  `json:"youtube_video_id,omitempty"`
	Cost           float64 `json:"cost"`
	Reason         string  `json:"reason,omitempty"`
}

// ── Ordered production-phase list ─────────────────────────────────────────────

var workflowPhases = []string{
	"researching", "brand_check", "scripting", "generating_voice",
	"generating_assets", "directing", "post_production", "rendering",
	"finishing", "delivering", "analytics",
}

// ── Retry policies (mirror Python constants in video_production.py) ───────────

var retryStandard = &temporal.RetryPolicy{
	MaximumAttempts:        3,
	InitialInterval:        10 * time.Second,
	BackoffCoefficient:     2.0,
	MaximumInterval:        60 * time.Second,
	NonRetryableErrorTypes: []string{"BudgetExceededError", "ValidationError"},
}

var retryRender = &temporal.RetryPolicy{
	MaximumAttempts: 2,
	InitialInterval: 30 * time.Second,
	MaximumInterval: 5 * time.Minute,
}

var retryFinish = &temporal.RetryPolicy{
	MaximumAttempts:    3,
	InitialInterval:    30 * time.Second,
	BackoffCoefficient: 2.0,
	MaximumInterval:    5 * time.Minute,
}

var retryLight = &temporal.RetryPolicy{
	MaximumAttempts:    2,
	InitialInterval:    5 * time.Second,
	BackoffCoefficient: 2.0,
	MaximumInterval:    30 * time.Second,
}

// ── Phase helpers ─────────────────────────────────────────────────────────────

// shouldSkip returns true when phase was already completed before resumeFrom.
func shouldSkip(phase, resumeFrom string) bool {
	if resumeFrom == "" {
		return false
	}
	phaseIdx, resumeIdx := -1, -1
	for i, p := range workflowPhases {
		if p == phase {
			phaseIdx = i
		}
		if p == resumeFrom {
			resumeIdx = i
		}
	}
	return phaseIdx >= 0 && resumeIdx >= 0 && phaseIdx < resumeIdx
}

// ── Activity execution helpers ────────────────────────────────────────────────

// execActivity runs a named cross-language activity; result decoded to map.
// args are forwarded as positional Temporal activity arguments.
func execActivity(
	ctx workflow.Context,
	name string,
	timeout time.Duration,
	rp *temporal.RetryPolicy,
	args ...interface{},
) (map[string]interface{}, error) {
	ao := workflow.ActivityOptions{StartToCloseTimeout: timeout, RetryPolicy: rp}
	actCtx := workflow.WithActivityOptions(ctx, ao)
	var result map[string]interface{}
	err := workflow.ExecuteActivity(actCtx, name, args...).Get(actCtx, &result)
	return result, err
}

// execActivityBool runs an activity expected to return a bool.
func execActivityBool(
	ctx workflow.Context,
	name string,
	timeout time.Duration,
	rp *temporal.RetryPolicy,
	args ...interface{},
) (bool, error) {
	ao := workflow.ActivityOptions{StartToCloseTimeout: timeout, RetryPolicy: rp}
	actCtx := workflow.WithActivityOptions(ctx, ao)
	var result bool
	err := workflow.ExecuteActivity(actCtx, name, args...).Get(actCtx, &result)
	return result, err
}

// execActivityStringList runs an activity expected to return []string.
func execActivityStringList(
	ctx workflow.Context,
	name string,
	timeout time.Duration,
	rp *temporal.RetryPolicy,
	args ...interface{},
) ([]string, error) {
	ao := workflow.ActivityOptions{StartToCloseTimeout: timeout, RetryPolicy: rp}
	actCtx := workflow.WithActivityOptions(ctx, ao)
	var result []string
	err := workflow.ExecuteActivity(actCtx, name, args...).Get(actCtx, &result)
	return result, err
}

// ── Map accessors ─────────────────────────────────────────────────────────────

func addCost(result map[string]interface{}) float64 {
	costMap, _ := result["cost"].(map[string]interface{})
	if costMap == nil {
		return 0
	}
	v, _ := costMap["cost_usd"].(float64)
	return v
}

func getFloat(m map[string]interface{}, key string, fallback float64) float64 {
	if m == nil {
		return fallback
	}
	switch v := m[key].(type) {
	case float64:
		return v
	case float32:
		return float64(v)
	case int:
		return float64(v)
	}
	return fallback
}

func getString(m map[string]interface{}, key, fallback string) string {
	if m == nil {
		return fallback
	}
	if v, ok := m[key].(string); ok {
		return v
	}
	return fallback
}

func getBool(m map[string]interface{}, key string) bool {
	if m == nil {
		return false
	}
	v, _ := m[key].(bool)
	return v
}

func getSlice(m map[string]interface{}, key string) []interface{} {
	if m == nil {
		return nil
	}
	v, _ := m[key].([]interface{})
	return v
}

func getMap(m map[string]interface{}, key string) map[string]interface{} {
	if m == nil {
		return nil
	}
	v, _ := m[key].(map[string]interface{})
	return v
}

// ── Brain directive ───────────────────────────────────────────────────────────

// checkBrainDirective returns an ApplicationError when the directive demands HALT or HOLD.
func checkBrainDirective(directive map[string]interface{}) error {
	if len(directive) == 0 {
		return nil
	}
	action := strings.ToUpper(getString(directive, "action", ""))
	if action != "HALT" && action != "HOLD" {
		return nil
	}
	reasoning := getString(directive, "reasoning", "no reason provided")
	msg := fmt.Sprintf("BrainHalt(%s): %s", action, reasoning)
	if action == "HALT" {
		return temporal.NewNonRetryableApplicationError(msg, "BrainHaltException", nil)
	}
	return temporal.NewApplicationError(msg, "BrainHaltException")
}
