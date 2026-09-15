# Quality Gates & Compliance

> 30+ quality gates enforced across Temporal activities. Anti-inflation scoring. Human review via workflow signals. Content fingerprinting for cross-channel dedup.

---

## All Quality Gates

| #   | Gate                        | Service      | Hard Threshold         | Retry | Fail Action              |
| --- | --------------------------- | ------------ | ---------------------- | ----- | ------------------------ |
| 1   | Research Depth              | Research     | ≥ 8.0                  | 2     | Proceed with warning     |
| 2   | Fact Confidence (per claim) | Research     | ≥ 0.7                  | 1     | Remove claim             |
| 3   | Idea Composite              | Research     | ≥ 7.5                  | 0     | STOP pipeline            |
| 4   | Script Structure            | Script       | Pass/Fail              | 1     | Rewrite                  |
| 5   | Word Count                  | Script       | ±15% of target         | 1     | Rewrite                  |
| 6   | Forbidden Words             | Script       | 0 violations           | 1     | Auto-remove + rewrite    |
| 7   | Script Critic (per dim)     | Script       | ≥ 6.0 each             | 2     | Rewrite targeted section |
| 8   | Script Overall              | Script       | ≥ 8.0                  | 2     | Human review signal      |
| 9   | Hook Retention              | Script       | ≥ 8.0                  | 2     | Regenerate hook          |
| 10  | Title-Script Alignment      | Script       | ≥ 7.5                  | 1     | Rewrite title            |
| 11  | Clickbait Check             | Script       | ≥ 8.0 authenticity     | 0     | Block                    |
| 12  | Policy Compliance           | Script       | Risk = low             | 0     | Human review signal      |
| 13  | Voice Duration              | Voice        | ±20% of target         | 2     | Adjust speed param       |
| 14  | Voice Word Count            | Voice        | 100% of narrated words | 1     | Regenerate scene         |
| 15  | Voice Pace (WPM)            | Voice        | 130-170 WPM            | 1     | Adjust target_wpm        |
| 16  | Stock Relevance             | Assets       | ≥ 7.0 per clip         | 2     | Backup search terms      |
| 17  | Asset Diversity             | Assets       | ≥ 3 visual styles      | 0     | Warn (proceed)           |
| 18  | Music-Scene Fit             | Assets       | ≥ 7.0                  | 1     | Select different track   |
| 19  | License Compliance          | Assets       | All free/CC            | 0     | Block asset              |
| 20  | Thumbnail CTR Prediction    | Thumbnail    | ≥ 7.5                  | 2     | Regenerate concept       |
| 21  | Title-Thumb Alignment       | Thumbnail    | ≥ 7.5                  | 1     | Regenerate               |
| 22  | Mobile Readability          | Thumbnail    | Pass/Fail              | 1     | Increase text size       |
| 23  | Direction Coherence         | Assembly     | ≥ 8.5                  | 2     | Regenerate v3            |
| 24  | v3 Schema Validation        | Assembly     | Pass Zod schema        | 2     | Regenerate               |
| 25  | Timeline Continuity         | Assembly     | No gaps                | 1     | Fix gaps                 |
| 26  | All Asset URLs Exist        | Assembly     | 100%                   | 0     | Fallback assets          |
| 27  | Caption Timing              | Assembly     | ±200ms per word        | 1     | Recalculate from audio   |
| 28  | Production Inspector        | Assembly     | ≥ 8.0                  | 2     | Regenerate               |
| 29  | **Final Composite**         | **Assembly** | **≥ 8.0**              | **0** | **Human review signal**  |
| 30  | Strike Risk                 | Assembly     | All risk < 3           | 0     | Human review signal      |
| 31  | Cross-Channel Similarity    | Assembly     | < 40%                  | 0     | **BLOCK**                |
| 32  | AI Disclosure Present       | Delivery     | Required               | 0     | Inject automatically     |
| 33  | Niche Disclaimer Present    | Delivery     | If health/finance      | 0     | Inject automatically     |

---

## Anti-Inflation Measures

Quality score inflation is a critical risk — AI scorers tend to give higher scores over time. Five countermeasures:

### 1. Adversarial Scoring Prompts

All QC scoring prompts include:

```
You are a harsh but fair critic. You rarely give scores above 7.
A score of 9+ means genuinely exceptional — better than 95% of YouTube content in this niche.
A score of 5 is average. Most AI-generated content scores 4-6.
```

