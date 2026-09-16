# Skill: Quality Gates

**Use when:** Modifying quality thresholds, scoring logic, rewrite loops, prompt registry, or composite scoring in the video production pipeline.

**When NOT to use:** General code quality or testing discussions.

---

## Quality Thresholds (system_config)

| Gate                 | Threshold | Config Key                   |
| -------------------- | --------- | ---------------------------- |
| Script overall       | ≥ 9.0     | quality_threshold_script     |
| Hook retention       | ≥ 9.0     | quality_threshold_hook       |
| Thumbnail CTR        | ≥ 9.0     | quality_threshold_thumbnail  |
| Research depth       | ≥ 8.0     | quality_threshold_research   |
| Voice quality        | ≥ 8.0     | quality_threshold_voice      |
| Direction coherence  | ≥ 8.5     | quality_threshold_direction  |
| Production composite | ≥ 8.0     | quality_threshold_production |
| **Final composite**  | **≥ 8.5** | quality_threshold_composite  |

## Anti-Inflation Measures

1. **Adversarial scoring prompts** — "You rarely give scores above 7. A score of 9+ means genuinely exceptional."
2. **Calibration examples** — Embedded in prompts with known-score samples.
3. **Rewrite limits** — Script: max 3 rewrites. Thumbnail: max 2 regenerations.
4. **Composite scoring** — Weighted average across all gates, not single-dimension.
5. **Human review** — Triggered when composite < threshold OR any gate < 6.0.

## Prompt Registry (v2)

All 12 prompts stored in `prompt_registry` table with versioning. Updated via `seed-data.sql` with `ON CONFLICT DO UPDATE`. Key prompts:

- Script V1: 50+ word scene_direction per segment, emphasis_words, emotion tags
- Script Critique: 8 dimensions (structure, pacing, hook, clarity, engagement, voice_fit, scene_direction_quality, audience_retention_curve)
- Direction: Frame-accurate per-segment (camera, text_strategy, motion_design, audio_cues, background_strategy)
- Thumbnail: 200+ word DALL-E prompts, text_style, composition_rule

## Rewrite Loop Pattern

```python
for attempt in range(max_rewrites):
    result = await generate(...)
    critique = await critique(result)
    if critique.overall >= threshold:
        break
    # Feed critique back for targeted rewrite
```

## Composite Score Calculation

Weighted average of all gate scores. Weights from `system_config.composite_score_weights` JSON.
If composite < 8.5 → signal for human review via Temporal.
