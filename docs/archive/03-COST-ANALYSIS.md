# Cost Analysis — All Strategies × All Scale Points

---

# ⚡ LOCKED STRATEGY: C-Optimized (Active Plan)

> **This is the confirmed, active strategy.** 10 channels from day 1.
> All other strategies (A, B, C-Original) are kept below for reference and can be switched to at any time.

## Confirmed Decisions

- **Strategy:** C-Optimized (adaptive schedule, optimized LLM + self-hosted infra)
- **Starting channels:** 10
- **Voice provider:** ElevenLabs (ALL content — long-form AND Shorts, 100% voiced)
- **Research:** Full SerpAPI ($50/mo) — no compromise
- **n8n:** Self-hosted on Hetzner CX31 ($18/mo)
- **LLM stack:** GPT-4o + Claude Sonnet (core tasks), Gemini Flash (QC/scoring), GPT-4o-mini (lightweight tasks)

---

## C-Optimized: How It Works

### Schedule (same adaptive ramp as Strategy C)

- Month 1: 1 Long + 7 Shorts / week per channel
- Month 2: 1 Long + 5 Shorts / week per channel
- Month 3+: 2 Long + 3 Shorts / week per channel (steady state)

### Cost Optimizations (vs original Strategy C)

| Optimization | What Changed | Savings | Quality Impact |
|-------------|-------------|---------|---------------|
| Self-host n8n | Cloud $120 → Hetzner CX31 $18 | $102/mo | Zero — same n8n engine, unlimited executions |
| Optimized LLM routing | Gemini Flash for research synthesis/QC, GPT-4o-mini for critique | ~$7/channel/mo | Negligible — Flash excels at structured tasks |
| Tighter long-form scripts | 10 min (1500 words) → 8 min (1100 words) | ~27% fewer voice chars | Better — tighter scripts = better retention, still qualifies for mid-roll ads |
| Visual-only scenes | 12% of long-form scenes use music + B-roll only (no narration) | ~12% fewer voice chars | Better — creates pacing variety, standard documentary technique |

### What Is NOT Compromised

- Script quality: Claude Sonnet (unchanged)
- Direction Engine: GPT-4o (unchanged)
- v3 scene generation: GPT-4o (unchanged)
- Fact-checking: GPT-4o (unchanged)
- Voice provider: ElevenLabs for ALL content (unchanged)
- ALL Shorts are fully voiced — 100%, no text-only Shorts
- Research depth: Full SerpAPI + multi-source (unchanged)
- Quality gates: All 30 gates at same thresholds (unchanged)
- Visual quality: Same Remotion engine + components (unchanged)

---

## C-Optimized: Per-Video Cost

### Long-Form (~8 min, optimized LLM)

| Component | Cost |
|-----------|------|
| GPT-4o (v3, direction, fact-check) | $0.35 |
| Claude Sonnet (script writing, audience sim) | $0.16 |
| Gemini Flash (research synthesis, QC/scoring, ~18 calls) | $0.05 |
| GPT-4o-mini (tags, desc, emotion map, critique) | $0.04 |
| GPT-4o Vision (thumbnail QC) | $0.05 |
| **LLM Subtotal** | **$0.65** |
| ElevenLabs (~5,808 chars, with visual-only scenes) | included in Pro plan |
| DALL-E 3 (2 thumbnails) | $0.08 |
| SerpAPI (3 queries) | $0.03 |
| Pixabay / Pexels | $0.00 |
| YouTube Data API | $0.00 |
| **Total per long-form (excl. ElevenLabs plan)** | **$0.76** |

### Short-Form (~45 sec, ALL voiced)

| Component | Cost |
|-----------|------|
| LLM (Gemini Flash research, Claude script, Gemini QC) | $0.28 |
| ElevenLabs (~480 chars) | included in Pro plan |
| SerpAPI | $0.03 |
| **Total per short (excl. ElevenLabs plan)** | **$0.31** |

---

## C-Optimized: ElevenLabs Character Budget

### Per Channel Per Month

| Phase | Long-form | Shorts | Total/Channel |
|-------|----------|--------|---------------|
| Month 1 (1L+7S/wk) | 4.33 × 5,808 = 25,149 | 30.3 × 480 = 14,544 | **39,693** |
| Month 2 (1L+5S/wk) | 4.33 × 5,808 = 25,149 | 21.65 × 480 = 10,392 | **35,541** |
| Month 3+ steady (2L+3S/wk) | 8.66 × 5,808 = 50,293 | 12.99 × 480 = 6,235 | **56,528** |

