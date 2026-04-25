# Complete Cost Analysis

> Self-hosted Temporal | Fish Audio PAYG | Hetzner VPS | All costs broken down for 1 to 100 channels.

---

## Pricing Sources (as of April 2026)

| Provider | Pricing Model | Rate |
|----------|--------------|------|
| **Fish Audio** | PAYG: $15 per 1M UTF-8 bytes | ≈ $0.0208/min of audio |
| **OpenAI GPT-4o** | Per token | $2.50/1M input, $10.00/1M output |
| **OpenAI GPT-4o-mini** | Per token | $0.15/1M input, $0.60/1M output |
| **Anthropic Claude Sonnet** | Per token | $3.00/1M input, $15.00/1M output |
| **Google Gemini 2.5 Flash** | Per token | $0.075/1M input, $0.30/1M output |
| **OpenAI DALL-E 3** | Per image (1024×1024) | $0.04/image |
| **SerpAPI** | Per search | Free: 100/mo, Basic $50: 5K/mo |
| **Hetzner CX21** | VPS (2 vCPU, 4GB) | $7/mo |
| **Hetzner CX31** | VPS (4 vCPU, 8GB) | $18-24/mo |
| **Hetzner CX41** | VPS (8 vCPU, 16GB) | $36/mo |
| **Hetzner CX51** | VPS (16 vCPU, 32GB) | $61/mo |
| **Temporal** | Self-hosted (OSS) | $0 license |
| **PostgreSQL** | Self-hosted | $0 (runs on VPS) |
| **Redis** | Self-hosted | $0 (runs on VPS) |
| **MinIO** | Self-hosted | $0 (runs on VPS) |

---

## Per-Video Cost Breakdown

### Long-Form Video (8 min, ~1100 words)

| Step | Provider | Model | Tokens In | Tokens Out | Cost |
|------|----------|-------|-----------|------------|------|
| Research synthesis | Google | Gemini Flash | 3,200 | 2,800 | $0.0011 |
| Fact verification | OpenAI | GPT-4o | 2,000 | 500 | $0.0100 |
| Script writing | Anthropic | Claude Sonnet | 4,500 | 3,200 | $0.0615 |
| Script critique | OpenAI | GPT-4o-mini | 3,000 | 1,500 | $0.0014 |
| Script rewrite (50% chance) | Anthropic | Claude Sonnet | 4,000 | 3,000 | $0.0285 |
| Hook generation (3 variants) | OpenAI | GPT-4o-mini | 1,000 | 1,500 | $0.0011 |
| Tags + description | OpenAI | GPT-4o-mini | 500 | 800 | $0.0006 |
| Audience simulation | Anthropic | Claude Sonnet | 2,000 | 1,000 | $0.0210 |
| Emotion mapping | OpenAI | GPT-4o-mini | 800 | 600 | $0.0005 |
| TTS (8 min audio) | Fish Audio | PAYG | — | — | $0.1664 |
| Asset relevance scoring | Google | Gemini Flash | 2,000 | 1,000 | $0.0005 |
| Thumbnail concepts (2) | OpenAI | GPT-4o | 1,000 | 800 | $0.0105 |
| DALL-E backgrounds (2) | OpenAI | DALL-E 3 | — | — | $0.0800 |
| Thumbnail QC | OpenAI | GPT-4o Vision | 1,500 | 500 | $0.0088 |
| Direction Engine (v3) | OpenAI | GPT-4o | 6,000 | 5,000 | $0.0650 |
| QC scoring (5 gates) | Google | Gemini Flash | 5,000 | 2,000 | $0.0010 |
| Production inspector | Google | Gemini Flash | 3,000 | 1,500 | $0.0007 |
| SerpAPI (3 queries) | SerpAPI | — | — | — | $0.0300 |
| **TOTAL per long-form** | | | | | **$0.49** |

### Short-Form Video (45 sec, ~80 words)

| Step | Provider | Model | Cost |
|------|----------|-------|------|
| Research (cached 70%) | Google | Gemini Flash | $0.0003 |
| Script writing | Anthropic | Claude Sonnet | $0.0120 |
| Script critique | OpenAI | GPT-4o-mini | $0.0005 |
| TTS (45 sec audio) | Fish Audio | PAYG | $0.0156 |
| Asset scoring | Google | Gemini Flash | $0.0003 |
| Direction v3 | OpenAI | GPT-4o | $0.0200 |
| QC scoring | Google | Gemini Flash | $0.0005 |
| SerpAPI (1 query, cached 50%) | SerpAPI | — | $0.0050 |
| **TOTAL per short-form** | | | **$0.054** |

---

## Monthly Volume per Channel

### Month 1-2 (Ramp-up: 1L + 7S/week)

