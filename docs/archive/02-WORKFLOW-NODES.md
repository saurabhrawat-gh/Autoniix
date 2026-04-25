# Workflow Node-by-Node Blueprint

---

## Workflow A: Control & Scheduling (35 nodes)

| # | Node Name | Type | Purpose |
|---|-----------|------|---------|
| 1 | Daily Cron Trigger | scheduleTrigger | Fire daily |
| 2 | Manual Trigger | manualTrigger | Manual option |
| 3 | Read System_Config | googleSheets | Check system status |
| 4 | System Status Gate | if | STOP if paused/emergency |
| 5 | Read Channel_DNA | googleSheets | All channel configs |
| 6 | Validate Channel_DNA | code | Required fields, data types |
| 7 | Validation Gate | if | Skip invalid channels |
| 8 | Filter Active Channels | if | status === "active" only |
| 9 | Check Schedule (Day + Timezone) | code | Is today a publishing day? |
| 10 | Read Execution_Locks | googleSheets | Existing locks |
| 11 | Check Execution Lock | code | Skip if locked this week |
| 12 | Read Output_Log (Paused) | googleSheets | Find paused content_ids |
| 13 | Resume Router | if | Resume paused vs create new |
| 14 | Resume Trigger | httpRequest | Re-trigger at checkpoint |
| 15 | Generate Run Metadata | code | run_id, execution_week, timestamps |
| 16 | Write Execution Lock | googleSheets | Prevent duplicates |
| 17 | Read Performance_Memory | googleSheets | Past learnings |
| 18 | Read Trend_Intelligence | googleSheets | Recent trends |
| 19 | Inject Learnings + Trends | code | Merge into context |
| 20 | Production Planner | code | How many long/short today |
| 21 | Process Videos (Batch) | splitInBatches | Loop per video |
| 22 | Content Mix Engine | code | Select content_mode |
| 23 | Content Calendar Check | code | Series continuity, format rotation |
| 24 | Topic Cluster Engine | code | Generate candidates |
| 25 | Read Recent Topics | googleSheets | Dedup data |
| 26 | Cross-Channel Dedup | code | Same topic across ANY channel? |
| 27 | Topic Selector (Dedup) | code | Pick best novel topic |
| 28 | Budget Pre-Check | code | Estimate cost vs daily_budget |
| 29 | Budget Gate | if | STOP if over budget |
| 30 | Prepare B1 Payload | code | Bundle context |
| 31 | Trigger Workflow B1 | httpRequest | POST /workflow-b1-trigger |
| 32 | Log Trigger | code | Record timestamp |
| 33 | Update Daily Budget Used | googleSheets | Increment tracker |
| 34 | Loop Back | code | Next video |
| 35 | Watchdog Check | code | Stuck executions > 6h |

---

## Workflow B1: Research & Ideation (155 nodes)

### Section 1: Entry & Context (10 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 1 | Webhook Trigger | webhook | /workflow-b1-trigger |
| 2 | Parse Input | code | Validate JSON |
| 3 | Read System_Config | googleSheets | Emergency check |
| 4 | System Gate | if | STOP if paused |
| 5 | Read Channel_DNA | googleSheets | Full config |
| 6 | Read Belief_Registry | googleSheets | Beliefs for channel |
| 7 | Read Performance_Memory | googleSheets | Past learnings |
| 8 | Read Output_Log (Last 20) | googleSheets | Recent topics |
| 9 | Read Prompt_Registry | googleSheets | Active B1 prompts |
| 10 | Build Research Context | code | Merge all context |

