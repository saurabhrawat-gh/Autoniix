# Appendix: Glossary

**Activity** — a Temporal unit of work, typically a thin wrapper around a
service HTTP call. Idempotent, retried under `RetryPolicy`.

**A/B framework** — deterministic experiment assignment + Welch’s t-test
for coarse variant comparison.

**Bandit (Thompson Sampling)** — Beta-Bernoulli arm selection for online
learning across small choice sets (hook style, pacing).

**Brier score** — mean squared error between predicted probability and
observed outcome. Lower is better. Healthy < 0.20 in this stack.

**Checkpoint** — the current/last phase recorded on `videos.checkpoint`,
used by the resume-from-checkpoint workflow path.

**Composite score** — weighted mean of per-dimension quality scores;
compared against the composite threshold to decide pass / human review.

**Content id** — globally-unique id for one produced video. Format:
`<prefix>_<channel>_<timestamp>` where prefix is `TEST_VID` or `VID`.

**Content mode** — `long` (8 min) or `short` (45 s).

**DAM** — Digital Asset Manager, the Library UI / table for local stock
footage.

**Direction v3** — the rich per-segment direction (camera, text strategy,
motion design, audio cues, background, transition) produced by the
direction service.

**Emergency stop** — a global flag in `system_config.emergency_stop`. When
true, every workflow short-circuits at its next `check_system_status`.

**Fallback chain** — ordered list of providers tried in turn on failure;
lives in `provider_credentials` table, resolved by `chain.py`.

**Fleet health** — BFF aggregate of DB pool pressure, Temporal queue
depth, worker/service health and model health.

**Niche** — the topical category for a channel (sleep, finance, stoic,
etc.). Determines which GBM / bandit / threshold applies.

**Phase** — one of `WORKFLOW_PHASES` (researching, brand_check, scripting,
generating_voice, generating_assets, directing, post_production,
rendering, delivering, analytics).

**Principal** — the BFF’s representation of the authenticated caller
(`user_id`, `workspace_id`, `role`).

**PSI** — Population Stability Index, used for drift detection on model
inputs.

**Resume from checkpoint** — starting a new workflow with the same
`content_id` and `resume_from_phase` so earlier phases are skipped and
their outputs re-hydrated from `save_checkpoint_data`.

**Retry (fresh)** — marks the old job `superseded`, starts a brand-new
workflow with a fresh `content_id`.

**Stopped** — user-initiated stop. Job is resumable.

**Superseded** — marker for an old failed/stopped job that has been
replaced by a retry; excluded from active views and counters.

**Test mode / Production mode** — see [[Test-vs-Production-Mode]].

**Vision QC** — GPT-4o-Vision call that scores thumbnails on multiple
composition dimensions; loops with regeneration up to 2 times.

**Workspace** — multi-tenant scope. Every channel, video, config row
lives inside exactly one workspace.

## Related pages

- [[Home]] · [[Workflow-VideoProduction]] · [[ML-GBM-Models]]
