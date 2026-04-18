# Build Order & Scaling Roadmap

> Strategy: C-Optimized (LOCKED) | Starting: 10 diversified channels | Budget: $328/mo

---

## Channel Lineup (10 Channels, Day 1)

| # | Brand | Channel | Niche | Voice |
|---|-------|---------|-------|-------|
| 1 | Body Signals | Sleep & Recovery | Health | Unique voice A |
| 2 | Body Signals | Hair & Skin Restoration | Health | Unique voice B |
| 3 | Body Signals | Gut Health & Digestion | Health | Unique voice C |
| 4 | Body Signals | Anxiety & Stress Signals | Health | Unique voice D |
| 5 | Body Signals | Metabolism & Weight Science | Health | Unique voice E |
| 6 | Money Decoded | Investing for Beginners | Finance | Unique voice F |
| 7 | Money Decoded | Money Psychology | Finance | Unique voice G |
| 8 | Money Decoded | Credit & Debt Freedom | Finance | Unique voice H |
| 9 | Mind Shifts | Dark Psychology & Persuasion | Psychology | Unique voice I |
| 10 | Mind Shifts | Stoic Mindset | Psychology | Unique voice J |

Account structure:
- Management: yt.empire.management@gmail.com (Brand Accounts)
- AdSense: saurabhrawat.official@gmail.com (ONE account, all channels)

---

## Build Order

### Phase 0: Preparation (Day 1-2)
- [ ] Fix Google Sheets: rename Belief_Registry columns, add missing columns
- [ ] Create new tabs: Trend_Intelligence, API_Usage_Tracker, System_Config
- [ ] Add new columns to Output_Log (artifact URLs, checkpoint columns)
- [ ] Add new columns to Channel_DNA (words_per_video_long, words_per_video_short, visual_only_ratio, + font, caption, pacing, etc.)
- [ ] Seed Channel_DNA with all 10 channels (unique voices, colors, fonts, templates)
- [ ] Seed Belief_Registry (3 beliefs per channel × 10 channels = 30 beliefs)
- [ ] Seed System_Config (6 rows)
- [ ] Seed Prompt_Registry (initial prompts for all modules)
- [ ] Set up n8n self-hosted (Hetzner CX31, Docker)
- [ ] Set up Remotion VPS (Hetzner CX31, Docker)
- [ ] Set up n8n variables: API keys, Remotion URL
- [ ] Create 10 YouTube Brand Account channels under yt.empire.management@gmail.com
- [ ] Set unique visual identity per channel: colors, fonts, thumbnail style, intro/outro
- [ ] Select unique ElevenLabs voice per channel (10 distinct voices)
- [ ] Add health/finance/psychology disclaimers to all channel descriptions
- [ ] Verify AI disclosure process documented

### Phase 1: Short-Form Pipeline (Week 1)
- [ ] Build Workflow A (Control & Scheduling) — 35 nodes
- [ ] Build Workflow B1 (Research & Ideation) — 155 nodes
  - Start with short-form path (~55 active nodes)
- [ ] Build Workflow B2 (Asset Generation) — voice + stock only (~40 nodes)
- [ ] Build Remotion Phase 1 (MVP renderer)
- [ ] Build Workflow B4 (Assembly) — simplified for shorts (~30 nodes)
- [ ] Build Workflow C (Delivery) — 18 nodes
- [ ] **START PUBLISHING SHORTS** across all 10 channels by end of Week 1

### Phase 2: Long-Form Pipeline (Week 2)
- [ ] Extend B1 for long-form (activate remaining nodes, 8-min target)
- [ ] Extend B2 with music/SFX engine
- [ ] Build Workflow B3 (Thumbnail) — 42 nodes
- [ ] Extend B4 with Direction Engine + full QA
- [ ] Build Remotion Phase 2 (data viz, transitions, branding)
- [ ] **START PUBLISHING LONG-FORM** across all 10 channels by end of Week 2

### Phase 3: Intelligence & Quality (Week 3)
- [ ] Build Workflow D (Virality Intelligence) — 50 nodes
- [ ] Build Workflow E (Trend Intelligence) — 40 nodes
- [ ] Build Admin Control Workflow — 10 nodes
- [ ] Add all checkpoint/pause/resume nodes
- [ ] Build Remotion Phase 3 (premium components)

### Phase 4: Polish & Compliance (Week 4+)
- [ ] Add human review notification system
- [ ] Add Google Drive storage for all artifacts
- [ ] Fine-tune quality gate thresholds based on real output
- [ ] Add cross-channel dedup and fingerprinting
- [ ] Add niche-specific disclaimer injection (health, finance, legal)
- [ ] Add AI disclosure flag in upload metadata
- [ ] Set up monthly compliance audit workflow
- [ ] Performance tuning and cost optimization

---

## Scaling Roadmap (C-Optimized)