### Section 2: Multi-Source Research (32 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 11 | YouTube Trending Search | httpRequest | /youtube/v3/search?order=viewCount&maxResults=15 |
| 12 | Parse YouTube Trending | code | Titles, views, dates |
| 13 | Viral Pattern Extractor | code | Title structures, patterns |
| 14 | Competitor Scan (Batch) | splitInBatches | Loop competitor_channels |
| 15 | Competitor Videos | httpRequest | /youtube/v3/search?channelId={id}&order=date |
| 16 | Parse Competitor Videos | code | Titles, topics, velocity |
| 17 | Competitor Loop Back | code | Continue batch |
| 18 | Competitor Gap Analyzer | code | What they cover vs miss |
| 19 | YouTube Comments Extractor | httpRequest | /youtube/v3/commentThreads |
| 20 | Parse Pain Points | code | Recurring questions, frustrations |
| 21 | Google Trends Check | httpRequest | SerpAPI engine=google_trends |
| 22 | Parse Trends Data | code | Direction, breakouts |
| 23 | Trends Gate | if | Skip if no key |
| 24 | Wikipedia Search | httpRequest | /wiki/rest_v1/page/summary |
| 25 | Parse Wiki | code | Summary, facts |
| 26 | Reddit Search | httpRequest | /reddit/search.json |
| 27 | Parse Reddit | code | Themes, takes |
| 28 | Reddit Gate | if | Skip if failed |
| 29 | News API Search | httpRequest | newsapi.org |
| 30 | Parse News | code | Current events angle |
| 31 | News Gate | if | Skip if no key |
| 32 | Merge All Sources | code | Unified research package |
| 33 | GPT Research Synthesizer | openAi | Deep synthesis from ALL sources |
| 34 | Parse Research | code | Structured JSON |
| 35 | GPT Claim Extractor | openAi | Every factual claim |
| 36 | Parse Claims | code | Claims array |
| 37 | GPT Fact Verifier | openAi | Confidence per claim (temp 0.1) |
| 38 | Parse Fact Check | code | Filter low-confidence |
| 39 | Remove Unverifiable | code | Strip <0.6, hedge 0.6-0.8 |
| 40 | Research Quality Inspector | gemini | Depth, uniqueness, quality, actionability |
| 41 | Research Gate (≥8) | if | Pass or retry |
| 42 | Research Retry Counter | code | Max 2 |

### Section 3: Ideation (18 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 43 | Checkpoint: research_complete | code | Save state |
| 44 | Emergency Check | sheets+if | Quick pause check |
| 45 | Insight Extractor | code | Top insights, hooks, pain points |
| 46 | Contrarian Angle Selector | code | Through intellectual_lens |
| 47 | Performance Memory Injection | code | What worked before |
| 48 | GPT Idea Generator (10) | openAi | 10 title+hook+angle combos |
| 49 | Parse Ideas | code | Ideas array |
| 50 | Algorithmic Scorer | code | Curiosity, length, novelty, emotion |
| 51 | GPT Audience Simulator | claude | 5 personas rate each title |
| 52 | Parse Audience Sim | code | Per-idea scores |
| 53 | Composite Score | code | Algo(30%)+audience(40%)+research(30%) |
| 54 | Novelty Check vs Output_Log | code | Penalize similar |
| 55 | Novelty Check vs Belief_Registry | code | cooling_until_date |
| 56 | Rank & Select Top 3 | code | Primary + 2 A/B |
| 57 | Idea Quality Inspector | gemini | Virality, uniqueness, fit, clarity |
| 58 | Idea Gate (≥7.5) | if | Pass or fail |
| 59 | Idea Fail → STOP | code+sheets | Log failure, end |
| 60 | Prepare Idea Package | code | Bundle selected |

### Section 4: Script v1 (22 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 61 | Checkpoint: ideation_complete | code | Save state |
| 62 | Build Script Prompt | code | All context + golden paragraphs |
| 63 | Narrative Template Selector | code | Force variety (revelation, myth-destruction, etc.) |
| 64 | GPT Script Writer v1 | claude | Scene-based with parentheticals |
| 65 | Parse Script v1 | code | Scenes array |
| 66 | Structure Validator | code | Required scenes, correct order |
| 67 | Word Count Validator | code | ±15% of target |
| 68 | Forbidden Words Scanner | code | Against forbidden_words |
| 69 | Parenthetical Validator | code | Every scene has emotion_direction |
| 70 | GPT Script Critic | openAi | 6 dimensions scored |
| 71 | Parse Critique | code | Scores + weaknesses |
| 72 | Critique Gate | if | Any <6 → rewrite |
| 73 | GPT Script Rewriter | claude | Fix specific weaknesses |
| 74 | Parse Rewrite | code | Rewritten script |
| 75 | Rewrite Counter | code | Max 2 |
| 76 | Rewrite Router | if | Loop or proceed |
| 77 | GPT Fact-Check Script | openAi | Script claims vs research |
| 78 | Parse Script Fact Check | code | Soften unsupported |
| 79 | Emotional Arc Analyzer | code | Verify tension peak exists |
| 80 | Word-Level Upgrader | openAi-mini | Replace 10 weakest words |
| 81 | Purple Cow Verifier | code | ≥1 unexpected element |
| 82 | Script Quality Inspector | gemini | Overall, publishable, risk |

