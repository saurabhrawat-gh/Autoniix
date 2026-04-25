# Architecture Option 2: Enhanced Monolith (Pure n8n)

> Self-hosted n8n | Fish Audio TTS | PostgreSQL (optional) | All logic in n8n
> Build time: 4 weeks | Best for: 1-15 channels

---

## Overview

This is the **original 582-node architecture** enhanced with critical improvements:
- **Fish Audio** replaces ElevenLabs (77-89% cheaper)
- **PostgreSQL** replaces Google Sheets (optional — can start with Sheets, migrate later)
- **Better error handling** across all workflows
- **Improved checkpoint/resume** system
- **API cost tracking** built into every workflow

Everything runs inside n8n. No external services, no Docker containers, no additional frameworks.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  Hetzner VPS (n8n Self-Hosted)               │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    n8n Engine                          │   │
│  │                                                        │   │
│  │  Workflow A:  Control & Scheduling        (35 nodes)  │   │
│  │  Workflow B1: Research & Ideation        (155 nodes)  │   │
│  │  Workflow B2: Asset Generation           (110 nodes)  │   │
│  │  Workflow B3: Thumbnail Generation        (42 nodes)  │   │
│  │  Workflow B4: Assembly & QA               (87 nodes)  │   │
│  │  Workflow C:  Delivery                    (18 nodes)  │   │
│  │  Workflow D:  Virality Intelligence       (50 nodes)  │   │
│  │  Workflow E:  Trend Intelligence          (40 nodes)  │   │
│  │  Admin:       Control                     (10 nodes)  │   │
│  │  + Checkpoint / Error Handling            (35 nodes)  │   │
│  │                                                        │   │
│  │  TOTAL: ~582 nodes across 9 workflows                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │ PostgreSQL   │  │ Remotion     │                         │
│  │ (optional)   │  │ (renderer)   │                         │
│  │              │  │              │                         │
│  │ OR: Google   │  │ Same VPS or  │                         │
│  │    Sheets    │  │ separate     │                         │
│  └──────────────┘  └──────────────┘                         │
└─────────────────────────────────────────────────────────────┘

External APIs:
  ├─ Fish Audio (TTS)
  ├─ OpenAI (GPT-4o, GPT-4o-mini, DALL-E 3, Vision)
  ├─ Anthropic (Claude Sonnet)
  ├─ Google (Gemini Flash)
  ├─ SerpAPI (research)
  ├─ Pixabay / Pexels (stock footage)
  ├─ Freesound (music/SFX)
  └─ YouTube Data API
```

---

## Enhancements Over Original Architecture

### Enhancement 1: Fish Audio (replaces ElevenLabs)

**Changes in Workflow B2 (Voice Engine, ~28 nodes):**

| Original Node | Enhanced Node | Change |
|---------------|--------------|--------|
| ElevenLabs Quota Check | Fish Audio Credit Check | `GET https://api.fish.audio/v1/user` |
| Build ElevenLabs Request | Build Fish Audio Request | Different API format |
| ElevenLabs TTS | Fish Audio TTS | `POST https://api.fish.audio/v1/tts` |
| Parse Voice | Parse Fish Audio Response | Extract audio + timestamps |

**Fish Audio API Integration:**

