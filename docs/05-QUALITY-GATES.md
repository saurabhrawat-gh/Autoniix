# Quality Gates & Failure Points

---

## All Quality Gates

| Gate | Location | Hard Threshold | Retry | Fail Action |
|------|----------|---------------|-------|-------------|
| Research Depth | B1 | ≥8.0 | 2 | Proceed with warning |
| Fact Confidence (per claim) | B1 | ≥0.7 | 1 | Remove claim |
| Idea Composite | B1 | ≥7.5 | 0 | STOP pipeline |
| Script Structure | B1 | Pass/Fail | 1 | Rewrite |
| Word Count | B1 | ±15% | 1 | Rewrite |
| Forbidden Words | B1 | 0 violations | 1 | Auto-remove |
| Script Critic (per dim) | B1 | ≥6.0 each | 2 | Rewrite targeted |
| Script Overall | B1 | ≥8.0 | 2 | Human review |
| Hook Retention | B1 | ≥8.0 | 2 | Regenerate |
| Title-Script Alignment | B1 | ≥7.5 | 1 | Rewrite title |
| Clickbait Check | B1 | ≥8.0 | 0 | Block |
| Policy Compliance | B1 | Risk=low | 0 | Human review |
| Voice Duration | B2 | ±20% | 2 | Adjust speed |
| Voice Word Count | B2 | 100% | 1 | Regenerate |
| Voice Pace (WPM) | B2 | 130-170 | 1 | Adjust |
| Stock Relevance | B2 | ≥7.0/clip | 2 | Backup search |
| Asset Diversity | B2 | ≥3 styles | 0 | Warn |
| Music-Scene Fit | B2 | ≥7.0 | 1 | Different track |
| Thumbnail CTR | B3 | ≥7.5 | 2 | Regenerate |
| Title-Thumb Alignment | B3 | ≥7.5 | 1 | Regenerate |
| Mobile Readability | B3 | Pass/Fail | 1 | Increase text |
| Direction Coherence | B4 | ≥8.5 | 2 | Regenerate |
| v3 Schema | B4 | Pass/Fail | 2 | Regenerate |
| Timeline Continuity | B4 | No gaps | 1 | Fix |
| Asset Reference | B4 | All exist | 0 | Fallback |
| Caption Timing | B4 | Pass/Fail | 1 | Recalculate |
| Production Inspector | B4 | ≥8.0 | 2 | Regenerate |
| **Final Composite** | **B4** | **≥8.0** | **0** | **Human review** |
| Strike Risk | B4 | All <3 | 0 | Human review |
| Cross-Channel Similarity | B4 | <40% | 0 | BLOCK |

### Anti-Inflation Measures

1. QC models use adversarial prompts: "You rarely score above 7."
2. Calibration examples in every QC (what 3/10, 5/10, 7/10, 9/10 looks like)
3. Generator and judge ALWAYS different models
4. Track score distributions weekly → auto-adjust thresholds if inflated
5. If inspector gives 10/10 → flag as suspicious

---

## Failure Points & Mitigations

### API Failures

| Failure | Probability | Severity | Mitigation |
|---------|------------|----------|-----------|
| OpenAI rate limit | Medium | Medium | retryOnFail: true, maxTries: 3, wait 10s |
| GPT JSON parse failure | High (10-15%) | Low | Strip fences, try/catch, retry with stricter prompt |
| YouTube API quota exhaustion | Medium (at scale) | Medium | Cache competitor data weekly, quota tracking, degrade gracefully |
| ElevenLabs char limit | Medium | HIGH | Pre-check quota, STOP if insufficient, track per-video |
| DALL-E content rejection | Medium (5-10%) | Low | Sanitize prompt, 3 concepts (fallback), stock image backup |
| Remotion server crash | Low-Medium | HIGH | Health check first, 30min timeout, retry simplified |
| Pixabay/Pexels rate limit | Low | Medium | Rate limiter (600ms), batch similar terms, cache |

### GPT Quality Failures