### Section 5: Script v2 (6 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 83 | Checkpoint: script_v1_complete | code | Save state |
| 84 | GPT Asset Enrichment | openAi | Line-by-line visual annotation |
| 85 | Parse Script v2 | code | Enriched lines array |
| 86 | Asset Term Validator | code | >3 words, not generic |
| 87 | Visual Coherence Checker | code | No jarring jumps |
| 88 | Asset Type Distribution | code | Mix of types |

### Section 6: Hook Engine (12 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 89 | GPT Hook Generator (5) | openAi | 5 hooks, different techniques |
| 90 | Parse Hooks | code | Array |
| 91 | Technique Classifier | code | Verify variety |
| 92 | GPT Retention Predictor | gemini | 30s retention per hook |
| 93 | Parse Retention | code | Scores |
| 94 | Alignment Scorer | code | Hook delivers on title? |
| 95 | Hook Ranking | code | Retention+alignment+novelty |
| 96 | Hook Gate (≥8) | if | Pass/fail |
| 97 | Hook Retry Counter | code | Max 2 |
| 98 | Hook Retry Router | if | Loop or proceed |
| 99 | Select Best Hook | code | Winner |
| 100 | Replace Script Hook | code | Swap in winner |

### Section 7: Packaging (12 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 101 | GPT Title Optimizer (8) | openAi-mini | 8 variants |
| 102 | Parse Titles | code | Array |
| 103 | Title CTR Predictor | code | Length, words, curiosity |
| 104 | Title-Content Alignment | code | Promise matches delivery |
| 105 | Select Top 3 Titles | code | Primary + A/B |
| 106 | GPT Description Writer | openAi-mini | YouTube-optimized |
| 107 | Parse Description | code | Extract |
| 108 | GPT Tag Generator | openAi-mini | 15-20 tags |
| 109 | Parse Tags | code | Extract |
| 110 | YouTube Chapters Generator | code | From scene boundaries |
| 111 | Comment Triggers Injector | code | ≥2 engagement triggers in script |
| 112 | Shorts Funnel Linker | code | Link short→long-form |

### Section 8: Compliance & Output (13 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 113 | Niche Compliance Checker | code | Health/finance disclaimers |
| 114 | Clickbait Detector | gemini | Title promise vs delivery |
| 115 | Policy Inspector | gemini | YouTube guidelines check |
| 116 | Compliance Gate | if | Risk must be "low" |
| 117 | Build Final Package | code | Bundle everything |
| 118 | Save to Google Drive | httpRequest | Research, scripts as files |
| 119 | Log to Output_Log | googleSheets | Status=scripting_complete |
| 120 | Update Belief_Registry | googleSheets | Mark used |
| 121 | Log API Usage | googleSheets | Track costs |
| 122 | Prepare B2 Payload | code | Script + voice config |
| 123 | Prepare B3 Payload | code | Title + thumbnail config |
| 124 | Trigger B2 | httpRequest | POST /workflow-b2-trigger |
| 125 | Trigger B3 | httpRequest | POST /workflow-b3-trigger |

Remaining ~30 nodes: error handlers, retry wiring, checkpoint saves, emergency checks, notifications.

---

## Workflow B2: Asset Generation (110 nodes)

### Section 1: Entry (5 nodes)
Webhook, Parse, System Check, Gate, Read DNA

### Section 2: Voice Engine (28 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 6 | Split → Scenes | code | Break into scenes |
| 7 | Split → Sentences | code | Per-sentence for TTS |
| 8 | GPT Emotion Mapper | openAi-mini | ElevenLabs params per sentence |
| 9 | Parse Emotion Map | code | Settings array |
| 10 | Emotion Transition Validator | code | No jarring jumps |
| 11 | Transition Smoother | openAi-mini | Insert transitions if needed |
| 12 | SSML Builder | code | Convert to SSML markup |
| 13 | Pause Planner | code | Strategic pause lengths |
| 14 | WPM Calculator | code | Speed per sentence (130-170) |
| 15 | Dual Voice Allocator | code | Primary/secondary per sentence |
| 16 | ElevenLabs Quota Check | httpRequest | GET /v1/user/subscription |
| 17 | Quota Gate | if | STOP if insufficient |
| 18 | Voice Batch Loop | splitInBatches | Per scene |
| 19 | Build ElevenLabs Request | code | SSML + settings |
| 20 | ElevenLabs TTS | httpRequest | POST with-timestamps |
| 21 | Parse Voice | code | Audio + timestamps |
| 22 | Word Timestamp Extractor | code | Word-level timing |
| 23 | Duration Validator | code | ±20% of target |
| 24 | Silence Detector | code | No >2s silences |
| 25 | Pronunciation Check | code | Word count match |
| 26 | Pace Validator | code | WPM in range |
| 27 | Voice Quality Inspector | gemini | Emotion+pacing+emphasis |
| 28 | Voice Gate (≥7.5) | if | Pass/retry |
| 29 | Voice Retry Counter | code | Max 2 |
| 30 | Voice Retry | code | Adjust settings |
| 31 | Voice Loop Back | code | Continue |
| 32 | Audio Manifest Builder | code | All files + timestamps |
| 33 | Upload Audio to Drive | httpRequest | Store for Remotion |