### 2. Calibration Examples

Every scoring prompt includes reference examples:

```json
{
  "calibration": {
    "score_3": "Generic script with obvious AI phrasing, no unique angle, factual errors",
    "score_5": "Competent script, correct facts, but predictable structure, no surprise",
    "score_7": "Good script with clear voice, strong hook, 1-2 unique insights",
    "score_9": "Exceptional — would outperform 90% of human-written scripts in niche"
  }
}
```

### 3. Separate Generator and Judge

| Task              | Generator Model | Judge Model                                |
| ----------------- | --------------- | ------------------------------------------ |
| Script writing    | Claude Sonnet   | GPT-4o-mini (critique) + Gemini Flash (QC) |
| Fact checking     | GPT-4o          | Gemini Flash (verify sources)              |
| Thumbnail concept | GPT-4o          | GPT-4o Vision (visual QC)                  |
| Direction v3      | GPT-4o          | Gemini Flash (schema + coherence)          |

Generator and judge are **always different models** to prevent self-reinforcing bias.

### 4. Score Distribution Tracking

```python
# Analytics Service: weekly distribution check
async def check_score_inflation(channel_id: str, weeks: int = 4):
    scores = await db.fetch_all(
        "SELECT scores->>'overall' as score FROM videos "
        "WHERE channel_id = $1 AND created_at > NOW() - INTERVAL '$2 weeks' "
        "ORDER BY created_at",
        channel_id, weeks,
    )

    avg = statistics.mean(scores)
    if avg > 8.5:
        # Scores are inflating — tighten thresholds
        await db.execute(
            "UPDATE system_config SET config_value = $1 WHERE config_key = 'quality_threshold'",
            str(min(float(current_threshold) + 0.5, 9.0)),
        )
        return {"action": "threshold_raised", "new_threshold": current_threshold + 0.5}

    return {"action": "none", "avg_score": avg}
```

### 5. Suspicious Score Detection

If any scorer gives a 10/10, flag as suspicious and re-score with a different model.

---

## Failure Points & Mitigations

### Provider Failures

| Failure                   | Probability       | Severity | Mitigation                                                                      |
| ------------------------- | ----------------- | -------- | ------------------------------------------------------------------------------- |
| OpenAI rate limit         | Medium            | Medium   | Temporal retry (3×, backoff), circuit breaker at 5 failures                     |
| GPT JSON parse failure    | High (10-15%)     | Low      | Strip fences, Pydantic validation, retry with stricter prompt                   |
| Fish Audio TTS error      | Low               | Medium   | Retry 3×, fallback to Google TTS (via TTSProvider interface)                    |
| DALL-E content rejection  | Medium (5-10%)    | Low      | Sanitize prompt, 3 concept fallbacks, stock image backup                        |
| Remotion render crash     | Low-Medium        | High     | Health check activity, 20min timeout, heartbeat every 2min, retry simplified v3 |
| Pixabay/Pexels rate limit | Low               | Medium   | Token bucket rate limiter, batch terms, Redis cache                             |
| YouTube upload quota      | Medium (at scale) | High     | Queue uploads, respect daily quota, exponential backoff                         |
| SerpAPI quota exhaustion  | Medium            | Medium   | Cache results (7d TTL), degrade to Google Custom Search                         |

### AI Quality Failures

| Failure                    | Probability    | Severity | Mitigation                                                |
| -------------------------- | -------------- | -------- | --------------------------------------------------------- |
| Hallucinated facts         | High (20-30%)  | CRITICAL | Claim extractor + fact verifier + source confidence ≥ 0.7 |
| Fact-checker hallucination | Medium         | CRITICAL | Temp 0.1, cross-ref web data, flag statistics for human   |
| Quality score inflation    | High (ongoing) | Medium   | Anti-inflation measures (see above)                       |
| Brand voice drift          | Slow (weeks)   | Medium   | Golden paragraphs in Channel_DNA, consistency scoring     |
| Repetitive structures      | Medium         | Medium   | Template rotation, pattern tracking in Performance_Memory |
| Prompt injection via data  | Very Low       | Medium   | Sanitize all DB inputs, validate JSON schemas at boundary |

### Infrastructure Failures