| Failure | Probability | Severity | Mitigation |
|---------|------------|----------|-----------|
| Hallucinated facts | High (20-30%) | CRITICAL | Claim extractor + fact verifier + source confidence |
| Fact-checker hallucination | Medium | CRITICAL | Temp 0.1, cross-ref web data, flag stats for human |
| Quality score inflation | High (ongoing) | Medium | Adversarial prompts, calibration, distribution tracking |
| Brand voice drift | Slow (weeks) | Medium | Golden paragraphs, consistency check, periodic audit |
| Repetitive structures | Medium | Medium | Template rotation, pattern tracking, novelty scoring |

### Data & State Failures

| Failure | Probability | Severity | Mitigation |
|---------|------------|----------|-----------|
| Sheets concurrent write | Low (1-3ch) | Medium | content_id idempotency, sequential writes, _last_modified_by |
| B4 race condition | Low (5%) | High | Flag+read pattern, assembly_started_at mutex, 2-3s delay |
| Webhook delivery failure | Low (1-2%) | High | retryOnFail: 3, watchdog in A every 6h |
| Stale performance memory | Medium | Medium | still_valid flag, 90-day auto-expire, re-validate weekly |
| Lock expiry during execution | Low | Medium | 24h TTL, B4 refreshes lock, check Output_Log before create |
| Data loss (sheets) | Low | HIGH | Weekly CSV backup to Drive |

### Content Quality Failures

| Failure | Probability | Severity | Mitigation |
|---------|------------|----------|-----------|
| Title-thumb-script misalignment | Medium (15-20%) | HIGH | Alignment inspector, hard threshold ≥8 |
| Repetitive content | Medium | Medium | Output_Log dedup, structure rotation, Performance_Memory |
| Voice monotone | Medium | Medium | Per-sentence SSML, pace variation, dual voice |
| Visual-audio mismatch | Medium | Medium | GPT relevance scorer per clip, SFX placement validator |
| YouTube policy violation | Low-Medium | CRITICAL | Policy inspector, niche compliance, AI disclosure |
| Cross-channel similarity | Medium (at 100ch) | CRITICAL | Fingerprint + dedup, different voices/templates/prompts |

### System Failures

| Failure | Probability | Severity | Mitigation |
|---------|------------|----------|-----------|
| n8n execution timeout | Medium | High | Split sub-workflows, checkpoint saves |
| n8n memory limit | Medium | High | Trim payload between sections, store large data to Drive |
| Cost runaway | Low | HIGH | max_daily_api_spend, per-video cost estimator, budget gates |
| Cascading failure | Low | HIGH | Each workflow handles own failures, watchdog, notifications |
| Prompt injection | Very Low | Medium | Sanitize all Sheet data, validate patterns |

---

## Manual Review Points (Human-in-the-Loop)

### Recommended Checkpoints

| When | What You Review | Time | Impact |
|------|----------------|------|--------|
| After Idea Selection (B1) | Title + hook + angle | 30s | Prevents bad topic (saves downstream cost) |
| After Script v1 Final (B1) | Full script + scores | 3-5 min | Catches tone/factual issues |
| After Hook Selection (B1) | Top 3 hooks | 30s | Ensures strong opening |
| After Thumbnail Concepts (B3) | 3 concepts + DALL-E images | 1 min | Prevents bad thumbnails |
| After Final Assembly (B4) | Video URL + scores | 10 min watch | Final quality check |

### Review Scaling

- **First 10 videos:** ALL checkpoints (train the system)
- **Videos 11-50:** After Idea + After Final Assembly only
- **After 50 videos:** Final Assembly only (or auto if scores ≥8.5)
- **100 channels:** 10% random audit + anomaly detection

### How It Works

```
Pipeline → review point → writes to Output_Log (status="awaiting_review")
→ sends notification with download links + approve/reject buttons
→ pipeline STOPS

You: Approve → webhook → pipeline resumes
     Reject + notes → pipeline logs failure → ends
     Edit → changes in Sheet → click Resume
```
