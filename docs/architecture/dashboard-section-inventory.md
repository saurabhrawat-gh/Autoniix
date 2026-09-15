# Unified Section Inventory — Autoniix Dashboard

> **Single source of truth for every section, route, feature, and API dependency.**
> Every sprint chat references this document by section ID.

---

## How to Use This Document

Each section has a unique **Section ID** (e.g., `S01-HOME`). When starting a sprint for a section:

1. Read the section's purpose, routes, and API inventory below.
2. Open the BA agent workflow for deep-dive spec discussion.
3. Reference child sections and related sections for cross-cutting concerns.
4. After spec lock, implement backend → tests → frontend.

---

## Section Index

| ID  | Section                                             | Routes | Status      |
| --- | --------------------------------------------------- | ------ | ----------- |
| S01 | [Home (Mission Control)](#s01-home-mission-control) | 1      | Needs audit |
| S02 | [Notifications](#s02-notifications)                 | 1      | Needs audit |
| S03 | [Channels](#s03-channels)                           | 3      | Needs audit |
| S04 | [Content](#s04-content)                             | 3      | Needs audit |
| S05 | [Library](#s05-library)                             | 1      | Needs audit |
| S06 | [Queue](#s06-queue)                                 | 1      | Stub        |
| S07 | [Progress](#s07-progress)                           | 2      | Needs audit |
| S08 | [Review](#s08-review)                               | 3      | Needs audit |
| S09 | [Fleet](#s09-fleet)                                 | 1      | Needs audit |
| S10 | [Analytics](#s10-analytics)                         | 1      | **Missing** |
| S11 | [Experiments](#s11-experiments)                     | 1      | Needs audit |
| S12 | [Workspace](#s12-workspace)                         | 1      | Needs audit |
| S13 | [Teams](#s13-teams)                                 | 1      | Needs audit |
| S14 | [Users](#s14-users)                                 | 1      | Needs audit |
| S15 | [Providers](#s15-providers)                         | 2      | Needs audit |
| S16 | [Settings](#s16-settings)                           | 2      | Needs audit |
| S17 | [Debug](#s17-debug)                                 | 1      | Needs audit |
| S18 | [Profile](#s18-profile)                             | 1      | Needs audit |
| —   | [Auth (Login/Register)](#auth-loginregister)        | 5      | Needs audit |

**Total: 38+ routes across 18 sections + auth**

---

## S01 — Home (Mission Control)

**Route:** `/dashboard`
**Sidebar label:** Home
**Pillar:** Top Leaf
**Purpose:** Entry point dashboard. Live pipeline overview with real-time stats, quick actions, system health, and activity feed.

### Child Routes

None directly, but links to: Channels, Content, Review, Library, Experiments, Queue, Progress, Teams, Settings.

### Related Sections

- S03 (Channels) — active channel count, channel stats
- S04 (Content) — video counts, delivery stats
- S07 (Progress) — active jobs, running jobs
- S08 (Review) — pending review count
- S09 (Fleet) — system health ECG
- S16 (Settings) — budget, emergency stop

### Features (every minute detail)

1. **Stat Cards (Primary Row):** Active Channels, Videos Today, Cost Today, Active Jobs
2. **Stat Cards (Secondary Row):** Success Rate, Pending Review, Failed Today, System Health
3. **Quick Actions Grid:** 8 shortcut links to other sections with badges
4. **System Banner:** Production mode indicator with sonar pulse / Emergency stop with alert
5. **Live Activity Feed:** Recent jobs with status badges, progress %, AnimatePresence transitions
6. **Pending Review Banner:** Conditional CTA to review page
7. **WebSocket Live Updates:** Job status changes auto-refresh stats
8. **Refresh Button:** Manual refresh with spinning icon
9. **Empty States:** Skeleton loaders, "No active jobs" empty state
10. **Animations:** Staggered section entrance, stat card flash on WS update, review badge elastic pop

### API Inventory

| API Endpoint                   | v2 Module | Status    | Notes                                                             |
| ------------------------------ | --------- | --------- | ----------------------------------------------------------------- |
| `GET /api/v2/channels/stats`   | channels  | ✅ Exists | Returns dashboard stats (channels, today, budget, emergency_stop) |
| `GET /api/v2/content?limit=30` | content   | ✅ Exists | Returns grouped job list for activity feed                        |
| `WS /api/ws/events`            | main.py   | ✅ Exists | WebSocket for live job updates                                    |

### FE Client Functions Used

- `dashboardApi.stats()` → `GET /api/v2/channels/stats`
- `contentApi.list({ limit: 30 })` → `GET /api/v2/content`
- `wsEvents()` → WebSocket connection
- `isLoggedIn()` → auth check

### Pending Investigation

- [ ] Does `/api/v2/channels/stats` return all fields the dashboard expects? (channels.total/active/disabled/archived, today.videos_total/delivered/failed/in_progress/cost, budget.daily_limit, environment_mode, emergency_stop)
- [ ] Does the WebSocket actually push `job_update` events correctly?
- [ ] Are cost calculations accurate (today cost vs budget)?
- [ ] Does the emergency_stop flag work end-to-end (set → freeze → resume)?
- [ ] Are the stat card animations working with reduced motion preference?

---

## S02 — Notifications

**Route:** `/dashboard/notifications`
**Sidebar label:** Notifications
**Pillar:** Top Leaf
**Purpose:** Notification center — view, filter, and mark-read system notifications. Notification routing configuration.

### Child Routes

None.

### Related Sections

- S17 (Debug) — shares notification delivery data
- S16 (Settings) — notification preferences may live here

### Features

1. **Notification List:** Filterable by unread/severity
2. **Mark as Read:** Individual notification read tracking
3. **Severity Levels:** info, warning, critical
4. **Deduplication:** 60s dedupe window by key
5. **Notification Routes:** Create/update/delete routing rules
6. **Delivery History:** Track notification deliveries per channel
7. **Event Types:** Categorized by event_type with payload

### API Inventory

| API Endpoint                               | v2 Module     | Status    | Notes                                          |
| ------------------------------------------ | ------------- | --------- | ---------------------------------------------- |
| `GET /api/v2/notifications`                | notifications | ✅ Exists | List with unread_only, severity, limit filters |
| `POST /api/v2/notifications`               | notifications | ✅ Exists | Create notification with dedupe                |
| `POST /api/v2/notifications/{id}/read`     | notifications | ✅ Exists | Mark single notification read                  |
| `GET /api/v2/notifications/routes`         | notifications | ✅ Exists | List routing rules                             |
| `POST /api/v2/notifications/routes`        | notifications | ✅ Exists | Create route                                   |
| `PUT /api/v2/notifications/routes/{id}`    | notifications | ✅ Exists | Update route                                   |
| `DELETE /api/v2/notifications/routes/{id}` | notifications | ✅ Exists | Delete route                                   |
| `GET /api/v2/notifications/deliveries`     | notifications | ✅ Exists | Delivery history                               |

### FE Client Functions Used

- `notifyApi.list()`, `notifyApi.read()`, `notifyApi.routes()`, `notifyApi.upsertRoute()`, `notifyApi.updateRoute()`, `notifyApi.deleteRoute()`, `notifyApi.deliveries()`

### Pending Investigation

- [ ] Does the notification bell in ChromeBar show real unread count?
- [ ] Are notification routes actually dispatching (Slack, email, webhook)?
- [ ] Is the deduplication working correctly?
- [ ] Are read receipts per-user (array_append) working?
- [ ] What notification channels are supported? (Slack only? Email? Webhook?)

---

## S03 — Channels

**Route:** `/dashboard/channels`
**Sidebar label:** Channels
**Pillar:** Create
**Purpose:** Channel management — create, configure, trigger, and monitor YouTube channels. The core entity of the entire system.

### Child Routes

- `/dashboard/channels/new` — Channel creation wizard (multi-step)
- `/dashboard/channels/[id]` — Channel detail/edit page

### Related Sections

- S04 (Content) — channel's videos
- S07 (Progress) — channel's active jobs
- S08 (Review) — channel's pending reviews
- S15 (Providers) — channel-scoped credentials
- S16 (Settings) — finishing config, review config per channel

### Features (every minute detail)

#### Channel List Page

1. **Channel Cards/Table:** List all channels with status, stats, active jobs
2. **Status Indicators:** active, disabled, archived, paused
3. **Quick Stats per Channel:** delivered count, in-progress count, weekly usage
4. **Active Jobs per Channel:** Show running/paused jobs with content_mode
5. **Channel Actions:** Trigger, Enable/Disable, Archive/Restore, Clone, Export, Delete
6. **Filtering:** By status, content_mode
7. **Search:** Channel name search
8. **Weekly Usage Gauges:** Short vs long form limits

#### Channel Create Wizard (Multi-Step)

1. **Step 1 — Basics:** Channel name, niche, sub-niche, content mode, platform, handle
2. **Step 2 — Brand DNA:** AI-generated or manual: belief_territory, intellectual_lens, topic_domain, brand_voice, narrative_rhythm, emotional_contract, target_audience, primary_format, thumbnail_style, primary_color, forbidden_words
3. **Step 3 — Content Strategy:** Pillars (name, description, weight, examples), Topic Rules (kind, value, metadata), References (kind, label, uri)
4. **Step 4 — Voice & Style:** ElevenLabs voice, stability, similarity, style; humor_style, narration_style, music_style, pacing_style, LUT preference, transition preference, typography preference, meme_intensity, emotion_intensity
5. **Step 5 — Publishing:** Auto-upload, human_review_required (none/first_10/always), review_ratio, review_timeout_hours, max_daily_api_spend, videos_per_week (short/long), durations
6. **Step 6 — Review & Create:** Summary of all settings before creation
7. **Presets:** Apply channel presets to pre-fill the wizard
8. **Draft Save:** Save wizard progress and resume later
9. **AI Field Suggestions:** Per-field AI suggestions via `/api/v2/channels/ai/field-suggest`
10. **Brand DNA Generation:** LLM-generated brand DNA from niche + name

#### Channel Detail/Edit Page

1. **Profile Tab:** Mission, vision, brand_personality, tone, completeness score
2. **Pillars Tab:** CRUD for content pillars
3. **Topic Rules Tab:** CRUD for topic rules (include/exclude/prefer)
4. **References Tab:** CRUD for reference materials (upload/link)
5. **Settings Tab:** All channel config (same as wizard fields)
6. **Finishing Config:** Resolve-finisher settings (color grade, audio, output format)
7. **Review Config:** Review gate profile (hands_off/quick/standard/full_control/custom) + per-gate toggles
8. **Provider Overrides:** Channel-scoped credential chains
9. **Trigger Panel:** Manual trigger with topic hint, content_mode, max_cost
10. **Job Controls:** Pause/Resume/Stop per active job
11. **Status Actions:** Enable, Disable, Archive, Restore, Clone, Export, Delete (hard delete with password confirmation)

### API Inventory

| API Endpoint                                     | v2 Module     | Status | Notes                              |
| ------------------------------------------------ | ------------- | ------ | ---------------------------------- |
| `GET /api/v2/channels`                           | channels      | ✅     | List with include_archived, enrich |
| `POST /api/v2/channels`                          | channels      | ✅     | Create with full payload           |
| `GET /api/v2/channels/{id}`                      | channels      | ✅     | Single channel detail              |
| `PUT /api/v2/channels/{id}`                      | channels      | ✅     | Update channel                     |
| `DELETE /api/v2/channels/{id}`                   | channels      | ✅     | Hard delete (owner + password)     |
| `PUT /api/v2/channels/{id}/enable`               | channels      | ✅     | Enable channel                     |
| `PUT /api/v2/channels/{id}/disable`              | channels      | ✅     | Disable channel                    |
| `PUT /api/v2/channels/{id}/archive`              | channels      | ✅     | Archive channel                    |
| `PUT /api/v2/channels/{id}/restore`              | channels      | ✅     | Restore archived                   |
| `POST /api/v2/channels/{id}/clone`               | channels      | ✅     | Clone channel                      |
| `GET /api/v2/channels/{id}/export`               | channels      | ✅     | Export channel config              |
| `POST /api/v2/channels/{id}/trigger`             | channels      | ✅     | Manual trigger                     |
| `POST /api/v2/channels/{id}/jobs/{cid}/pause`    | channels      | ✅     | Pause job                          |
| `POST /api/v2/channels/{id}/jobs/{cid}/resume`   | channels      | ✅     | Resume job                         |
| `POST /api/v2/channels/{id}/jobs/{cid}/stop`     | channels      | ✅     | Stop job                           |
| `GET /api/v2/channels/presets`                   | channels      | ✅     | List presets                       |
| `PUT /api/v2/channels/{id}/profile`              | channels      | ✅     | Upsert profile                     |
| `POST /api/v2/channels/{id}/pillars`             | channels      | ✅     | Add pillar                         |
| `DELETE /api/v2/channels/{id}/pillars/{pid}`     | channels      | ✅     | Delete pillar                      |
| `POST /api/v2/channels/{id}/topic-rules`         | channels      | ✅     | Add topic rule                     |
| `DELETE /api/v2/channels/{id}/topic-rules/{rid}` | channels      | ✅     | Delete topic rule                  |
| `POST /api/v2/channels/{id}/references`          | channels      | ✅     | Add reference                      |
| `DELETE /api/v2/channels/{id}/references/{rid}`  | channels      | ✅     | Delete reference                   |
| `POST /api/v2/channels/ai/field-suggest`         | channels      | ✅     | AI field suggestion                |
| `POST /api/v2/channels/drafts`                   | channels      | ✅     | Save wizard draft                  |
| `PUT /api/v2/channels/drafts/{id}`               | channels      | ✅     | Update draft                       |
| `GET /api/v2/channels/drafts/{id}`               | channels      | ✅     | Get draft                          |
| `GET /api/v2/channels/{id}/settings/finishing`   | finishing     | ✅     | Get finishing config               |
| `PUT /api/v2/channels/{id}/settings/finishing`   | finishing     | ✅     | Update finishing config            |
| `GET /api/v2/finishing/presets`                  | finishing     | ✅     | List finishing presets             |
| `GET /api/v2/channels/{id}/settings/review`      | review_config | ✅     | Get review config                  |
| `PUT /api/v2/channels/{id}/settings/review`      | review_config | ✅     | Update review config               |

### FE Client Functions Used

- `channelsApi.*` — all CRUD + status actions + trigger + job controls
- `finishingApi.*` — finishing config
- `reviewConfigApi.*` — review config

### Pending Investigation

- [ ] Does channel creation handle all 6 wizard steps atomically (transaction)?
- [ ] Are presets working? What presets exist?
- [ ] Does AI field suggestion use the correct LLM provider?
- [ ] Does Brand DNA generation fall back gracefully when LLM is unavailable?
- [ ] Are draft saves working (resume wizard)?
- [ ] Does clone correctly duplicate pillars, rules, references?
- [ ] Does export produce a re-importable config?
- [ ] Does hard delete cascade correctly (videos, events, pillars, rules, refs)?
- [ ] Are channel-scoped provider overrides resolving correctly?
- [ ] Does trigger respect max_daily_api_spend?
- [ ] Does trigger check for existing in-progress jobs per content_mode?
- [ ] Are pause/resume/stop working with Temporal workflow signals?
- [ ] Does the completeness_score heuristic make sense?
- [ ] Are weekly usage limits enforced?

---

## S04 — Content

**Route:** `/dashboard/content`
**Sidebar label:** Content
**Pillar:** Create
**Purpose:** Content/video management — view, search, filter, and bulk-manage all videos across channels.

### Child Routes

- `/dashboard/content/calendar` — Calendar view of scheduled/delivered content
- `/dashboard/content/kanban` — Kanban board view by status

### Related Sections

- S03 (Channels) — filter by channel
- S07 (Progress) — job status tracking
- S08 (Review) — pending review items

### Features

#### Content List Page

1. **Grouped List:** Videos grouped by day/week/month/quarter/year
2. **Status Filters:** By job status (researching, scripting, assembling, pending_review, delivered, failed, etc.)
3. **Review State Filter:** pending, approved, rejected
4. **Content Mode Filter:** short, long_form
5. **Channel Filter:** Per-channel view
6. **Cursor Pagination:** Infinite scroll with next_cursor
7. **Search:** Full-text search across titles/topics
8. **Bulk Actions:** Bulk approve, reject, retry, delete with confirmation
9. **Content Stats:** Aggregated stats by period with channel breakdown

#### Calendar Page

1. **Month/Week View:** Calendar grid with video cards on delivery dates
2. **Date Range:** Configurable start/end
3. **Channel Filter:** Per-channel calendar

#### Kanban Page

1. **Status Columns:** Cards grouped by status lane
2. **Drag & Drop:** Move cards between statuses (if implemented)
3. **Card Details:** Title, channel, cost, duration, thumbnail preview

### API Inventory

| API Endpoint                           | v2 Module | Status | Notes                                        |
| -------------------------------------- | --------- | ------ | -------------------------------------------- |
| `GET /api/v2/content`                  | content   | ✅     | Grouped list with filters, cursor pagination |
| `GET /api/v2/content/search`           | content   | ✅     | Full-text search                             |
| `POST /api/v2/content/bulk`            | content   | ✅     | Bulk actions (approve/reject/retry/delete)   |
| `GET /api/v2/content/calendar`         | content   | ✅     | Calendar data                                |
| `GET /api/v2/content/{id}`             | content   | ✅     | Single video detail                          |
| `GET /api/v2/content/stats`            | content   | ✅     | Aggregated stats                             |
| `POST /api/v2/content/trigger`         | content   | ✅     | Trigger from content page                    |
| `GET /api/v2/content/triggers/history` | content   | ✅     | Trigger history                              |

### FE Client Functions Used

- `contentApi.list()`, `contentApi.search()`, `contentApi.bulk()`, `contentApi.calendar()`, `contentApi.detail()`, `contentApi.stats()`, `contentApi.trigger()`, `contentApi.triggerHistory()`

### Pending Investigation

- [ ] Does grouping by day/week/month work correctly with timezone?
- [ ] Is cursor pagination working (no duplicates, no gaps)?
- [ ] Are bulk actions atomic? What happens if some fail?
- [ ] Does search index titles, topics, channel names?
- [ ] Is the calendar showing correct dates (scheduled_for vs delivered_at)?
- [ ] Does kanban drag-and-drop actually update status?
- [ ] Are content stats accurate (buckets, by_channel breakdown)?

---

## S05 — Library

**Route:** `/dashboard/library`
**Sidebar label:** Library
**Pillar:** Create
**Purpose:** Digital Asset Management (DAM) — browse, search, upload, and organize assets (images, videos, audio, brand kits, music).

### Child Routes

None (all functionality in single page with tabs/modals).

### Related Sections

- S03 (Channels) — channel-scoped assets, brand kits
- S12 (Workspace) — workspace-scoped assets

### Features

#### Asset Browser

1. **Asset Grid/List:** Browse all uploaded assets
2. **Scope Filtering:** workspace, channel, brand scoped
3. **Kind Filtering:** image, video, audio, document
4. **Tag Filtering:** By user-defined tags
5. **Search:** Semantic search + text search
6. **Upload:** Drag-and-drop with preflight (SHA256 dedup)
7. **Asset Detail:** Preview, metadata, license, tags, expiry
8. **Edit Metadata:** Display name, tags, license, expiry
9. **Delete:** Soft/hard delete

#### Collections

1. **Smart Collections:** Query-based auto-collections
2. **Manual Collections:** Curated asset groups
3. **Collection CRUD:** Create, update, delete

#### Brand Kits

1. **Brand Kit List:** Per-scope brand kits
2. **Brand Kit CRUD:** Name, palette, notes
3. **Asset Binding:** Bind assets to brand kits

#### Licenses & Quotas

1. **License Tracking:** Per-asset license attribution
2. **Storage Quotas:** Per-workspace storage limits
3. **Quota Enforcement:** Block uploads when quota exceeded

### API Inventory

| API Endpoint                                  | v2 Module        | Status | Notes              |
| --------------------------------------------- | ---------------- | ------ | ------------------ |
| `GET /api/v2/library/assets`                  | library          | ✅     | List assets        |
| `GET /api/v2/library/brand`                   | library          | ✅     | Brand assets       |
| `GET /api/v2/library/music`                   | library          | ✅     | Music assets       |
| `GET /api/v2/library/dam/assets`              | library          | ✅     | DAM asset list     |
| `POST /api/v2/library/dam/assets/preflight`   | library          | ✅     | SHA256 dedup check |
| `GET /api/v2/library/dam/assets/{id}`         | library          | ✅     | Asset detail       |
| `PATCH /api/v2/library/dam/assets/{id}`       | library          | ✅     | Update metadata    |
| `DELETE /api/v2/library/dam/assets/{id}`      | library          | ✅     | Delete asset       |
| `GET /api/v2/library/dam/tags`                | library          | ✅     | Tag list           |
| `POST /api/v2/library/dam/search`             | library          | ✅     | Semantic search    |
| `GET /api/v2/library/dam/collections`         | library          | ✅     | List collections   |
| `POST /api/v2/library/dam/collections`        | library          | ✅     | Create collection  |
| `PUT /api/v2/library/dam/collections/{id}`    | library          | ✅     | Update collection  |
| `DELETE /api/v2/library/dam/collections/{id}` | library          | ✅     | Delete collection  |
| `GET /api/v2/library/dam/brand-kits`          | library          | ✅     | List brand kits    |
| `POST /api/v2/library/dam/brand-kits`         | library          | ✅     | Create brand kit   |
| `PUT /api/v2/library/dam/brand-kits/{id}`     | library          | ✅     | Update brand kit   |
| License endpoints                             | library_licenses | ✅     | License CRUD       |
| Quota endpoints                               | library_quotas   | ✅     | Quota CRUD         |

### FE Client Functions Used

- `libraryApi.*`, `damApi.*`

### Pending Investigation

- [ ] Is semantic search actually working (vector embeddings)?
- [ ] Does SHA256 preflight prevent duplicate uploads?
- [ ] Are storage quotas enforced at upload time?
- [ ] Do smart collections auto-update when new assets match?
- [ ] Are brand kit bindings working (asset → brand kit)?
- [ ] Is license metadata preserved through the pipeline?

---

## S06 — Queue

**Route:** `/dashboard/queue`
**Sidebar label:** Queue
**Pillar:** Operate
**Purpose:** Currently a redirect stub to `/dashboard/progress`. Intended to show the job queue with scheduling, prioritization, and capacity management.

### Current Status: STUB

- `page.tsx`: 10-line redirect to `/dashboard/progress`
- No dedicated v2 API
- No dedicated FE client functions

### Child Routes

None.

### Related Sections

- S07 (Progress) — currently redirects here
- S04 (Content) — job triggering

### Features (Planned/Expected)

1. **Job Queue View:** All pending/scheduled jobs in queue order
2. **Priority Management:** Reorder jobs by priority
3. **Capacity Indicators:** Available slots per content_mode
4. **Schedule Calendar:** When jobs are scheduled to run
5. **Queue Actions:** Move to top, move to bottom, remove from queue
6. **Bulk Schedule:** Schedule multiple jobs at once

### Pending Investigation

- [ ] Should Queue be a separate page or remain merged with Progress?
- [ ] What queue backend? (Temporal task queues? Redis? DB?)
- [ ] How does prioritization work?
- [ ] What capacity constraints exist?

---

## S07 — Progress

**Route:** `/dashboard/progress`
**Sidebar label:** Progress
**Pillar:** Operate
**Purpose:** Job progress monitoring — view all active, paused, failed, and recently completed jobs with real-time progress updates.

### Child Routes

- `/dashboard/jobs/[id]` — Job detail page with phase timeline, output preview, metadata

### Related Sections

- S03 (Channels) — per-channel job controls
- S04 (Content) — content list
- S06 (Queue) — queue redirect target
- S08 (Review) — pending review jobs

### Features

#### Progress List Page

1. **Job Cards:** Active/paused/failed/stopped jobs with status, channel, content_mode, progress %
2. **Job Controls:** Pause, Resume, Stop, Retry, Restart per job
3. **Phase Timeline:** Current phase indicator (researching → scripting → voicing → assembling → reviewing → delivering)
4. **Progress Bars:** Visual progress per job
5. **Cost Tracking:** Per-job cost display
6. **Error Display:** Error messages for failed jobs
7. **WebSocket Updates:** Real-time progress via WS
8. **Filtering:** By status, channel, content_mode
9. **BorderBeam Animation:** Running jobs get animated border

#### Job Detail Page

1. **Phase Timeline:** Full phase history with timestamps
2. **Output Preview:** Video player, thumbnail preview
3. **Metadata View:** Script, research data, voice config, assembly params
4. **Job Events:** Chronological event log
5. **Cost Breakdown:** Per-phase cost tracking
6. **Retry/Restart:** With checkpoint resume support
7. **Approve/Reject:** Direct review actions

### API Inventory

| API Endpoint                     | v2 Module | Status | Notes                   |
| -------------------------------- | --------- | ------ | ----------------------- |
| `GET /api/v2/jobs/active`        | jobs      | ✅     | Active jobs list        |
| `GET /api/v2/jobs/{id}/progress` | jobs      | ✅     | Job progress detail     |
| `GET /api/v2/jobs/{id}/output`   | jobs      | ✅     | Output preview          |
| `GET /api/v2/jobs/{id}/metadata` | jobs      | ✅     | Job metadata            |
| `POST /api/v2/jobs/{id}/approve` | jobs      | ✅     | Approve job             |
| `POST /api/v2/jobs/{id}/reject`  | jobs      | ✅     | Reject job              |
| `POST /api/v2/jobs/{id}/retry`   | jobs      | ✅     | Retry (new content_id)  |
| `POST /api/v2/jobs/{id}/restart` | jobs      | ✅     | Restart from checkpoint |
| `POST /api/v2/jobs/{id}/pause`   | jobs      | ✅     | Pause workflow          |
| `POST /api/v2/jobs/{id}/resume`  | jobs      | ✅     | Resume workflow         |
| `POST /api/v2/jobs/{id}/stop`    | jobs      | ✅     | Stop/terminate          |
| `WS /api/ws/progress/{id}`       | main.py   | ✅     | Per-job progress WS     |

### FE Client Functions Used

- `jobsApi.*`, `wsProgress()`

### Pending Investigation

- [ ] Does retry correctly supersede old failed jobs?
- [ ] Does restart correctly resume from checkpoint?
- [ ] Are Temporal workflow signals (pause/resume/stop) reliable?
- [ ] Does the progress WS push updates for every phase transition?
- [ ] Is the phase timeline accurate (no missing phases)?
- [ ] Are orphaned workflows (DB says running, Temporal says gone) handled?
- [ ] Does cost tracking include all phases?
- [ ] Is the output preview working for all content_modes?

---

## S08 — Review

**Route:** `/dashboard/review`
**Sidebar label:** Review
**Pillar:** Operate
**Purpose:** Human review queue — approve, reject, edit, and comment on videos before they're published.

### Child Routes

- `/dashboard/review/[id]` — Review detail with video player, script, thumbnail, metadata
- `/dashboard/review/[id]/diff` — Script diff view for edited scripts

### Related Sections

- S03 (Channels) — per-channel review config
- S04 (Content) — content list with review state
- S07 (Progress) — job progress leading to pending_review

### Features

#### Review Queue Page

1. **Review Queue:** Filterable by state (pending, approved, rejected), channel
2. **Review Cards:** Thumbnail, title, channel, script preview, cost
3. **Quick Actions:** Approve, reject from queue
4. **3D Tilt Cards:** Motion animation on hover
5. **Approve Animation:** Green bloom + confetti on approve
6. **Reject Animation:** X-shake on reject

#### Review Detail Page

1. **Video Player:** Embedded video preview
2. **Script Viewer:** Full script with editing capability
3. **Thumbnail Preview:** Current thumbnail with regenerate option
4. **Metadata View:** All job metadata
5. **Comments:** Thread-based review comments
6. **Decision:** Approve/Reject with summary
7. **Title Editing:** Edit title, hook, topic
8. **Thumbnail Regeneration:** Regenerate with prompt nudge
9. **Script Editing:** Inline script editing with diff view

### API Inventory

| API Endpoint                                    | v2 Module | Status | Notes                     |
| ----------------------------------------------- | --------- | ------ | ------------------------- |
| `GET /api/v2/review/queue`                      | review    | ✅     | Review queue with filters |
| `GET /api/v2/review/{id}`                       | review    | ✅     | Review detail             |
| `POST /api/v2/review/{id}/open`                 | review    | ✅     | Open for review           |
| `POST /api/v2/review/{id}/decide`               | review    | ✅     | Approve/reject decision   |
| `POST /api/v2/review/{id}/script/edit`          | review    | ✅     | Edit script               |
| `POST /api/v2/review/{id}/thumbnail/regenerate` | review    | ✅     | Regenerate thumbnail      |
| `POST /api/v2/review/{id}/comments`             | review    | ✅     | Add comment               |
| `PUT /api/v2/review/{id}/title`                 | review    | ✅     | Update title/hook/topic   |

### FE Client Functions Used

- `reviewApi.*`

### Pending Investigation

- [ ] Does approve trigger the delivery workflow?
- [ ] Does reject trigger retry or mark as failed?
- [ ] Are review comments threaded (replies)?
- [ ] Does script editing create a diff that can be reviewed?
- [ ] Does thumbnail regeneration use the same provider chain?
- [ ] Are review decisions audited?
- [ ] Does the review config (hands_off/quick/standard/full_control) actually gate which phases require review?

---

## S09 — Fleet

**Route:** `/dashboard/fleet`
**Sidebar label:** Fleet
**Pillar:** Operate
**Purpose:** Fleet health monitoring — real-time status of all backend services, database pool, Remotion render queue, and system pressure metrics.

### Child Routes

None.

### Related Sections

- S01 (Home) — System Health ECG card
- S16 (Settings) — emergency stop
- S17 (Debug) — shares fleet health data

### Features

1. **Service Health Grid:** Per-service status (research, script, voice, assets, thumbnail, assembly, delivery, analytics, admin, direction, brand, editor)
2. **Health Indicators:** Green/red per service with latency
3. **DB Pool Stats:** Size, idle, min, max, pressure %
4. **Remotion Queue:** Active renders, waiting, max concurrent, memory
5. **Pressure Metrics (24h):** Quality gate blocks, video failures
6. **Gate Calibration:** Niches calibrated, auto vs default dims
7. **Niche Pulse:** Saturation scorer freshness
8. **Retention Coverage:** Curve fetch coverage %
9. **Diversity Floor:** Forced explorations, force rate
10. **Calibration Health:** Brier score, ECE, weighted fraction
11. **Aggregate Health Score:** Weighted score with traffic-light band
12. **Scale Config:** Temporal max activities, DB statement timeout

### API Inventory

| API Endpoint                      | v2 Module | Status | Notes                     |
| --------------------------------- | --------- | ------ | ------------------------- |
| `GET /api/v2/system/fleet-health` | system    | ✅     | Full fleet health payload |

### FE Client Functions Used

- `systemApi.fleetHealth()`

### Pending Investigation

- [ ] Are all 12 services actually running and returning health checks?
- [ ] Is the aggregate health score calculation correct?
- [ ] Does the fleet health endpoint timeout gracefully (per-service 3s timeout)?
- [ ] Are the pressure metrics accurate (quality_gate_blocks, video_failures)?
- [ ] Is Remotion queue data real-time?
- [ ] Does DB pool pressure reflect actual load?

---

## S10 — Analytics

**Route:** `/dashboard/analytics`
**Sidebar label:** Analytics
**Pillar:** Measure
**Purpose:** Analytics dashboard — channel performance, cost analysis, content trends, viewer metrics.

### Current Status: MISSING

- **No `page.tsx` exists** — no directory at `/dashboard/analytics/`
- **No dedicated v2 analytics API module** — analytics data is partially embedded in fleet-health and stats endpoints
- Backend service exists at `src/services/analytics/` but has no v2 API surface

### Child Routes

None defined.

### Related Sections

- S01 (Home) — summary stats
- S03 (Channels) — per-channel analytics
- S04 (Content) — content performance
- S09 (Fleet) — system health metrics

### Features (Planned/Expected)

1. **Channel Performance:** Views, watch time, subscribers per channel
2. **Cost Analysis:** Cost per video, cost per view, provider breakdown
3. **Content Trends:** Top performing topics, formats, durations
4. **Viewer Metrics:** Retention curves, CTR, engagement
5. **Export:** CSV/PDF export of analytics data
6. **Date Range:** Configurable time periods
7. **Comparison:** Period-over-period comparison
8. **A/B Test Results:** Experiment outcome visualization

### API Inventory — NONE (needs full implementation)

### Pending Investigation

- [ ] What analytics data is already being collected (analytics_records table)?
- [ ] Is YouTube Analytics API integrated?
- [ ] What metrics matter most for the MVP?
- [ ] Should this be a separate service or part of the dashboard BFF?
- [ ] What visualization library? (Recharts? D3? Tremor?)

---

## S11 — Experiments

**Route:** `/dashboard/experiments`
**Sidebar label:** Experiments
**Pillar:** Measure
**Purpose:** A/B testing framework — create, run, and analyze experiments on content variables (thumbnails, titles, topics, formats).

### Child Routes

None.

### Related Sections

- S03 (Channels) — per-channel experiments
- S10 (Analytics) — experiment results visualization

### Features

1. **Experiment List:** All experiments with status (draft, active, paused, completed)
2. **Experiment Create:** Define variants, metrics, traffic split
3. **Activate/Pause:** Control experiment lifecycle
4. **Complete:** End experiment with winner selection
5. **Results:** Statistical analysis of outcomes
6. **Variant Assignment:** Bandit-based or random assignment
7. **Outcome Tracking:** Per-variant performance metrics

### API Inventory

| API Endpoint                               | v2 Module   | Status | Notes                   |
| ------------------------------------------ | ----------- | ------ | ----------------------- |
| `GET /api/v2/experiments`                  | experiments | ✅     | List with status filter |
| `POST /api/v2/experiments`                 | experiments | ✅     | Create experiment       |
| `POST /api/v2/experiments/{name}/activate` | experiments | ✅     | Activate                |
| `POST /api/v2/experiments/{name}/pause`    | experiments | ✅     | Pause                   |
| `POST /api/v2/experiments/{name}/complete` | experiments | ✅     | Complete with winner    |
| `GET /api/v2/experiments/{name}/results`   | experiments | ✅     | Results                 |

### FE Client Functions Used

- `experimentsApi.*`

### Pending Investigation

- [ ] What experiment types are supported? (thumbnail, title, topic, format?)
- [ ] Is the bandit algorithm (Thompson sampling?) working correctly?
- [ ] Are results statistically significant (sample size, confidence)?
- [ ] Does completing an experiment apply the winner automatically?
- [ ] Are experiment assignments persisted across sessions?

---

## S12 — Workspace

**Route:** `/dashboard/workspace`
**Sidebar label:** Workspace
**Pillar:** Configure
**Purpose:** Workspace management — name, slug, plan, mode (solo/teams), integrations, members, brands, series, campaigns, projects.

### Child Routes

None (all managed through tabs/modals on the same page).

### Related Sections

- S13 (Teams) — member management
- S15 (Providers) — workspace-scoped credentials
- S16 (Settings) — workspace-level settings

### Features

1. **Workspace Profile:** Name, slug, plan
2. **Mode Toggle:** Solo vs Teams mode
3. **Integrations:** Slack webhook URL
4. **Members List:** All workspace members with roles
5. **Invite Management:** Create, revoke invites
6. **Role Management:** Change member roles (owner/member/viewer)
7. **Member Removal:** Remove members from workspace
8. **Ownership Transfer:** Password-verified ownership handoff
9. **Brands CRUD:** Workspace-level brands
10. **Series CRUD:** Content series management
11. **Campaigns CRUD:** Marketing campaigns
12. **Projects CRUD:** Content projects with channel/series/campaign binding
13. **Audit Log:** Workspace-level audit trail

### API Inventory

| API Endpoint                                | v2 Module | Status | Notes               |
| ------------------------------------------- | --------- | ------ | ------------------- |
| `GET /api/v2/workspace`                     | workspace | ✅     | Workspace detail    |
| `PUT /api/v2/workspace`                     | workspace | ✅     | Update workspace    |
| `GET /api/v2/workspace/integrations`        | workspace | ✅     | Get integrations    |
| `PUT /api/v2/workspace/integrations`        | workspace | ✅     | Update integrations |
| `GET /api/v2/workspace/members`             | workspace | ✅     | List members        |
| `PUT /api/v2/workspace/members/{id}/role`   | workspace | ✅     | Change role         |
| `DELETE /api/v2/workspace/members/{id}`     | workspace | ✅     | Remove member       |
| `POST /api/v2/workspace/transfer-ownership` | workspace | ✅     | Transfer ownership  |
| `GET /api/v2/workspace/invites`             | workspace | ✅     | List invites        |
| `POST /api/v2/workspace/invites`            | workspace | ✅     | Create invite       |
| `DELETE /api/v2/workspace/invites/{id}`     | workspace | ✅     | Revoke invite       |
| `GET /api/v2/workspace/brands`              | workspace | ✅     | List brands         |
| `GET /api/v2/workspace/brands/{id}`         | workspace | ✅     | Brand detail        |
| `POST /api/v2/workspace/brands`             | workspace | ✅     | Create brand        |
| `PUT /api/v2/workspace/brands/{id}`         | workspace | ✅     | Update brand        |
| `GET /api/v2/workspace/series`              | workspace | ✅     | List series         |
| `POST /api/v2/workspace/series`             | workspace | ✅     | Create series       |
| `PUT /api/v2/workspace/series/{id}`         | workspace | ✅     | Update series       |
| `DELETE /api/v2/workspace/series/{id}`      | workspace | ✅     | Delete series       |
| `GET /api/v2/workspace/campaigns`           | workspace | ✅     | List campaigns      |
| `POST /api/v2/workspace/campaigns`          | workspace | ✅     | Create campaign     |
| `PUT /api/v2/workspace/campaigns/{id}`      | workspace | ✅     | Update campaign     |
| `GET /api/v2/workspace/projects`            | workspace | ✅     | List projects       |
| `GET /api/v2/workspace/projects/{id}`       | workspace | ✅     | Project detail      |
| `POST /api/v2/workspace/projects`           | workspace | ✅     | Create project      |
| `PUT /api/v2/workspace/projects/{id}`       | workspace | ✅     | Update project      |
| `DELETE /api/v2/workspace/projects/{id}`    | workspace | ✅     | Delete project      |
| `GET /api/v2/workspace/settings`            | workspace | ✅     | Entity settings     |

### FE Client Functions Used

- `workspaceApi.*`, `membersApi.*`, `invitesApi.*`, `brandsApi.*`, `seriesApi.*`, `campaignsApi.*`, `projectsApi.*`, `settingsApi.*`

### Pending Investigation

- [ ] Does solo vs teams mode actually change behavior?
- [ ] Is Slack integration working (webhook dispatch)?
- [ ] Does ownership transfer require password + invalidate sessions?
- [ ] Is the last-owner demotion guard working?
- [ ] Are invites expiring correctly?
- [ ] Does accept-invite flow work end-to-end?
- [ ] Are brands/series/campaigns/projects actually used in the pipeline?
- [ ] Is the audit log readable and filterable?

---

## S13 — Teams

**Route:** `/dashboard/teams`
**Sidebar label:** Teams
**Pillar:** Configure
**Purpose:** Team management within a workspace — create teams, assign members, set team-level permissions.

### Child Routes

None.

### Related Sections

- S12 (Workspace) — member management
- S14 (Users) — user management (superadmin)

### Features

1. **Team List:** All teams in workspace
2. **Team CRUD:** Create, update, delete teams
3. **Member Assignment:** Add/remove members to teams
4. **Team Permissions:** Team-level access control
5. **Team Scoping:** Scope channels/projects to teams

### API Inventory

Currently uses workspace members API. Dedicated teams API may be needed.

### Pending Investigation

- [ ] Is Teams fully implemented or just a stub?
- [ ] How do teams differ from workspace members?
- [ ] Are team-level permissions implemented?
- [ ] Can channels/projects be scoped to teams?

---

## S14 — Users

**Route:** `/dashboard/users`
**Sidebar label:** Users
**Pillar:** Configure
**Purpose:** Platform-level user management (superadmin only) — list all users, disable/enable, delete, transfer superadmin.

### Child Routes

None.

### Related Sections

- S12 (Workspace) — workspace members
- S13 (Teams) — team members

### Features

1. **User List:** All platform users with roles, status
2. **Disable/Enable:** Suspend or reactivate user accounts
3. **Delete:** Hard delete user account
4. **Transfer Superadmin:** Hand off superadmin role to another user

### API Inventory

| API Endpoint                                  | v2 Module | Status | Notes               |
| --------------------------------------------- | --------- | ------ | ------------------- |
| `GET /api/v2/users`                           | users     | ✅     | List all users      |
| `POST /api/v2/users/transfer-superadmin/{id}` | users     | ✅     | Transfer superadmin |
| `PUT /api/v2/users/{id}/disable`              | users     | ✅     | Disable user        |
| `PUT /api/v2/users/{id}/enable`               | users     | ✅     | Enable user         |
| `DELETE /api/v2/users/{id}`                   | users     | ✅     | Delete user         |

### FE Client Functions Used

- `usersApi.*`

### Pending Investigation

- [ ] Is the superadmin guard working (only superadmin can access)?
- [ ] Does disabling a user revoke their sessions?
- [ ] Does deleting a user cascade correctly (workspace memberships, owned content)?
- [ ] Is superadmin transfer atomic (no gap without superadmin)?

---

## S15 — Providers

**Route:** `/dashboard/providers`
**Sidebar label:** Providers
**Pillar:** Configure
**Purpose:** Provider/API key management — the operations center for all third-party API integrations (LLM, TTS, storage, YouTube, etc.).

### Child Routes

- `/dashboard/providers/[category]` — Category-specific provider management

### Related Sections

- S03 (Channels) — channel-scoped credential overrides
- S16 (Settings) — feature flags for provider features
- S12 (Workspace) — workspace-scoped credentials

### Features (every minute detail)

#### Provider Catalog & Marketplace

1. **Provider Sections (Kinds):** Grouped by capability (LLM, TTS, Image, Video, Storage, Search, YouTube)
2. **Custom Sections:** User-created provider sections
3. **Marketplace Catalog:** All available providers with connected status, supported models, pricing tier, free tier, config schema
4. **Custom Providers:** User-added marketplace providers
5. **Restore Defaults:** Reset to system provider catalog

#### Credential Management

1. **Credential List:** Per-category, with health status, rotation status, enabled/disabled
2. **Add Credential:** Manual entry (API key, model, extra config)
3. **Wizard Add:** Guided form based on provider's config_schema
4. **Edit Credential:** Update label, model, extra config
5. **Delete Credential:** Remove with cascade checks
6. **Enable/Disable:** Toggle credential without deleting (preserves chains)
7. **Test Credential:** Live test with latency measurement
8. **Rotate Credential:** Key rotation with hint tracking
9. **Rotation Status:** Days since rotation, overdue warnings
10. **Default Fallback:** Mark credential as default fallback for category
11. **Bookmark/Default:** Set/unset as default fallback

#### Provider Chains (Priority/Routing)

1. **Chain View:** Ordered list of credentials per category
2. **Reorder:** Drag-and-drop priority reordering
3. **Chain V2 (Multi-Scope):** workspace-level, channel-level, content_mode-level chains
4. **Resolved Chain:** Show effective chain for a given channel + content_mode
5. **Chain Entry Enable/Disable:** Toggle individual entries in chain
6. **Content Mode Chains:** Different chains for short vs long_form

#### Routing Policies

1. **Routing Policy:** round_robin, fallback, lowest_cost, highest_throughput
2. **Scope-Aware Routing:** Different policies per scope (workspace/channel)
3. **Custom Rules:** Per-route custom routing rules
4. **Fallback Chain:** Ordered fallback when primary fails

#### Quota Management

1. **Quota List:** Per-scope monthly caps
2. **Create Quota:** Set monthly_cap_usd, alert_pct, hard_limit
3. **Update Quota:** Adjust caps and policies
4. **Delete Quota:** Remove quota
5. **Alert Thresholds:** Notify when approaching quota

#### Health Monitoring

1. **Health History:** Per-credential health check history
2. **Probe All:** Fan-out health check all enabled credentials
3. **Health Stream:** SSE stream of live health status
4. **Setup Checklist:** Which categories have configured + healthy credentials

#### Sandbox / Testing

1. **Sandbox Run:** Test inference with a credential
2. **Sandbox History:** Recent test run results

#### Audit & Change Requests

1. **Audit Log:** Per-category, per-credential audit trail
2. **Change Requests:** Member requests credential changes → Admin approval → Owner approval workflow
3. **Change Request Types:** add_credential, change_chain_priority, remove_credential, change_model, rotate_credential
4. **Dual Approval:** Admin reviews → forwards to Owner → Owner approves/rejects

#### YouTube OAuth

1. **OAuth Flow:** Connect YouTube channel via OAuth
2. **Connection Status:** Connected channel name, avatar, scopes
3. **Disconnect:** Revoke YouTube access
4. **Scope Validation:** Check for missing scopes

#### Content Modes

1. **Content Mode List:** System + custom content modes
2. **Mode-Aware Chains:** Different provider chains per content mode

### API Inventory

| API Endpoint                                                 | v2 Module       | Status | Notes                     |
| ------------------------------------------------------------ | --------------- | ------ | ------------------------- |
| `GET /api/v2/providers/categories`                           | providers       | ✅     | Category list             |
| `GET /api/v2/providers/kinds`                                | providers       | ✅     | Provider sections         |
| `POST /api/v2/providers/kinds`                               | providers       | ✅     | Create section            |
| `DELETE /api/v2/providers/kinds/{kind}`                      | providers       | ✅     | Delete section            |
| `POST /api/v2/providers/categories`                          | providers       | ✅     | Create category           |
| `PATCH /api/v2/providers/categories/{name}`                  | providers       | ✅     | Update category           |
| `DELETE /api/v2/providers/categories/{name}`                 | providers       | ✅     | Delete category           |
| `GET /api/v2/providers/marketplace`                          | providers       | ✅     | Marketplace catalog       |
| `POST /api/v2/providers/marketplace`                         | providers       | ✅     | Add custom provider       |
| `DELETE /api/v2/providers/marketplace/{key}`                 | providers       | ✅     | Remove custom provider    |
| `GET /api/v2/providers/catalog-for-category`                 | providers       | ✅     | Catalog for category      |
| `POST /api/v2/providers/restore-defaults`                    | providers       | ✅     | Restore defaults          |
| `GET /api/v2/providers/credentials`                          | providers       | ✅     | List credentials          |
| `POST /api/v2/providers/credentials`                         | providers       | ✅     | Create credential         |
| `PUT /api/v2/providers/credentials/{id}`                     | providers       | ✅     | Update credential         |
| `DELETE /api/v2/providers/credentials/{id}`                  | providers       | ✅     | Delete credential         |
| `POST /api/v2/providers/credentials/{id}/test`               | providers       | ✅     | Test credential           |
| `POST /api/v2/providers/credentials/{id}/rotate`             | providers       | ✅     | Rotate key                |
| `POST /api/v2/providers/credentials/from-wizard`             | providers       | ✅     | Wizard create             |
| `GET /api/v2/providers/setup-checklist`                      | providers       | ✅     | Setup checklist           |
| `GET /api/v2/providers/credentials/{id}/rotation-status`     | providers       | ✅     | Rotation status           |
| `GET /api/v2/providers/credentials/rotation-status`          | providers       | ✅     | All rotation status       |
| `PUT /api/v2/providers/credentials/{id}/default-fallback`    | providers       | ✅     | Set default fallback      |
| `DELETE /api/v2/providers/credentials/{id}/default-fallback` | providers       | ✅     | Clear default fallback    |
| `PUT /api/v2/providers/credentials/{id}/enabled`             | providers       | ✅     | Enable/disable credential |
| `GET /api/v2/providers/chains/{category}`                    | providers       | ✅     | Get chain                 |
| `PUT /api/v2/providers/chains/{category}`                    | providers       | ✅     | Set chain                 |
| `GET /api/v2/providers/chains`                               | providers       | ✅     | Chains V2 (multi-scope)   |
| `PUT /api/v2/providers/chains`                               | providers       | ✅     | Upsert chain V2           |
| `DELETE /api/v2/providers/chains`                            | providers       | ✅     | Delete chain V2           |
| `PUT /api/v2/providers/chains/entry/{id}/enabled`            | providers       | ✅     | Toggle chain entry        |
| `PATCH /api/v2/providers/chains/reorder`                     | providers       | ✅     | Reorder chain             |
| `GET /api/v2/providers/resolved`                             | providers       | ✅     | Resolved chain            |
| `GET /api/v2/providers/routes`                               | providers       | ✅     | Routing policies          |
| `PUT /api/v2/providers/routes/{category}`                    | providers       | ✅     | Set routing policy        |
| `GET /api/v2/providers/quotas`                               | providers       | ✅     | Quota list                |
| `POST /api/v2/providers/quotas`                              | providers       | ✅     | Create quota              |
| `PUT /api/v2/providers/quotas/{id}`                          | providers       | ✅     | Update quota              |
| `DELETE /api/v2/providers/quotas/{id}`                       | providers       | ✅     | Delete quota              |
| `GET /api/v2/providers/health/{id}`                          | providers       | ✅     | Health history            |
| `POST /api/v2/providers/health/probe-all`                    | providers       | ✅     | Probe all                 |
| `GET /api/v2/providers/health-stream`                        | providers       | ✅     | Health SSE stream         |
| `POST /api/v2/providers/sandbox/run`                         | providers       | ✅     | Sandbox test              |
| `GET /api/v2/providers/sandbox/runs`                         | providers       | ✅     | Sandbox history           |
| `GET /api/v2/providers/audit-log`                            | providers       | ✅     | Provider audit log        |
| `GET /api/v2/providers/registered`                           | providers       | ✅     | Registered providers      |
| `GET /api/v2/providers/models`                               | providers       | ✅     | Supported models          |
| `GET /api/v2/providers/content-modes`                        | providers       | ✅     | Content modes             |
| `GET /api/v2/providers/change-requests`                      | change_requests | ✅     | List change requests      |
| `POST /api/v2/providers/change-requests`                     | change_requests | ✅     | Create change request     |
| `GET /api/v2/providers/change-requests/{id}`                 | change_requests | ✅     | Get change request        |
| `POST /api/v2/providers/change-requests/{id}/admin-review`   | change_requests | ✅     | Admin review              |
| `POST /api/v2/providers/change-requests/{id}/owner-review`   | change_requests | ✅     | Owner review              |
| `GET /api/v2/providers/youtube/auth`                         | youtube_oauth   | ✅     | YouTube OAuth URL         |
| `GET /api/v2/providers/youtube/status`                       | youtube_oauth   | ✅     | OAuth status              |
| `DELETE /api/v2/providers/youtube/disconnect`                | youtube_oauth   | ✅     | Disconnect                |
| `POST /api/v2/providers/_admin/clean-slate`                  | providers       | ✅     | Admin reset               |

### FE Client Functions Used

- `providersApi.*`, `changeRequestsApi.*`, `youtubeOAuthApi.*`

### Pending Investigation — CRITICAL (most complex section)

- [ ] **Multi-Scope Config Resolution:** When a channel has a channel-level chain AND a content_mode-level chain, which wins? What's the resolution order? (channel+mode > channel > workspace+mode > workspace > default)
- [ ] **Enable/Disable Logic:** When a credential is disabled, does it get skipped in the chain? Does disabling the last enabled credential in a chain cause errors? What happens to in-flight jobs?
- [ ] **Default Fallback:** How does the "default fallback" interact with chains? Is it used when all chain entries fail?
- [ ] **Chain Reordering:** Is the reorder atomic? Does it affect in-flight jobs?
- [ ] **Routing Policy:** Is round_robin actually round-robin? Is fallback actually falling back? Is lowest_cost comparing real-time pricing?
- [ ] **Test Credential:** Does it test the actual API call or just connectivity? What capabilities are tested?
- [ ] **Key Rotation:** Does rotation update the vault atomically? Is there a rollback on failure? Does it invalidate the old key?
- [ ] **Change Request Flow:** Does the dual-approval (admin → owner) work end-to-end? What happens if admin rejects? What if owner rejects? What if the request expires?
- [ ] **Quota Enforcement:** Are hard limits actually blocking API calls? Are alert thresholds triggering notifications?
- [ ] **Health Probes:** Are they running on a schedule or only on-demand? Are unhealthy credentials auto-disabled?
- [ ] **YouTube OAuth:** Does the OAuth flow handle token refresh? What scopes are required?
- [ ] **Sandbox:** Does sandbox run use real API calls? Are costs tracked?
- [ ] **Audit Log:** Is every credential mutation audited? Is the log queryable by category, credential, action?
- [ ] **Content Mode Chains:** Do short and long_form actually resolve different chains?
- [ ] **Provider Catalog:** Are supported_models validated against the actual provider API?
- [ ] **Setup Checklist:** Is "healthy" determined by recent probe or just configuration existence?

---

## S16 — Settings

**Route:** `/dashboard/settings`
**Sidebar label:** Settings
**Pillar:** Configure
**Purpose:** System configuration — feature flags, system config, emergency controls, environment info.

### Child Routes

- `/dashboard/settings/flags` — Feature flag management

### Related Sections

- S09 (Fleet) — emergency stop
- S15 (Providers) — provider feature flags
- S12 (Workspace) — workspace settings

### Features

#### Settings Page

1. **System Config:** Key-value config editor (daily_budget_limit, emergency_stop, etc.)
2. **Emergency Stop:** Freeze all operations (pause workflows, block triggers)
3. **Emergency Resume:** Unfreeze all operations
4. **Environment Info:** Production/test mode, version, deployment info
5. **Clean Slate:** Full system reset (truncate job tables, wipe storage, clear Redis)
6. **Test Data Management:** View/delete test data

#### Feature Flags Page

1. **Flag List:** All feature flags with enabled/disabled status, description, payload
2. **Toggle Flags:** Enable/disable flags
3. **Flag Payload:** Edit JSON payload for non-boolean flags
4. **Flag Categories:** Grouped by domain (auth, providers, pipeline, experiments, brain)

### API Inventory

| API Endpoint                           | v2 Module | Status | Notes              |
| -------------------------------------- | --------- | ------ | ------------------ |
| `GET /api/v2/system/config`            | system    | ✅     | System config list |
| `PUT /api/v2/system/config`            | system    | ✅     | Update config      |
| `POST /api/v2/system/emergency-stop`   | system    | ✅     | Emergency stop     |
| `POST /api/v2/system/emergency-resume` | system    | ✅     | Emergency resume   |
| `GET /api/v2/system/environment`       | system    | ✅     | Environment info   |
| `POST /api/v2/system/clean-slate`      | system    | ✅     | Clean slate        |
| `GET /api/v2/flags`                    | flags     | ✅     | List feature flags |
| `PUT /api/v2/flags/{key}`              | flags     | ✅     | Set flag           |

### FE Client Functions Used

- `systemApi.*`, `flagsApi.*`

### Pending Investigation

- [ ] Does emergency stop actually pause all running workflows?
- [ ] Does emergency resume actually resume all paused workflows?
- [ ] Is clean-slate safe (preserves channels, config, users)?
- [ ] Are feature flags taking effect within 30s (cache TTL)?
- [ ] Is the flag payload editor validating JSON?
- [ ] Are all system_config keys documented?

---

## S17 — Debug

**Route:** `/dashboard/debug`
**Sidebar label:** Debug
**Pillar:** Configure
**Purpose:** Developer debugging — fleet health raw data, critical alerts, notification deliveries.

### Child Routes

None.

### Related Sections

- S09 (Fleet) — fleet health data
- S02 (Notifications) — notification deliveries

### Features

1. **Fleet Health Raw:** JSON dump of fleet health endpoint
2. **Critical Alerts:** Last 20 critical notifications
3. **Delivery History:** Recent notification deliveries with status

### API Inventory

Uses existing `systemApi.fleetHealth()`, `notifyApi.list()`, `notifyApi.deliveries()`.

### Pending Investigation

- [ ] Should this be expanded with more debug tools?
- [ ] Should it be hidden in production?

---

## S18 — Profile

**Route:** `/dashboard/profile`
**Sidebar label:** (in ChromeBar user menu, not sidebar)
**Purpose:** User profile management — display name, email, password change, MFA setup, account deletion.

### Child Routes

None.

### Related Sections

- Auth — login, register

### Features

1. **Profile View:** Display name, email, role, workspace
2. **Update Profile:** Change display name
3. **Change Password:** Current password + new password
4. **MFA Setup:** TOTP-based two-factor authentication
5. **MFA Verify:** Verify MFA code during setup
6. **Delete Account:** Password-verified account deletion
7. **Workspace Switcher:** List and switch workspaces
8. **Create Workspace:** Create additional workspaces

### API Inventory

| API Endpoint                         | v2 Module | Status | Notes            |
| ------------------------------------ | --------- | ------ | ---------------- |
| `PUT /api/v2/auth/profile`           | auth      | ✅     | Update profile   |
| `DELETE /api/v2/auth/account`        | auth      | ✅     | Delete account   |
| `POST /api/v2/auth/mfa/setup`        | auth      | ✅     | MFA setup        |
| `POST /api/v2/auth/mfa/verify`       | auth      | ✅     | MFA verify       |
| `GET /api/v2/auth/workspaces`        | auth      | ✅     | List workspaces  |
| `POST /api/v2/auth/switch-workspace` | auth      | ✅     | Switch workspace |
| `POST /api/v2/auth/create-workspace` | auth      | ✅     | Create workspace |

### FE Client Functions Used

- `authApi.updateProfile()`, `authApi.deleteAccount()`, `authApi.mfaSetup()`, `authApi.mfaVerify()`, `authApi.listWorkspaces()`, `authApi.switchWorkspace()`, `authApi.createWorkspace()`

### Pending Investigation

- [ ] Does MFA setup generate valid TOTP URIs?
- [ ] Does MFA enforcement actually block login without code?
- [ ] Does account deletion cascade correctly?
- [ ] Does workspace switching invalidate old workspace tokens?
- [ ] Can a user be in multiple workspaces simultaneously?

---

## Auth (Login/Register)

**Routes:** `/login`, `/register`, `/forgot-password`, `/reset-password`, `/accept-invite`
**Purpose:** Authentication and registration flows.

### Features

1. **Login:** Email + password + optional MFA code
2. **Register:** Email + password + workspace name + display name
3. **Forgot Password:** Email-based reset token
4. **Reset Password:** Token + new password
5. **Accept Invite:** Token + optional password + display name
6. **Token Refresh:** HttpOnly cookie-based refresh
7. **Logout:** Clear cookies + server-side session invalidation
8. **Auth Mode Detection:** v2 vs legacy mode

### API Inventory

| API Endpoint                      | v2 Module | Status | Notes           |
| --------------------------------- | --------- | ------ | --------------- |
| `GET /api/v2/auth/mode`           | auth      | ✅     | Auth mode check |
| `POST /api/v2/auth/register`      | auth      | ✅     | Register        |
| `POST /api/v2/auth/login`         | auth      | ✅     | Login           |
| `POST /api/v2/auth/refresh`       | auth      | ✅     | Token refresh   |
| `POST /api/v2/auth/logout`        | auth      | ✅     | Logout          |
| `GET /api/v2/auth/me`             | auth      | ✅     | Current user    |
| `POST /api/v2/auth/forgot`        | auth      | ✅     | Forgot password |
| `POST /api/v2/auth/reset`         | auth      | ✅     | Reset password  |
| `POST /api/v2/auth/accept-invite` | auth      | ✅     | Accept invite   |

### Pending Investigation

- [ ] Is the JWT secret secure (not default)?
- [ ] Are refresh tokens rotated on use?
- [ ] Is MFA enforced when configured?
- [ ] Does forgot-password send actual emails?
- [ ] Are invite tokens single-use and expiring?
- [ ] Is rate limiting applied to login attempts?