### Section 3: Stock Footage (22 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 34 | Checkpoint: voice_complete | code | Save state |
| 35 | Extract Search Terms | code | From v2 |
| 36 | Categorize Asset Types | code | video/animation/text |
| 37 | Stock Batch Loop | splitInBatches | Per line |
| 38 | Pixabay Search | httpRequest | /api/videos |
| 39 | Parse Pixabay | code | URLs, dimensions |
| 40 | Pexels Search | httpRequest | /videos/search |
| 41 | Parse Pexels | code | URLs, dimensions |
| 42 | Merge & Dedup | code | Combine sources |
| 43 | GPT Relevance Scorer | gemini | Clip matches intent? |
| 44 | Relevance Gate (≥7) | if | Pass/re-search |
| 45 | Backup Term Search | code | Use backup_search_term |
| 46 | Parse Backup | code | Extract |
| 47 | Stock Retry Counter | code | Max 2 |
| 48 | Stock Loop Back | code | Continue |
| 49 | Resolution Filter | code | Min 720p |
| 50 | Duration Filter | code | Clip ≥ segment |
| 51 | Visual Diversity Checker | code | Not all same-looking |
| 52 | Cross-Channel Asset Dedup | code | Not used by other channel |
| 53 | License Validator | code | Commercial use OK |
| 54 | Fallback Generator | code | Text card for missing |
| 55 | Asset Match Inspector | gemini | Coherent narrative? |

### Section 4: Music & SFX (16 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 56 | Checkpoint: stock_complete | code | Save state |
| 57 | GPT Emotional Arc | openAi-mini | Intensity per scene |
| 58 | Parse Arc | code | Curve |
| 59 | Music Mood Mapper | code | Arc → moods |
| 60 | Music Search | httpRequest | Freesound |
| 61 | Parse Music | code | URLs, licenses |
| 62 | Music License Validator | code | CC0 only |
| 63 | Music-Scene Scorer | code | Mood matches? |
| 64 | Music Selection | code | Assign tracks |
| 65 | GPT SFX Planner | openAi-mini | Effects + placement |
| 66 | Parse SFX | code | Array |
| 67 | SFX Search | httpRequest | Freesound |
| 68 | Parse SFX Results | code | URLs |
| 69 | SFX License Validator | code | CC0 only |
| 70 | Audio Mix Planner | code | Volumes, ducking |
| 71 | Audio Inspector | gemini | Fit, density, balance |

### Section 5: Output (8 nodes)
Assemble, completeness check, save to Drive, update Output_Log, log API usage, signal B4, fail handlers.

Remaining ~31 nodes: error handlers, retry wiring, emergency checks, rate limiters.

---

## Workflow B3: Thumbnail Generation (42 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 1-4 | Entry | webhook+code+sheets | Trigger, parse, system check, DNA |
| 5 | Competitor Thumbnail Patterns | code | From research data |
| 6 | GPT Concept Generator (5) | openAi | 5 concepts |
| 7 | Parse Concepts | code | Array |
| 8 | GPT CTR Prediction | gemini | Per concept |
| 9 | Parse CTR | code | Scores |
| 10 | Rank Concepts | code | Weighted |
| 11 | Title-Thumb Alignment | gemini | Match? |
| 12 | Alignment Gate (≥7.5) | if | Pass/regenerate |
| 13 | Select Top 3 | code | Best concepts |
| 14 | DALL-E Prompt Sanitizer | code | Remove triggers |
| 15-17 | DALL-E Gen (×3) | httpRequest | 3 backgrounds |
| 18 | DALL-E Failure Handler | code | Stock fallback |
| 19 | Parse URLs | code | Extract |
| 20 | Build Remotion Thumb Specs | code | 3×3=9 variants |
| 21 | POST Remotion /api/thumbnail | httpRequest | Render all |
| 22 | Parse Results | code | URLs |
| 23 | Mobile Readability Check | code | 120×68px test |
| 24 | GPT Vision Inspector | openAi-vision | Composition, contrast |
| 25 | Thumb Gate (≥8) | if | Pass/retry |
| 26 | Retry Counter | code | Max 2 |
| 27 | Final Selection | code | Best variant |
| 28 | Save to Drive | httpRequest | All variants |
| 29 | Update Output_Log | googleSheets | thumb_ready + URLs |
| 30 | Signal B4 | httpRequest | POST /workflow-b4-ready |
| 31 | Log API Usage | googleSheets | Costs |

