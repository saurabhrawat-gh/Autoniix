# Skill: Test vs Production Mode

**Use when:** Environment-related changes, provider switching, cost optimization, safety guard modifications, or any feature that behaves differently in test vs production.

**When NOT to use:** Features that behave identically in both modes.

---

## Mode Selection

- Config: `ENVIRONMENT_MODE=test` or `ENVIRONMENT_MODE=production` (in `.env`)
- Code: `from src.environment import is_test, is_production, get_mode`
- Dashboard: Header pill shows green TEST / red pulsing PRODUCTION

## Provider Remapping (Automatic)

| Category  | Test Provider                 | Production Provider  | Cost Difference          |
| --------- | ----------------------------- | -------------------- | ------------------------ |
| LLM (all) | mock_llm (cached JSON)        | openai/claude/gemini | $0.00 vs $0.01-0.05/call |
| TTS       | edge_tts (free Microsoft)     | fishaudio/elevenlabs | $0.00 vs $0.02-0.10      |
| Image     | placeholder (Pillow)          | dalle                | $0.00 vs $0.04-0.08      |
| Search    | mock_search (Wikipedia cache) | serpapi              | $0.00 vs $0.003/call     |
| Storage   | minio (test/ prefix)          | minio (prod/ prefix) | Same (self-hosted)       |

## Key Differences

| Aspect             | Test              | Production        |
| ------------------ | ----------------- | ----------------- |
| Content ID prefix  | `TEST_VID_`       | `VID_`            |
| Storage prefix     | `test/`           | `prod/`           |
| Render resolution  | 640x360 @ 15fps   | 1920x1080 @ 30fps |
| YouTube upload     | **Blocked**       | Allowed           |
| Daily budget limit | $5 (configurable) | No hard limit     |
| Max videos/day     | 10 (configurable) | No hard limit     |
| Delivery phase     | Skipped           | Full pipeline     |

## Safety Guards

- Delivery service blocks YouTube upload in test mode (hardcoded check)
- `check_system_status` enforces `test_daily_budget_limit` and `test_max_videos_per_day`
- `update_video_status` and `emit_job_event` tag records with `environment` column
- Dashboard shows production confirmation dialog with cost warning

## Cleanup

- `DELETE /api/test-data` — Removes all test-prefixed data from MinIO and DB
- `GET /api/test-data/stats` — Shows test data counts
- MinIO `delete_prefix("test/")` for bulk cleanup

## Cost Summary

- Test: ~$0.00/video
- Production: ~$0.12-0.35/video