### At 10 Channels

| Phase | 10ch Total Chars | Pro 500K Usage | Status |
|-------|-----------------|---------------|--------|
| Month 1 | 396,930 | 79% | ✅ Comfortable |
| Month 2 | 355,410 | 71% | ✅ Comfortable |
| Month 3+ | 565,280 | 113% | ⚠️ 13% over |

### Handling the Month 3+ Overage (565K vs 500K limit)

By Month 3, revenue should be emerging from 10 channels. Three options:

1. **Upgrade to Scale $330** — revenue from early months funds it (recommended)
2. **Tighten scripts by ~10%** — target 1000 words instead of 1100, fits within 500K
3. **Increase visual-only scenes to 18%** — more breathing room, fits within 500K

The system is designed so you can adjust `words_per_video` and `visual_only_ratio` in Channel_DNA
at any time. No workflow changes needed.

---

## C-Optimized: Variable Cost Per Channel Per Month

| Component | Month 1-2 | Month 3+ (steady) |
|-----------|----------|-------------------|
| LLM (long-form) | $0.76 × 4.33 = $3.29 | $0.76 × 8.66 = $6.58 |
| LLM (shorts) | $0.31 × 30.3 = $9.39 | $0.31 × 12.99 = $4.03 |
| **Variable/channel** | **$12.68** | **$10.61** |

---

## C-Optimized: Fixed Infrastructure (10 Channels)

| Service | Monthly |
|---------|---------|
| n8n Self-hosted (Hetzner CX31, 4CPU/8GB) | $18 |
| Remotion VPS (Hetzner CX31, 4CPU/8GB) | $24 |
| SerpAPI (5K searches) | $50 |
| ElevenLabs Pro (500K chars) | $99 |
| Misc (domain, monitoring) | $10 |
| **Fixed Total** | **$201** |

---

## C-Optimized: Total Monthly Cost (10 Channels, Locked)

| Phase | Variable (10ch) | Fixed | **Total/mo** | **Per Channel** |
|-------|----------------|-------|------------|----------------|
| Month 1-2 | $127 | $201 | **$328** | **$33** ✅ |
| Month 3+ (Pro $99) | $106 | $201 | **$307** | **$31** ✅ |
| Month 3+ (Scale $330) | $106 | $432 | **$538** | **$54** |

---

## C-Optimized: Progressive Scaling Table

| Phase | Mo | Channels | ElevenLabs | n8n | Remotion | SerpAPI | Variable | Misc | **Total** | **Per Ch** |
|-------|-----|----------|-----------|-----|---------|---------|----------|------|-----------|-----------|
| 1 | 1-5 | 10 | Pro $99 | $18 | $24 | $50 | $127 | $10 | **$328** | **$33** |
| 2 | 5-9 | 10→20 | Scale $330 | $18 | $36 | $50 | $212 | $10 | **$656** | **$33** |
| 3 | 9-14 | 20→30 | Scale $330 | $18 | $58 | $50 | $318 | $10 | **$784** | **$26** |
| 4 | 14-18 | 30→50 | Ent. ~$500 | $36 | $58 | $50 | $531 | $10 | **$1,185** | **$24** |
| 5 | 18+ | 50→100 | Ent. ~$1,000 | $36 | $120 | $50 | $1,061 | $10 | **$2,277** | **$23** |

---

## C-Optimized: Revenue Projection (10 Channels)

| Month | Subs/ch | Views/ch/mo | Revenue (10ch) | Spend | Monthly Profit | Cumulative |
|-------|---------|------------|----------------|-------|---------------|-----------|
| 1 | 50-200 | 5K-30K | $0 | $328 | -$328 | -$328 |
| 2 | 150-500 | 15K-60K | $0 | $328 | -$328 | -$656 |
| 3 | 300-900 | 30K-100K | $0 | $307 | -$307 | -$963 |
| 4 | 500-1,500 | 50K-180K | $0-100 | $307 | -$307 to -$207 | -$1,170 |
| 5 | 800-2,000 | 70K-250K | $100-400 | $307 | -$207 to +$93 | -$1,077 |
| 6 | 1K-3K | 100K-350K | $300-800 | $307 | -$7 to +$493 | -$584 |
| 9 | 3K-8K | 200K-600K | $800-2,500 | $307 | +$493 to +$2,193 | +$895 |
| 12 | 5K-15K | 400K-1M | $2,000-6,000 | $307 | +$1,693 to +$5,693 | +$5,974 |