```javascript
// n8n Code Node: Build Fish Audio Request
const scene = $input.first().json;
return [{
  json: {
    url: 'https://api.fish.audio/v1/tts',
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${$credentials.fishAudioApiKey}`,
      'Content-Type': 'application/json'
    },
    body: {
      text: scene.narration_text,
      reference_id: scene.voice_id,  // Fish Audio voice model ID
      format: 'mp3',
      mp3_bitrate: 128,
      normalize: true,
      latency: 'normal'  // 'normal' for best quality
    }
  }
}];
```

**Key differences from ElevenLabs:**
- Fish Audio uses `reference_id` (voice model) instead of `voice_id`
- Supports voice cloning with just 15 seconds of audio
- Credits-based billing (~625 credits/minute of audio)
- No SSML support natively — emotion control via prompt engineering
- Word-level timestamps available via separate ASR call if needed

**Emotion Handling Without SSML:**
Since Fish Audio doesn't support SSML markup like ElevenLabs, emotion is controlled via:
1. **Prompt-based emotion:** Prepend emotion hints to the text (Fish Audio's model responds to tone)
2. **Voice reference selection:** Create multiple voice references per channel (calm, excited, serious)
3. **Post-processing:** Apply volume/speed adjustments in Remotion

### Enhancement 2: PostgreSQL Option (replaces Google Sheets)

**Two paths — choose based on comfort level:**

#### Path A: Keep Google Sheets (simplest, no change)
- Pros: No migration, familiar, visual
- Cons: 60 req/min rate limit, no indexing, race conditions at scale
- **Recommended for:** 1-3 channels, getting started fast

#### Path B: Migrate to PostgreSQL (recommended for 5+ channels)
- Pros: No rate limits, indexing, transactions, ACID compliance
- Cons: Need to set up + maintain PostgreSQL
- **Recommended for:** 5+ channels, long-term operation

**n8n has built-in PostgreSQL nodes.** Replace every `googleSheets` node with `postgres` node:

```
Original:  Google Sheets Read → Filter → Process
Enhanced:  PostgreSQL Execute → (data already filtered via SQL) → Process
```

This actually REDUCES node count because SQL handles filtering that currently needs code nodes:
```sql
-- One query replaces 3 nodes (Read + Filter Active + Check Schedule)
SELECT * FROM channels
WHERE status = 'active'
AND timezone_day_match(timezone, weekly_day, NOW()) = true;
```

**Estimated node reduction with PostgreSQL: ~582 → ~520 nodes** (saving ~60 filter/parse nodes).

### Enhancement 3: Improved Error Handling

**Add to every workflow (built into the ~35 checkpoint nodes):**

```javascript
// n8n Code Node: Universal Error Handler
// Place after every HTTP Request node
const response = $input.first().json;
const maxRetries = 3;
const currentRetry = $json.retry_count || 0;

if (response.error || response.statusCode >= 400) {
  if (currentRetry < maxRetries) {
    // Exponential backoff
    const waitMs = Math.pow(2, currentRetry) * 1000;
    await new Promise(r => setTimeout(r, waitMs));
    return [{ json: { ...response, retry_count: currentRetry + 1, action: 'retry' } }];
  }
  // Max retries exceeded — save state and notify
  return [{ json: { action: 'checkpoint_save', error: response.error } }];
}
return [{ json: { ...response, action: 'continue' } }];
```

### Enhancement 4: API Cost Tracking (add ~5 nodes per workflow)

```javascript
// n8n Code Node: Track API Cost (add after every LLM call)
const usage = $input.first().json.usage;
const model = 'gpt-4o'; // or 'claude-sonnet', 'gemini-flash'

const costs = {
  'gpt-4o': { input: 2.50 / 1e6, output: 10.00 / 1e6 },
  'gpt-4o-mini': { input: 0.15 / 1e6, output: 0.60 / 1e6 },
  'claude-sonnet': { input: 3.00 / 1e6, output: 15.00 / 1e6 },
  'gemini-flash': { input: 0.075 / 1e6, output: 0.30 / 1e6 }
};

const cost = (usage.prompt_tokens * costs[model].input) +
             (usage.completion_tokens * costs[model].output);

return [{ json: {
  model, cost: cost.toFixed(6),
  tokens_in: usage.prompt_tokens,
  tokens_out: usage.completion_tokens,
  content_id: $json.content_id
}}];
```

### Enhancement 5: Circuit Breaker Pattern

Add a code node at the start of each workflow section:

```javascript
// Check if an API provider is currently failing
const provider = 'openai'; // or 'fish_audio', 'serpapi'
const failKey = `circuit_breaker_${provider}`;
const failures = parseInt(await $getWorkflowStaticData('global')[failKey] || '0');
const lastFail = $getWorkflowStaticData('global')[`${failKey}_time`] || 0;

// If 5+ failures in last 10 minutes, open circuit
if (failures >= 5 && (Date.now() - lastFail) < 600000) {
  return [{ json: { action: 'circuit_open', provider, message: 'API provider failing, skipping' } }];
}
return [{ json: { action: 'continue' } }];
```

---

## Fish Audio Plan Selection

| Channels | Plan | Price/month | Credits/month | Usage (Month 3+) | Headroom |
|----------|------|------------|---------------|-------------------|----------|
| 1 | Plus | $11 | 250,000 | ~49,400 | 80% free |
| 3 | Plus | $11 | 250,000 | ~148,200 | 41% free |
| 5 | Plus | $11 | 250,000 | ~247,000 | ~1% free |
| 10 | Pro | $75 | 2,000,000 | ~494,000 | 75% free |

### Credit Calculation

```
Per minute of generated audio ≈ 625 credits

Long-form (8 min):  5,000 credits/video
Short-form (45 sec): 469 credits/video

Per channel per month (Month 3+: 2L + 3S/week):
  Long:  8.66 × 5,000 = 43,300 credits
  Short: 12.99 × 469  = 6,093 credits
  Total: ~49,393 credits/channel/month
