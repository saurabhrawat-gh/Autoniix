# Workflow: RetentionFetchWorkflow

## Purpose

Daily ingestion of YouTube Analytics audience-retention curves for
delivered videos. **Daily 03:00 UTC**.

## Source

- `src/temporal_workflows/retention_fetch.py`
- Activities: `src/temporal_workflows/retention_activities.py`
  - `list_videos_needing_retention_activity`
  - `fetch_retention_for_video_activity`

## OAuth scope requirement

The Google OAuth refresh token used by delivery must include
`https://www.googleapis.com/auth/yt-analytics.readonly` in addition to
`youtube.upload`. Without it the activity raises 403. (Tracked in
`PENDING.md` first-deploy-checklist.)

## Logic

1. Pick videos delivered between 7 and 30 days ago that have no retention
   curve yet (`videos.retention_fetched_at IS NULL`).
2. For each, call YouTube Analytics API for `audienceWatchRatio` at 1s
   intervals across the video duration.
3. Persist curve to `videos.retention_curve` (JSONB) and update
   `videos.retention_fetched_at`.
4. Feed into `performance_outcomes` for the self-learning loop (the average
   retention is one of the labels for the script/thumbnail GBMs).

## Manual backfill

After first deploy: invoke this workflow once with `{"limit": 200}` so all
old videos are backfilled. Until that runs, the calibrator falls back to
tier labels.

## Related pages

- [[Service-Delivery]]
- [[Service-Analytics]]
- [[ML-Self-Learning-Loop]]