Remaining ~11 nodes: error handlers, retry wiring, emergency checks, fallback paths.

---

## Workflow B4: Assembly & QA + Direction Engine (87 nodes)

### Section 1: Entry & Sync (8 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 1 | Webhook | webhook | From B2 or B3 |
| 2 | Parse Input | code | Extract flag |
| 3 | Write Flag | googleSheets | Set received flag |
| 4 | Read Output_Log | googleSheets | Both flags set? |
| 5 | Both Ready Gate | if | Proceed or exit |
| 6 | Anti-Duplicate | code | assembly_started_at check |
| 7 | Set Assembly Started | googleSheets | Mutex |
| 8 | Load All Assets | code | Merge everything |

### Section 2: Direction Engine (25 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 9 | Content Type Classifier | code | stock_documentary / 2d_animated / hybrid_kinetic |
| 10 | Load Direction Ruleset | code | Format rules |
| 11 | Load Visual Identity | code | Colors, fonts, pacing |
| 12 | GPT Director | openAi | Per-scene direction plan |
| 13 | Parse Direction | code | Structured JSON |
| 14 | Emotional→Visual Arc | code | Emotion → visual intensity |
| 15 | Cut Frequency Calc | code | CPM per scene |
| 16 | Transition Decisions | code | Type per scene boundary |
| 17 | Color Grade Plan | code | Per-scene palette |
| 18 | Text Strategy | code | Subtitle/kinetic/card per line |
| 19 | Audio Direction | code | Volume, ducking, SFX |
| 20 | Motion Design | code | Animation type per segment |
| 21 | Component Allocator | code | Remotion component per segment |
| 22 | Aspect Ratio Director | code | 16:9 vs 9:16 decisions |
| 23 | Consistency Checker | code | Coherent visual language |
| 24 | Pacing Validator | code | CPM appropriate |
| 25 | Variety Enforcer | code | Not >3 same type |
| 26 | Format Compliance | code | Stock ratio matches rules |
| 27 | GPT Direction Inspector | gemini | Coherence, pacing, variety |
| 28 | Direction Gate (≥8.5) | if | Pass/retry |
| 29 | Direction Retry | code | Max 2 |
| 30 | Merge Direction+Assets | code | Combine |
| 31 | Frame Timing Calc | code | Exact frame numbers |
| 32 | Component Spec Builder | code | Remotion props |
| 33 | Caption Sync Calc | code | Word timestamps→frames |

### Section 3: Scene Descriptor v3 (15 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 34 | Checkpoint: direction_complete | code | Save state |
| 35 | GPT v3 Generator (per scene) | openAi | Frame-level specs |
| 36 | Parse v3 | code | Segment JSON |
| 37 | Schema Validator | code | All fields present |
| 38 | Timeline Continuity | code | No gaps/overlaps |
| 39 | Duration Alignment | code | Total matches plan |
| 40 | Asset Reference Valid | code | All refs exist |
| 41 | Caption Timing Valid | code | Words align |
| 42 | Animation Valid | code | Valid types |
| 43 | Color Grade Consistency | code | Gradual shifts |
| 44 | Audio Mix Valid | code | Levels correct |
| 45 | Production Inspector | gemini | Accuracy, quality, validity |
| 46 | Production Gate (≥8) | if | Pass/retry |
| 47 | Retry Counter | code | Max 2 |
| 48 | Assemble Full v3 | code | All scenes merged |

### Section 4: Render (8 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 49 | Remotion Health Check | httpRequest | GET /api/health |
| 50 | Health Gate | if | STOP if unhealthy |
| 51 | Build Render Payload | code | v3 + codec + quality |
| 52 | POST /api/render | httpRequest | Submit job |
| 53 | Parse Response | code | render_id |
| 54 | Status Check | if | Immediate failure? |
| 55 | Failure Handler | code | Retry simplified |
| 56 | Update Output_Log | googleSheets | render_submitted |