### Phase 1: Launch & Prove (Month 1-5) — 10 Channels

| Service | Monthly |
|---------|---------|
| n8n Self-hosted (Hetzner CX31) | $18 |
| Remotion VPS (Hetzner CX31) | $24 |
| SerpAPI | $50 |
| ElevenLabs Pro (500K chars) | $99 |
| Misc | $10 |
| LLM variable (10 channels) | $106-127 |
| **Total** | **$307-328** |

Focus: Prove pipeline works, calibrate quality, get first monetizations.

### Phase 2: Validate & Grow (Month 5-9) — 10 → 20 Channels

| Service | Monthly |
|---------|---------|
| n8n Self-hosted (CX31) | $18 |
| Remotion VPS (CX41, 8CPU/16GB) | $36 |
| SerpAPI | $50 |
| ElevenLabs Scale (2M chars) | $330 |
| Misc | $10 |
| LLM variable (20 channels) | $212 |
| **Total** | **$656 ($33/ch)** |

Trigger: ≥5 channels monetized AND revenue > $500/mo.
Add: 15 new channels from Phase 2 niche list (see 08-YOUTUBE-POLICY-SAFETY.md).

### Phase 3: Accelerate (Month 9-14) — 20 → 30 Channels

| Service | Monthly |
|---------|---------|
| n8n Self-hosted (CX31) | $18 |
| Remotion VPS (CX51, 16CPU/32GB) | $58 |
| SerpAPI | $50 |
| ElevenLabs Scale | $330 |
| Supabase Pro (optional) | $25 |
| Misc | $10 |
| LLM variable (30 channels) | $318 |
| **Total** | **$809 ($27/ch)** |

Trigger: Revenue > $1,500/mo AND < 10% videos need human intervention.
Migration: Consider Sheets → Supabase if >5,000 rows.

### Phase 4: Scale (Month 14-20) — 30 → 50 → 100 Channels

| Service | Monthly |
|---------|---------|
| n8n Self-hosted cluster (2 workers) | $36 |
| Remotion 2×CX41 | $72 |
| SerpAPI | $50 |
| ElevenLabs Enterprise | ~$500-1,000 |
| Supabase Pro | $25 |
| Redis (Upstash) | $10 |
| Misc | $10 |
| LLM variable (50-100 channels) | $531-1,061 |
| **Total (50ch)** | **~$1,234 ($25/ch)** |
| **Total (100ch)** | **~$2,264 ($23/ch)** |

Trigger: Revenue > $5,000/mo AND profit margin > 50%.
Add additional Google management accounts for channels 101+.

### Phase 5: Language Expansion (Month 20+) — Beyond 100

| Service | Incremental per language |
|---------|------------------------|
| Translation (GPT-4o) | ~$0.15/video |
| ElevenLabs (target language) | Same char allocation |
| Thumbnail text swap | ~$0.02/video |

Scale: Top 10-50 English channels × 5-10 languages = 50-500 additional channels.
This is the safe path to 1,000+ total channels.

---

## Migration Triggers

| From | To | When |
|------|----|------|
| Sheets → Supabase | >5,000 rows in any tab OR >15 channels active |
| Single render → 2 servers | >3 concurrent render needs |
| ElevenLabs Pro → Scale | >500K chars/month (at ~6 channels steady state) |
| Manual upload → YouTube API | OAuth2 verified + >20 channels |
| Single Google mgmt account → Multiple | Approaching 100 channels |

---

## Key Milestones

| Milestone | Target |
|-----------|--------|
| System built + first Short published | End of Week 1 |
| First Long-form published (all 10 channels) | End of Week 2 |
| Intelligence workflows running | End of Week 3 |
| 1,000 subscribers (first channel) | Month 2-3 |
| First channel monetized | Month 4-5 |
| 5 channels monetized | Month 5-7 |
| **$2,000 monthly profit** | **Month 7-8** |
| Scale to 20 channels | Month 5-9 (if gate conditions met) |
| 10 channels monetized | Month 7-10 |
| Scale to 50 channels | Month 12-14 |
| Scale to 100 channels | Month 18-20 |
| Begin language expansion | Month 20+ |
| Revenue: $10K/month | Month 14-18 |
| Revenue: $25K/month | Month 20-24 |

## Gate Rules (NEVER Scale If...)

| ❌ Don't scale if... | Why |
|---------------------|-----|
| Quality scores averaging < 7.5 | System isn't producing good content |
| < 50% channels monetized at current tier | Revenue model unproven |
| Revenue doesn't cover costs at current tier | Unit economics broken |
| > 20% videos need human intervention | System isn't autonomous enough |
| Any channel received a YouTube strike | Fix compliance before adding more |
| Monthly API costs > 120% of estimate | Cost leak — find and fix |
| Any AdSense warning received | STOP everything, investigate |
