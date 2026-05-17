# Cost Analysis

## Purpose

What does one video cost? What does the fleet cost at 1, 10, 100 channels?

## Source

- `docs/07-COST-ANALYSIS.md` (full breakdown)
- `src/observability/budget_metrics.py` (live metric)
- `intelligence_metrics` table (decision logging)

## Per-video (production mode)

Typical 8-minute long-form video:

| Component | Cost |
|---|---|
| LLM (research + script + critiques + QC) | $0.04–$0.12 |
| TTS (Fish Audio, ~1100 words, ~7.5 min) | $0.16 |
| Image (DALL·E thumbnail, 1–3 variants) | $0.04–$0.12 |
| Search (SerpAPI, ~5 queries) | $0.025 |
| Render compute (Remotion, ~6 min @ 30fps) | self-hosted, ~$0.01 elec |
| Storage / bandwidth | ~$0 (self-hosted MinIO) |
| **Total** | **$0.12–$0.35** |

## Per-video (test mode)

~$0.00 because providers are mock (Edge TTS, placeholder images, cached
LLM responses). First-time cache misses on mock LLM fall through to
gpt-4o-mini at ~$0.01.

## Fleet scaling table

Assuming 1 long + 7 shorts/week per channel × 4 weeks:

| Channels | Long+short/mo | Avg cost | Monthly |
|---|---|---|---|
| 1 | 32 | $0.20 | $6.40 |
| 10 | 320 | $0.20 | $64 |
| 100 | 3,200 | $0.20 | $640 |

VPS (Hetzner CCX23, ~$35/mo) supports up to ~25 channels with
default concurrency. Beyond that, scale `worker-production` replicas
or add a second VPS for Remotion workers.

## Savings from intelligence layer

`intelligence_metrics.cost_usd` is the difference between an LLM call
that was replaced by a local decision. Estimated $0.03–$0.05 saved per
video from local-first NLP, scorer-driven rewrites, and bandit-routed
choices.

## Budget guards

- Per-video: `params.max_cost_usd` (passed in `VideoParams`) raises
  `RuntimeError` mid-pipeline if exceeded.
- Daily fleet: `daily_budget_limit_usd` enforced by
  `check_system_status` at the top of every workflow.
- Test mode caps: `$5/day`, `10 videos/day`.

## Related pages

- [[Quality-Gates]] · [[Test-vs-Production-Mode]] ·
  [[Observability-Prometheus-Grafana]]
