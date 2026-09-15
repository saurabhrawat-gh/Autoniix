# 13 — Mass-Content Safety & Authenticity

**Goal:** keep the channels monetizable on YouTube despite running fully
automated AI pipelines. The screenshots from `Tricked Entertain`, `NYKentertain`
and `ErnieC3` show the failure mode we are designing around: YouTube's
"inauthentic content" enforcement that flags channels with mass-produced,
template-driven, low-narrative output.

This document captures the failure modes, our mitigations, and the metrics
the dashboard surfaces so you can spot drift early.

---

## 1. YouTube's enforcement signals (observed)

Pulled from the demonetization emails surfaced in the source images:

- "Mass-produced content using a similar template across multiple videos"
- "Highly repetitive content with minimal variation across videos"
- "Image slideshows or scrolling text with minimal or no narrative,
  commentary, or educational value"
- "Songs you did not originally create which have been modified to change
  the pitch or speed"
- "Content that exclusively features readings of other materials you did
  not originally create"

The common thread is _low entropy across a channel's catalog_ — visual,
narrative, and structural sameness — not single-video issues.

## 2. Our defenses

### 2.1 Per-video gates (block at generation time)

| Gate                                                            | Implementation                                                                                                                                                        | Threshold                                  |
| --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| **Title/hook similarity** to last 30 videos in the same channel | `src/intelligence/uniqueness_guard.check_uniqueness()` using pgvector cosine on `videos.title_embedding`                                                              | similarity ≥ **0.92** → reject and re-roll |
| **Phrase novelty** vs. `phrase_bank`                            | `research/burst_detector.py` (already in tree)                                                                                                                        | enforced via existing research scoring     |
| **Authenticity score**                                          | `compute_authenticity_score()` weighted composite of hook novelty, thumbnail distinctiveness, structure score, production score, and cross-channel similarity penalty | < **0.70** → human review forced           |

### 2.2 Variation enforcement (force diversity across the catalog)

- **Hook style**: drawn from the script `script_bandit_state` arms; the
  bandit is forbidden from picking the same arm twice in a row for the same
  channel (cool-down implemented in `script/self_learning.py`).
- **Thumbnail composition**: `thumbnail/composition_analyzer.py` rotates
  composition rules in a round-robin per channel.
- **Voice params**: `voice/voice_style_learner.py` draws from a wider
  posterior, not the MAP — we deliberately accept lower per-video score for
  better catalog diversity.
- **Music style** & **transition style**: drawn from per-channel preference
  with ε=0.15 exploration each render.

### 2.3 Human-ratio enforcer

`channels.human_review_ratio` (0.0–1.0) forces a randomly-selected fraction
of generations through manual review even when `human_review_required = 'never'`.
A Temporal activity (`review_gate`, Phase 3) reads this column and
short-circuits to the review-pending state with the configured probability.

### 2.4 Drift watchdog

A nightly Temporal cron walks each channel's last 5 published videos. If
all five exceed the channel's `authenticity_threshold` ceiling for
similarity, the channel is auto-paused and a `critical` notification fires
(routed to Slack when configured). Recovery requires manual action — same
muscle memory YouTube wants creators to develop.

## 3. Recommended ratios (solo operator)

For a single user running 1–10 channels:

- `human_review_ratio` ≥ **0.10** for any channel posting > 5 videos / week.
- `human_review_ratio` ≥ **0.20** for channels in policy-sensitive niches
  (commentary, news, kids, finance).
- Never run two channels with > 80% pillar overlap on the same Google account.
- Differentiate voice provider/voice-id between channels in the same niche.
- Differentiate LUT + transition style — not just thumbnails — between
  catalogs that share an audience.

## 4. What the dashboard shows

- **Per-video card** (`/dashboard/v2/content`): authenticity badge with
  three states — green ≥ 0.80, amber 0.60–0.80, red < 0.60.
- **Channel detail**: rolling 30-video authenticity histogram +
  similarity heatmap.
- **Debug**: list of recently-rejected candidates and the nearest
  similar video that triggered the rejection.

## 5. What this does NOT solve

- Original copyright disputes (manual content moderation needed).
- Music modification flags — we never run pitch/tempo modifications on
  third-party music. Use the Music Library + licensed tracks only.
- Pure narrative quality — the GBM critics catch the worst, but not all.

For ongoing tuning, watch `intelligence_metrics` and the rejection rate
on each channel; sustained > 30% rejection means similarity weights
need raising or topic generation broadening.