| Type | Per week | Per month (4.33 wk) | Cost/video | Monthly cost |
|------|----------|---------------------|-----------|-------------|
| Long-form | 1 | 4.33 | $0.49 | $2.12 |
| Short-form | 7 | 30.31 | $0.054 | $1.64 |
| **Total per channel** | | | | **$3.76** |

### Month 3+ (Steady: 2L + 3S/week)

| Type | Per week | Per month (4.33 wk) | Cost/video | Monthly cost |
|------|----------|---------------------|-----------|-------------|
| Long-form | 2 | 8.66 | $0.49 | $4.24 |
| Short-form | 3 | 12.99 | $0.054 | $0.70 |
| **Total per channel** | | | | **$4.94** |

---

## Infrastructure Costs by Scale

### Tier: 1-3 Channels

| Component | Specs | Monthly |
|-----------|-------|---------|
| Main VPS (Temporal + services + DB + Redis + MinIO) | CX31 (4 vCPU, 8GB) | $18 |
| Remotion (same VPS, RENDER_CONCURRENCY=1) | Shared | $0 |
| **Infra subtotal** | | **$18** |

### Tier: 5 Channels

| Component | Specs | Monthly |
|-----------|-------|---------|
| Main VPS (Temporal + services + DB + Redis + MinIO) | CX31 | $18 |
| Render VPS (Remotion, dedicated) | CX21 (2 vCPU, 4GB) | $7 |
| **Infra subtotal** | | **$25** |

### Tier: 10 Channels

| Component | Specs | Monthly |
|-----------|-------|---------|
| Main VPS (Temporal + services) | CX31 | $18 |
| DB VPS (PostgreSQL + Redis + MinIO) | CX21 | $7 |
| Render VPS (Remotion) | CX31 | $24 |
| **Infra subtotal** | | **$49** |

### Tier: 25 Channels

| Component | Specs | Monthly |
|-----------|-------|---------|
| Main VPS (Temporal + services) | CX41 (8 vCPU, 16GB) | $36 |
| DB VPS (PostgreSQL + Redis + MinIO) | CX31 | $18 |
| Render VPS × 2 | 2× CX31 | $48 |
| **Infra subtotal** | | **$102** |

### Tier: 50 Channels

| Component | Specs | Monthly |
|-----------|-------|---------|
| Main VPS (Temporal + services) | CX51 (16 vCPU, 32GB) | $61 |
| DB VPS | CX41 | $36 |
| Render VPS × 3 | 3× CX31 | $72 |
| **Infra subtotal** | | **$169** |

### Tier: 100 Channels

| Component | Specs | Monthly |
|-----------|-------|---------|
| Services VPS × 3 | 3× CX41 | $108 |
| DB VPS (primary) | CX51 | $61 |
| DB VPS (read replica) | CX31 | $18 |
| Redis/MinIO VPS | CX21 | $7 |
| Render VPS × 4 | 4× CX31 | $96 |
| Load balancer/misc | | $10 |
| **Infra subtotal** | | **$300** |

---

## Complete Monthly Cost Tables

### SerpAPI Usage

| Channels | Queries/month (Month 3+) | Plan | Cost |
|----------|-------------------------|------|------|
| 1 | ~65 | Free (100) | $0 |
| 3 | ~195 | Free (tight) | $0 |
| 5 | ~325 | Basic (5K) | $50 |
| 10 | ~650 | Basic (5K) | $50 |
| 25 | ~1,625 | Basic (5K) | $50 |
| 50 | ~3,250 | Basic (5K) | $50 |
| 100 | ~6,500 | Business (15K) | $130 |

### Full Cost: Month 3+ Steady State

| Channels | Infra | LLM/API Variable | TTS (PAYG) | SerpAPI | Misc | **Monthly Total** | **Per Channel** |
|---------:|------:|------------------:|-----------:|--------:|-----:|-----------------:|----------------:|
| **1** | $18 | $4.94 | $1.65 | $0 | $2 | **$27** | **$27** |
| **3** | $18 | $14.82 | $4.95 | $0 | $3 | **$41** | **$14** |
| **5** | $25 | $24.70 | $8.25 | $50 | $5 | **$113** | **$23** |
| **10** | $49 | $49.40 | $16.50 | $50 | $8 | **$173** | **$17** |
| **25** | $102 | $123.50 | $41.25 | $50 | $15 | **$332** | **$13** |
| **50** | $169 | $247.00 | $82.50 | $50 | $25 | **$574** | **$11** |
| **100** | $300 | $494.00 | $165.00 | $130 | $40 | **$1,129** | **$11** |

### Full Cost: Month 1-2 Ramp-up