```

---

## Cost Estimation

### Per-Video Costs

| Component | Long-form ($) | Short-form ($) |
|-----------|:------------:|:-------------:|
| GPT-4o (v3, direction, fact-check) | 0.35 | — |
| Claude Sonnet (script, audience sim) | 0.16 | 0.12 |
| Gemini Flash (research, QC) | 0.05 | 0.03 |
| GPT-4o-mini (tags, desc, critique) | 0.04 | 0.02 |
| GPT-4o Vision (thumbnail QC) | 0.05 | — |
| DALL-E 3 (2 thumbnails) | 0.08 | — |
| SerpAPI (3 queries) | 0.03 | 0.03 |
| Fish Audio (included in plan) | 0.00 | 0.00 |
| **Total per video** | **$0.76** | **$0.20** |

### Monthly Variable Cost per Channel

| Phase | Long-form | Shorts | Total/channel |
|-------|----------|--------|---------------|
| Month 1-2 (1L+7S/wk) | $3.29 | $6.06 | **$9.35** |
| Month 3+ (2L+3S/wk) | $6.58 | $2.60 | **$9.18** |

---

### Complete Cost: 1 Channel

#### Option A: Google Sheets (simplest start)

| Component | Month 1-2 | Month 3+ | Notes |
|-----------|----------|---------|-------|
| Hetzner CX21 (n8n only) | $7 | $7 | 2 vCPU, 4GB — sufficient for 1 channel |
| Fish Audio Plus | $11 | $11 | 250K credits |
| LLM variable | $9.35 | $9.18 | |
| SerpAPI | $0 | $0 | Free tier (100 searches) |
| Google Sheets | $0 | $0 | Free |
| Remotion (skip initially) | $0 | $0 | Use FFmpeg in code nodes for MVP |
| Misc | $2 | $2 | |
| **TOTAL** | **$29** | **$29** | **Absolute minimum** |

#### Option B: With PostgreSQL + Remotion

| Component | Month 1-2 | Month 3+ | Notes |
|-----------|----------|---------|-------|
| Hetzner CX31 (n8n + PostgreSQL + Remotion) | $18 | $18 | All on one VPS |
| Fish Audio Plus | $11 | $11 | |
| LLM variable | $9.35 | $9.18 | |
| SerpAPI | $0 | $0 | Free tier |
| Misc | $2 | $2 | |
| **TOTAL** | **$40** | **$40** | **Production-ready** |

### Complete Cost: 3 Channels

| Component | Month 1-2 | Month 3+ | Notes |
|-----------|----------|---------|-------|
| Hetzner CX31 (n8n + DB + Remotion) | $18 | $18 | Single VPS still works |
| Fish Audio Plus | $11 | $11 | 250K credits, 41% headroom |
| LLM variable (×3) | $28.05 | $27.54 | |
| SerpAPI | $0 | $0 | Free tier (~195 searches at steady) |
| Misc | $3 | $3 | |
| **TOTAL** | **$60** | **$60** | **$20/channel** |

### Complete Cost: 5 Channels

| Component | Month 1-2 | Month 3+ | Notes |
|-----------|----------|---------|-------|
| Hetzner CX31 (n8n + DB) | $18 | $18 | |
| Hetzner CX21 (Remotion) | $7 | $7 | Separate render server |
| Fish Audio Plus | $11 | $11 | At limit month 3+ (247K/250K) |
| LLM variable (×5) | $46.75 | $45.90 | |
| SerpAPI Basic | $50 | $50 | 5K searches (325 needed) |
| Misc | $5 | $5 | |
| **TOTAL** | **$138** | **$137** | **$27/channel** |

> ⚠️ At 5 channels, n8n may approach memory limits running 582 nodes with concurrent
> executions. Consider upgrading to CX41 ($36) if execution failures occur.

### Complete Cost: 10 Channels

| Component | Month 1-2 | Month 3+ | Notes |
|-----------|----------|---------|-------|
| Hetzner CX41 (n8n + DB) | $36 | $36 | 8 vCPU, 16GB — needed for 582 nodes × 10ch |
| Hetzner CX31 (Remotion) | $24 | $24 | Dedicated render server |
| Fish Audio Pro | $75 | $75 | 2M credits |
| LLM variable (×10) | $93.50 | $91.80 | |
| SerpAPI Basic | $50 | $50 | 5K searches (650 needed) |
| Misc | $10 | $10 | |
| **TOTAL** | **$289** | **$287** | **$29/channel** |

> ⚠️ 10 channels is near the ceiling for this architecture. n8n running 582 nodes with
> concurrent workflows for 10 channels will stress a CX41. Beyond 10-15 channels,
> consider the Hybrid architecture (Doc 09).

---

### Cost Summary Table

| Channels | Monthly Cost | Per Channel | vs Original (ElevenLabs) | Savings |
|----------|-------------|------------|--------------------------|---------|
| **1** | **$29-40** | $29-40 | ~$142 | **72-80%** |
| **3** | **$60** | $20 | ~$178 | **66%** |
| **5** | **$138** | $28 | ~$230 | **40%** |
| **10** | **$289** | $29 | ~$328 | **12%** |

### Cumulative Cost (First 12 Months, 1 Channel, Option A)

| Month | Monthly | Cumulative | Revenue Est. | Net |
|-------|---------|-----------|-------------|-----|
| 1-2 | $29 | $58 | $0 | -$58 |
| 3-4 | $29 | $116 | $0 | -$116 |
| 5-6 | $29 | $174 | $0-50 | -$124 |
| 7-9 | $29 | $261 | $50-200 | -$61 |
| 10-12 | $29 | $348 | $100-400 | +$52 to +$452 |

**Break-even: Month 9-11 with 1 channel (Option A).**

---

## Pros & Cons

### Pros
- ✅ **Lowest possible cost** ($29/month for 1 channel)
- ✅ Simplest to build (4 weeks)
- ✅ No Docker, no external services, no extra infrastructure
- ✅ Visual workflow debugging in n8n UI
- ✅ All existing documentation (02-WORKFLOW-NODES.md) applies directly
- ✅ Can start with Google Sheets, migrate to PostgreSQL later
- ✅ Fish Audio saves $88+/month vs ElevenLabs

### Cons
- ❌ **Hard ceiling: ~10-15 channels** (n8n memory/CPU limits)
- ❌ No fault isolation (one bad node can crash entire workflow)
- ❌ 582 nodes is complex to debug when things go wrong
- ❌ No caching (every API call is fresh, no Redis)
- ❌ Sequential processing (can't parallelize channels effectively)
- ❌ Google Sheets rate limits (if not using PostgreSQL)
- ❌ Difficult to swap components (LLM provider change = edit 50+ nodes)
- ❌ No plug-in/plug-out capability
- ❌ Major rewrite needed to scale beyond 15 channels

---

## Limitations & Ceiling

| Metric | Limit | Why |
|--------|-------|-----|
| **Max channels** | ~10-15 | n8n memory: 582 nodes × concurrent executions |
| **Max concurrent videos** | 2-3 | n8n execution queue, VPS CPU |
| **Max videos/day** | ~5-7 | Sequential processing bottleneck |
| **Data scalability** | ~5K rows (Sheets) / unlimited (PostgreSQL) | Sheets API rate limits |
| **API failure recovery** | Basic (n8n retry) | No circuit breakers, no dead letter queue |
| **Component swappability** | Low | Changing voice provider = edit 28 nodes manually |
| **Observability** | n8n UI only | No metrics, no distributed tracing |

### When to Upgrade

**Move to Hybrid (Doc 09) when ANY of these occur:**
- n8n execution failures due to memory/CPU
- Need >3 concurrent video pipelines
- Want to swap LLM/voice providers without editing dozens of nodes
- Need caching to reduce API costs
- Approaching 10 channels and planning to grow

---

## Build Timeline

| Week | Deliverable |
|------|------------|
| 1 | Workflow A (Control, 35 nodes) + Google Sheets setup + Fish Audio credential |
| 2 | Workflow B1 (Research & Ideation, 155 nodes) — biggest workflow |
| 3 | Workflow B2 (Assets, 110 nodes) + B3 (Thumbnail, 42 nodes) + Remotion MVP |
| 4 | Workflow B4 (Assembly, 87 nodes) + C (Delivery, 18 nodes) + first video |
| Post | D (Intelligence, 50 nodes) + E (Trends, 40 nodes) + Admin (10 nodes) |

---

## Migration Path to Hybrid

When ready to scale beyond 10-15 channels:

1. **Week 1:** Set up Docker Compose, PostgreSQL, Redis on new/same VPS
2. **Week 2:** Extract B1 logic into Research + Script services
3. **Week 3:** Extract B2 logic into Voice + Assets services
4. **Week 4:** Extract B4 logic into Assembly service, simplify n8n to ~50 nodes
5. **Result:** Hybrid architecture (Doc 09) — supports 50+ channels

The migration is incremental: extract one service at a time while n8n continues running.
