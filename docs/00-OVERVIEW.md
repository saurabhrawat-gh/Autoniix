# YouTube Automation — Master Architecture Plan

> Generated: April 17, 2025 | Updated: April 18, 2025
> Status: Planning Complete — Ready to Build
> Strategy: **C-Optimized (LOCKED)** | 10 diversified channels | $328/mo
> Total: ~582 nodes | 9 workflows | 10 Sheet tabs | Remotion renderer

## Locked Decisions

- **Strategy:** C-Optimized (adaptive: 1L+7S/wk → 2L+3S/wk steady state)
- **Channels:** 10 (5 Health + 3 Finance + 2 Psychology)
- **Brands:** Body Signals, Money Decoded, Mind Shifts
- **Voice:** ElevenLabs Pro $99 (100% voiced, unique voice per channel)
- **Research:** Full SerpAPI $50 (no compromise)
- **n8n:** Self-hosted Hetzner CX31 ($18)
- **Long-form:** 8 min (1100 words), 12% visual-only scenes
- **Shorts:** 45 sec (80 words), all voiced
- **Budget:** $328/mo (Month 1-2), $307/mo (Month 3+)
- **Target:** $2K profit by Month 7-8

## Account Structure

- Management: yt.empire.management@gmail.com (Brand Accounts, up to 100 channels)
- AdSense: saurabhrawat.official@gmail.com (ONE account, linked to ALL channels)
- For 100+ channels: additional management accounts, same AdSense

## System Diagram

```
A (Control) ──→ B1 (Research 155n) ──→ B2 (Assets 110n) ──→ B4 (Assembly 87n)
                                  └──→ B3 (Thumbnail 42n) ──→ B4
                                                                  ↓
                                                          Remotion Server
                                                                  ↓
D (Intelligence 50n, weekly)                            C (Delivery 18n)
E (Trends 40n, 3x daily)
Admin (10n, webhook)
+ ~35 checkpoint/control nodes across all workflows
```

## Node Count Summary

| Workflow | Nodes |
|----------|-------|
| A: Control & Scheduling | 35 |
| B1: Research & Ideation | 155 |
| B2: Asset Generation | 110 |
| B3: Thumbnail Generation | 42 |
| B4: Assembly & QA + Direction Engine | 87 |
| C: Delivery | 18 |
| D: Virality Intelligence | 50 |
| E: Trend Intelligence | 40 |
| Admin Control | 10 |
| Checkpoint/Control nodes | 35 |
| **TOTAL** | **~582** |

## Hybrid Model Stack (C-Optimized)

| Task | Model | Why |
|------|-------|-----|
| Research synthesis | Gemini 2.5 Flash | Cost-optimized, excellent at structured JSON |
| Script writing | Claude Sonnet | Superior creative writing (unchanged) |
| Script critique | GPT-4o-mini | Cost-optimized, critique is simpler task |
| Fact-checking | GPT-4o (temp 0.1) | Most reliable (unchanged) |
| Scene Descriptor v3 | GPT-4o | Best complex JSON output (unchanged) |
| Direction Engine | GPT-4o | Creative-to-technical translation (unchanged) |
| All QC/Scoring | Gemini 2.5 Flash | 94% cheaper, fast (unchanged) |
| Tags, desc, emotion map | GPT-4o-mini | Simple tasks, cheap (unchanged) |
| Audience simulation | Claude Sonnet | Best role-playing (unchanged) |
| Thumbnail QC | GPT-4o Vision | Can "see" the thumbnail (unchanged) |

## Sheet Tabs (10 total)

| Tab | GID | Status |
|-----|-----|--------|
| Channel_DNA | 0 | Needs 10-channel data + new columns |
| Execution_Locks | 1865472506 | Columns only ✅ |
| Belief_Registry | 259150285 | ❌ Wrong columns, needs fix + 30 seed beliefs |
| Output_Log | 1787987140 | ✅ + add artifact URL columns |
| Feedback_Loop | 844630622 | ✅ |
| Performance_Memory | 1321792890 | ✅ |
| Prompt_Registry | 2066543396 | ✅ needs seed data |
| Trend_Intelligence | NEW | Create + columns only |
| API_Usage_Tracker | NEW | Create + columns only |
| System_Config | NEW | Create + seed data |

## Documentation Index

| Doc | Contents |
|-----|----------|
| 00-OVERVIEW.md | This file — system summary |
| 01-SHEETS-STRUCTURE.md | All 10 tabs, columns, seed data |
| 02-WORKFLOW-NODES.md | Node-by-node for all 9 workflows |
| 03-COST-ANALYSIS.md | C-Optimized costs, all strategies, switching guide |
| 04-STRATEGY-SWITCHING.md | Strategy switching, system controls, checkpoints |
| 05-QUALITY-GATES.md | 30 quality gates, failure points, review system |
| 06-REMOTION-ARCHITECTURE.md | 48 React components, API, templates |
| 07-BUILD-ORDER.md | 4-week build plan, scaling roadmap, milestones |
| 08-YOUTUBE-POLICY-SAFETY.md | YouTube policy compliance, legal plan, 100-channel safety |

## Credentials

- Google Sheets OAuth2: JEExfumNmZ8LNXKP
- OpenAI: k9DUnxWeeBIU3zwy
- ElevenLabs API: sk_e2d1c71399f81aec1d9019525fdbe938b33376b9cbd483e4
- ElevenLabs Voice: uju3wxzG5OhpWcoi3SMy (default — each channel gets unique voice)
- Pixabay: 19295073-73da36f3ff10a5b2e1ce66eca
- YouTube Data API: AIzaSyCgjg0kfH0-mdQODrDVnUtH1-lq1tRas9A
- n8n URL: Self-hosted (to be configured)
- Remotion: $vars.REMOTION_RENDER_URL