**Break-even: Month 7-9 with 10 channels.**

---

# Strategy Switching Guide

> All strategies can be switched at any time. The system is designed for full flexibility.

## How to Switch

Switching between ANY strategy requires changing **only 2-3 values** in Channel_DNA per channel:

```
Channel_DNA columns that control strategy:
  videos_per_week_long    → e.g. 1, 0.25, 2
  videos_per_week_short   → e.g. 2, 7, 3
  words_per_video_long    → e.g. 1500, 1100
  words_per_video_short   → e.g. 150, 80
  visual_only_ratio       → e.g. 0, 0.12, 0.20
```

Workflow A reads these values fresh every execution cycle. No workflow changes needed.

## Switch Matrix

| From → To | Changes Needed | Effort | Downtime |
|-----------|---------------|--------|----------|
| C-Opt → A | Set 1L+2S/wk, 1500 words, 0% visual-only | 2 min | 0 |
| C-Opt → B | Set 0.25L+7S/wk, 1500 words, 0% visual-only | 2 min | 0 |
| C-Opt → C-Original | Set 2L+3S/wk, 1500 words, 0% visual-only | 2 min | 0 |
| Any → C-Opt | Set adaptive schedule, 1100 words, 12% visual-only | 2 min | 0 |
| Any → Any | Change scheduling columns | 2 min | 0 |

## Per-Channel Strategy Mixing

Different channels can run different strategies simultaneously:

```
CH_HEALTH01:   C-Optimized (2L+3S/wk, 1100 words)  — best performer
CH_PSYCH01:    C-Original  (2L+3S/wk, 1500 words)   — has Scale budget
CH_CRIME01:    Strategy B   (0.25L+7S/wk)            — new channel, Shorts focus
```

---

# Voice Provider Switching Guide

> The voice engine is modular. You can switch providers at any time without changing any other workflow.

## Current: ElevenLabs Pro ($99/mo, 500K chars)

This covers 10 channels comfortably through Month 1-2, and with minor adjustments at steady state.

## Upgrade Path: Full ElevenLabs at Scale

If revenue supports it, upgrade to full ElevenLabs with no optimizations:

| Channels | Plan | Cost | Chars | Words/Video | Visual-Only |
|----------|------|------|-------|------------|------------|
| 1-5 | Pro $99 | $99 | 500K | 1500 (full) | 0% |
| 6-23 | Scale $330 | $330 | 2M | 1500 (full) | 0% |
| 24-50 | Enterprise | ~$500-800 | Custom | 1500 (full) | 0% |
| 51-100 | Enterprise | ~$1,000-1,500 | Custom | 1500 (full) | 0% |

**To upgrade:** Change `words_per_video_long` to 1500, `visual_only_ratio` to 0, upgrade ElevenLabs plan.
Everything else stays the same. One afternoon of changes.

## Alternative Providers (If Needed Later)

| Provider | Quality | Price | When to Consider |
|----------|---------|-------|-----------------|
| ElevenLabs Scale | 8.5/10 | $330/mo (2M chars) | When revenue > $500/mo |
| LOVO AI | 8/10 | $24/mo (500K chars) | Budget fallback with SSML + timestamps |
| PlayHT 2.0 | 8.5/10 | $29/mo (Pro) | If ElevenLabs pricing changes |
| OpenAI TTS-HD | 7.5/10 | $30/1M chars | Only as emergency overflow, not primary |
| Google Cloud TTS Studio | 8/10 | $160/1M chars | If SSML precision is critical |

**The system is designed so switching voice providers requires changing only Workflow B2 (voice engine section, ~15 nodes).** All other workflows are voice-provider-agnostic.

---

# Reference: Original Strategies (Switchable)

> These are the unoptimized original strategies. Kept for reference and comparison.
> You can switch to any of these at any time by adjusting Channel_DNA values.

## Per-Video Cost (Original, Unoptimized LLM Stack)

### Long-Form (~10 min, original)