### Section 5: Storyboard (4 nodes)
Generate frames, parse URLs, save to Drive, update Output_Log.

### Section 6: Final QA (15 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 62 | Weighted Final Score | code | Idea(15%)+Script(25%)+Hook(15%)+Thumb(15%)+Production(15%)+Voice(15%) |
| 63 | Final QA Inspector | gemini | Publishable? |
| 64 | Final Gate (≥8) | if | Auto-approve or review |
| 65 | Policy Final Check | gemini | Strike risk |
| 66 | Strike Gate | if | Any ≥3 → human review |
| 67 | Content Fingerprint | code | Hash visual sequence |
| 68 | Cross-Channel Similarity | sheets+code | Compare fingerprints |
| 69 | Similarity Gate | if | >40% → BLOCK |
| 70 | Auto-Approve | code | Score ≥8.5, all gates pass |
| 71 | Human Review | code | 7.5-8.5 or flagged |
| 72 | Send Review Notification | httpRequest | Email with download links |
| 73 | Log to Output_Log | googleSheets | Final scores, URLs |
| 74 | Log to Feedback_Loop | googleSheets | Mirror entry |
| 75 | Update Lock (complete) | googleSheets | Release |

Remaining ~12 nodes: error handlers, checkpoints, budget tracking, notifications.

---

## Workflow C: Delivery (18 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 1 | Remotion Callback Webhook | webhook | Render complete |
| 2 | Parse Callback | code | render_id, status, url |
| 3 | Success Gate | if | Success/failure |
| 4 | Read Output_Log | googleSheets | Match render_id |
| 5 | Match Entry | code | Locate row |
| 6 | Download to Drive | httpRequest | Store video |
| 7 | Update Output_Log | googleSheets | render_complete + URL |
| 8 | Update Feedback_Loop | googleSheets | Mirror |
| 9 | AI Disclosure Inject | code | Add AI label |
| 10 | Disclaimer Inject | code | Niche disclaimers |
| 11 | Metadata Uniqueness | code | Description unique |
| 12 | Build Upload Package | code | Ready for YouTube Studio |
| 13 | Save Package to Drive | httpRequest | Store |
| 14 | Send Notification | httpRequest | All links |
| 15 | Failure Handler | code | Log failure |
| 16 | Log Failure | googleSheets | render_failed |
| 17 | Retry Render | httpRequest | Simplified v3 |
| 18 | Log API Usage | googleSheets | Costs |

---

## Workflow D: Virality Intelligence (50 nodes)

Runs weekly (cron).

1. **Analytics Collection (12):** Read Feedback_Loop → filter pending → YouTube Stats per video → update sheets
2. **Pattern Analysis (10):** GPT analyzes success/failure → title/hook/thumbnail/length patterns
3. **Competitor Intelligence (8):** Scan competitors → gaps + winning patterns
4. **Learning Loop (10):** Write Performance_Memory → prune stale → validate existing
5. **Channel DNA Evolution (5):** Suggest DNA updates → notify human
6. **Post-Publish Optimization (5):** CTR < target after 48h → suggest new title/thumbnail

---

## Workflow E: Trend Intelligence (40 nodes)

Runs 3x daily (cron).

1. **Niche Scanning (3):** Active channels → unique niches
2. **YouTube Trends (8):** Newest + viral this week per niche
3. **Algorithm Signals (5):** Performance changes + competitor velocity
4. **Google Trends (4):** Rising queries, breakouts
5. **Reddit/Forum (5):** Top posts in niche subreddits
6. **Competitor Tracker (5):** This week's uploads
7. **Virality Analyzer (4):** GPT top 5 opportunities per niche
8. **Anti-Repetition (3):** Compare against recent output
9. **Write Trends (2):** Store to Trend_Intelligence
10. **Alert (1):** Urgent opportunity notification

---

## Admin Control Workflow (10 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 1 | Webhook | webhook | /admin/* |
| 2 | Auth Check | code | Validate token |
| 3 | Route by Action | switch | pause/resume/stop/status/budget/strategy |
| 4 | Pause Handler | googleSheets | Set status |
| 5 | Resume Handler | sheets+http | Resume + checkpoints |
| 6 | Emergency Stop | googleSheets | emergency_stop=true |
| 7 | Status Reporter | code+sheets | Health summary |
| 8 | Budget Adjuster | googleSheets | Update limit |
| 9 | Strategy Changer | googleSheets | Update videos_per_week |
| 10 | Response Builder | code | JSON response |