| Channels | Infra | LLM/API Variable | TTS (PAYG) | SerpAPI | Misc | **Monthly Total** |
|---------:|------:|------------------:|-----------:|--------:|-----:|-----------------:|
| **1** | $18 | $3.76 | $1.65 | $0 | $2 | **$25** |
| **3** | $18 | $11.28 | $4.95 | $0 | $3 | **$37** |
| **5** | $25 | $18.80 | $8.25 | $50 | $5 | **$107** |
| **10** | $49 | $37.60 | $16.50 | $50 | $8 | **$161** |

---

## Temporal Platform Cost

### Self-Hosted (Recommended)

| Item | Cost |
|------|------|
| Temporal Server license | **$0** (open source) |
| Infrastructure overhead | ~1-2 GB RAM, included in VPS cost |
| Temporal persistence DB | Shares PostgreSQL instance |
| Temporal Web UI | Included in Docker image |

**Total Temporal cost: $0** — included in VPS infrastructure costs above.

### Temporal Cloud (For Reference)

| Plan | Base Price | Included Actions | Included Storage |
|------|-----------|-----------------|-----------------|
| Essentials | $100/mo | 1M Actions | 1 GB Active, 40 GB Retained |
| Business | $500/mo | 2.5M Actions | 2.5 GB Active, 100 GB Retained |

At your scale (1-10 channels), you'd stay well under 1M Actions/month. The $100/mo base fee is the dominant cost, making self-host the clear winner.

**Action estimate per video:** ~20-30 Actions (start workflow, start activities, heartbeats, signals). At 10 channels with 21.65 videos/month each = ~6,500 Actions/month — 0.65% of the free allocation.

---

## Fish Audio: PAYG vs Plans

| Metric | PAYG ($15/1M bytes) | Plus ($11/mo) | Pro ($75/mo) |
|--------|:-------------------:|:-------------:|:------------:|
| Price model | Per byte | 250K credits/mo | 2M credits/mo |
| Cost at 1 ch (79 min) | **$1.65** | $11.00 | $75.00 |
| Cost at 3 ch (237 min) | **$4.93** | $11.00 | $75.00 |
| Cost at 5 ch (395 min) | **$8.22** | $11.00 (at limit) | $75.00 |
| Cost at 10 ch (790 min) | **$16.43** | ❌ Over limit | $75.00 |
| Cost at 25 ch (1,975 min) | **$41.08** | ❌ Over limit | $75.00 |
| Cost at 50 ch (3,950 min) | **$82.16** | ❌ Over limit | ❌ Over limit |

**Recommendation:** Use PAYG until 25+ channels, then switch to Pro plan.

---

## 12-Month Cumulative Projection (1 Channel)

| Month | Phase | Monthly | Cumulative | Revenue Est. | Net |
|-------|-------|---------|-----------|-------------|-----|
| 1 | Ramp-up | $25 | $25 | $0 | -$25 |
| 2 | Ramp-up | $25 | $50 | $0 | -$50 |
| 3 | Steady | $27 | $77 | $0 | -$77 |
| 4 | Steady | $27 | $104 | $0 | -$104 |
| 5 | Steady | $27 | $131 | $0-25 | -$106 |
| 6 | Steady | $27 | $158 | $10-50 | -$108 |
| 7 | Steady | $27 | $185 | $25-100 | -$85 |
| 8 | Steady | $27 | $212 | $50-150 | -$62 |
| 9 | Steady | $27 | $239 | $75-200 | -$39 |
| 10 | Steady | $27 | $266 | $100-300 | +$34 |
| 11 | Steady | $27 | $293 | $125-350 | +$57 |
| 12 | Steady | $27 | $320 | $150-400 | +$80 |

**Break-even: Month 9-10 with 1 channel.**

---

## Cost Guardrails

### Daily Budget Cap

```sql
-- system_config
INSERT INTO system_config (config_key, config_value)
VALUES ('daily_budget_limit', '50.00');
```

Checked by `DailySchedulerWorkflow` before triggering any productions.

### Per-Video Budget Guard

Every activity receives `budget_guard.max_cost_usd`. Default per video:
- Long-form: $2.50 (5× expected to allow retries)
- Short-form: $0.50 (10× expected)

### Per-Provider Rate Limits

```python
# Redis-based token bucket
PROVIDER_LIMITS = {
    "openai": {"rpm": 500, "tpm": 200000},
    "anthropic": {"rpm": 100, "tpm": 100000},
    "google": {"rpm": 1000, "tpm": 500000},
    "fish_audio": {"rpm": 60},
    "serpapi": {"rpd": 100},  # Free tier
    "dalle": {"rpm": 15},
}
```

### Cost Alerts

Notifications sent when:
- Daily spend reaches 80% of limit
- Any single video exceeds 2× expected cost
- Provider error rate exceeds 20% in 10-minute window
- Monthly projection exceeds budget by 20%