| Component | Cost |
|-----------|------|
| GPT-4o (research, critique, v3, direction) | $0.75 |
| Claude Sonnet (script, audience sim) | $0.16 |
| Gemini Flash (QC/scoring, ~15 calls) | $0.03 |
| GPT-4o-mini (tags, desc, emotion map) | $0.02 |
| GPT-4o Vision (thumbnail QC) | $0.05 |
| Direction Engine (GPT-4o) | $0.15 |
| **LLM Subtotal** | **$1.16** |
| ElevenLabs (~9000 chars, dual voice) | $2.40 |
| DALL-E 3 (3 thumbnails) | $0.16 |
| SerpAPI (3 queries) | $0.03 |
| Pixabay / Pexels | $0.00 |
| YouTube Data API | $0.00 |
| **Total per long-form** | **$3.75** |

### Short-Form (~60 sec, original)

| Component | Cost |
|-----------|------|
| LLM (full research, lighter script/v3) | $0.59 |
| ElevenLabs (~900 chars) | $0.20 |
| SerpAPI | $0.03 |
| **Total per short** | **$0.82** |

## Strategy A: Balanced (1 Long + 2 Shorts / week)

- 4.33 long-form + 8.66 shorts per month per channel
- ~12 videos/month
- Variable/channel: $24.03/mo
- ElevenLabs chars/channel: 46,764/mo

## Strategy B: Shorts-First (1 Long / month + 7 Shorts / week)

- 1 long-form + 30.3 shorts per month per channel
- ~31 videos/month
- Variable/channel: $19.36/mo
- ElevenLabs chars/channel: 36,270/mo

## Strategy C-Original: Adaptive (evolves over months)

- Month 1: 1 Long + 7 Shorts / week
- Month 2: 1 Long + 5 Shorts / week
- Month 3+: 2 Long + 3 Shorts / week (steady state)
- Variable/channel (steady): $39.15/mo
- ElevenLabs chars/channel (steady): 89,631/mo

## Original Strategy Scaling Tables

### Strategy A: Total Monthly Cost

| Channels | Variable | ElevenLabs | Infra Base | **Total/mo** | **Per Channel** |
|----------|----------|-----------|-----------|------------|----------------|
| 5 | $120 | $99 | $144 | **$363** | $73 |
| 10 | $240 | $330 | $216 | **$786** | $79 |
| 30 | $721 | $500 | $171 | **$1,392** | $46 |
| 100 | $2,403 | $1,500 | $326 | **$4,229** | $42 |

### Strategy B: Total Monthly Cost

| Channels | Variable | ElevenLabs | Infra Base | **Total/mo** | **Per Channel** |
|----------|----------|-----------|-----------|------------|----------------|
| 5 | $97 | $99 | $144 | **$340** | $68 |
| 10 | $194 | $99 | $216 | **$509** | $51 |
| 30 | $581 | $330 | $171 | **$1,082** | $36 |
| 100 | $1,936 | $800 | $326 | **$3,062** | $31 |

### Strategy C-Original: Total Monthly Cost

| Channels | Variable | ElevenLabs | Infra Base | **Total/mo** | **Per Channel** |
|----------|----------|-----------|-----------|------------|----------------|
| 5 | $196 | $330 | $144 | **$670** | $134 |
| 10 | $392 | $330 | $216 | **$938** | $94 |
| 30 | $1,175 | $600 | $171 | **$1,946** | $65 |
| 100 | $3,915 | $2,000 | $326 | **$6,241** | $62 |

## Quick Comparison (All Strategies at 10 Channels)

| Strategy | Total/mo | Per Channel | ElevenLabs Quality | Notes |
|----------|----------|-----------|-------------------|-------|
| **C-Optimized (LOCKED)** | **$328** | **$33** | Full (100% ElevenLabs) | Self-hosted, optimized LLM, 8-min videos |
| C-Original | $938 | $94 | Full (100% ElevenLabs) | Cloud n8n, unoptimized LLM, 10-min videos |
| A (Balanced) | $786 | $79 | Full (100% ElevenLabs) | 1L+2S/week |
| B (Shorts-First) | $509 | $51 | Full (100% ElevenLabs) | Shorts-focused, cheapest original |

**C-Optimized saves 65% vs C-Original at 10 channels with no quality compromise on voice or content.**