| Failure               | Probability       | Severity | Mitigation                                                      |
| --------------------- | ----------------- | -------- | --------------------------------------------------------------- |
| Temporal server crash | Low               | High     | Docker restart policy: `always`, persistence in PostgreSQL      |
| Worker process crash  | Low               | Medium   | Temporal automatically re-dispatches activities                 |
| PostgreSQL down       | Very Low          | CRITICAL | Docker health check, auto-restart, daily pg_dump backup         |
| Redis down            | Low               | Medium   | Fallback: skip cache (slower but functional), auto-restart      |
| MinIO down            | Low               | High     | Versioning enabled, backup to external S3 weekly                |
| VPS out of memory     | Medium (at scale) | High     | Resource limits per container, monitoring alerts, scaling guide |
| Network partition     | Very Low          | High     | Temporal handles: workflow pauses, resumes when services return |

### Content Compliance Failures

| Failure                           | Probability       | Severity | Mitigation                                          |
| --------------------------------- | ----------------- | -------- | --------------------------------------------------- |
| YouTube policy violation          | Low-Medium        | CRITICAL | Policy scanner activity, niche-specific rules       |
| Cross-channel similarity          | Medium (at 100ch) | CRITICAL | Content fingerprinting + similarity < 40% gate      |
| Missing AI disclosure             | N/A               | High     | Auto-injected by Delivery Service (never forgotten) |
| Missing health/finance disclaimer | N/A               | High     | Auto-injected based on channel niche                |
| Copyright in stock footage        | Low               | HIGH     | License validation gate; only free/CC assets        |

---

## Human-in-the-Loop via Temporal Signals

### Trigger Conditions

A human review signal is sent when:

1. Final composite score < 8.0
2. Policy risk != "low"
3. Strike risk >= 3 on any dimension
4. Any gate marked "Human review" fails

### Notification Payload

```json
{
  "type": "human_review_required",
  "content_id": "VID_BS001_20250425_001",
  "channel_id": "BS001",
  "topic": "4 Types of Shivers",
  "score": 7.6,
  "failed_gates": ["direction_coherence"],
  "artifacts": {
    "script_url": "s3://yt-automation/scripts/.../script_base.json",
    "thumbnail_url": "s3://yt-automation/thumbnails/.../final.png",
    "quality_report_url": "s3://yt-automation/scripts/.../qa_report.json"
  },
  "actions": {
    "approve": "POST /api/videos/video-BS001-20250425-1030/approve {\"approved\": true}",
    "reject": "POST /api/videos/video-BS001-20250425-1030/approve {\"approved\": false}"
  },
  "timeout": "48 hours"
}
```

### Review Scaling

| Video Count   | Review Policy                  | Threshold      |
| ------------- | ------------------------------ | -------------- |
| 1-10          | ALL videos require approval    | Score override |
| 11-50         | Only if score < 8.0            | Standard       |
| 51-200        | Only if score < 7.5            | Relaxed        |
| 200+          | Only if score < 7.0 or anomaly | Minimal        |
| 100+ channels | 10% random audit               | Random sample  |

Thresholds are stored in `system_config` and adjustable via Admin API.

---

## Content Fingerprinting & Cross-Channel Dedup

### Fingerprint Generation

```python
import hashlib

def generate_fingerprint(script_base: dict) -> str:
    """Generate content fingerprint for cross-channel dedup."""
    # Combine: topic angle + key claims + structure
    components = [
        script_base["title"].lower(),
        " ".join(s["text_raw"][:100] for s in script_base["scenes"][:3]),
        " ".join(c["text"] for s in script_base["scenes"] for c in s.get("claims", [])[:2]),
    ]
    text = "|".join(components)
    return hashlib.sha256(text.encode()).hexdigest()
```

### Similarity Check

```python
async def check_cross_channel_similarity(fingerprint: str, channel_id: str) -> float:
    """Check if similar content exists on other channels."""
    existing = await redis.get(f"dedup:fingerprint:{fingerprint}")
    if existing and existing.decode() != channel_id:
        return 1.0  # Exact match on different channel → block

    # Fuzzy check: compare against recent fingerprints
    recent = await db.fetch_all(
        "SELECT content_fingerprint, channel_id FROM videos "
        "WHERE channel_id != $1 AND created_at > NOW() - INTERVAL '90 days'",
        channel_id,
    )

    max_similarity = 0.0
    for row in recent:
        sim = compute_jaccard_similarity(fingerprint, row["content_fingerprint"])
        max_similarity = max(max_similarity, sim)

    return max_similarity
```

Gate: `similarity < 0.40` → pass. `≥ 0.40` → **BLOCK** (content too similar across channels).
