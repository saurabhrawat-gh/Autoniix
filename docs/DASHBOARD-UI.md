# Dashboard UI — Feature Reference

## Quick Start

### Prerequisites
| Service        | How to start                                           |
|----------------|-------------------------------------------------------|
| PostgreSQL     | `docker compose up -d postgres-app`                   |
| Redis          | `docker compose up -d redis`                          |
| Temporal       | `docker compose up -d temporal`                       |

### 1. Start the Backend (BFF)
```bash
cd /path/to/youtube-automation
DB_HOST=localhost DB_PORT=5433 DB_PASSWORD=change_me_strong_random_64 \
  REDIS_URL=redis://localhost:6380 TEMPORAL_HOST=localhost:7233 \
  uvicorn src.services.dashboard.main:app --host 0.0.0.0 --port 8020
```
Health check: http://localhost:8020/health

### 2. Start the Frontend
```bash
cd dashboard
API_INTERNAL_URL=http://localhost:8020 npm run dev
```

### 3. Open the Dashboard
Go to **http://localhost:3000**  
Login password: `admin` (configurable in Settings)

---

## Theme & Design System

- **Palette**: Green accent (`#00d89f` dark / `#00976F` light), neutral grays, secondary purple
- **Mode**: Full light + dark theme support via CSS variables (auto-switches with system preference or manual toggle)
- **Fonts**: Inter (body), JetBrains Mono (code, IDs, monospace)
- **Layout**: Every page uses a **fixed/sticky header** with a **scrollable content area** below
- **Components**: Minimal borders, subtle shadows, toggle switches, underline-style tabs, pill badges

---

## Pages

### Login (`/login`)
Single-password authentication. The password is stored in `system_config` under `dashboard_admin_password`. Default: `admin`.

---

### Dashboard (`/dashboard`)
The main page. Fixed header contains: theme toggle, Progress link, Settings link, + Add Channel button, Logout.

#### Stats Cards (top row)
| Card             | Data                                        |
|------------------|---------------------------------------------|
| Active Channels  | Count of enabled channels / total            |
| Videos Today     | Total triggered today, delivered count, in-progress count |
| Cost Today       | Accrued cost vs daily budget limit            |
| System Status    | **Active** (green) or **Stopped** (red)       |

#### Channel List
Each channel row displays:
- **Status dot** — green (active), gray (disabled)
- **Channel name** with badges: niche, content mode tags (Short/Long), auto-upload, **Cron** (if schedule enabled)
- **Weekly usage counter** — e.g. `3/7S · 1/1L` showing videos used/limit per mode this week
- **Enable/Disable toggle** — slider switch
- **Disabled row styling** — `opacity-50` with muted background when channel is disabled
- **Smart action buttons** — contextual, based on channel state:

| Channel State    | Buttons Shown                                 |
|------------------|-----------------------------------------------|
| **Idle (single mode)** | `Trigger` (green, enabled if active + under weekly limit) |
| **Idle (both modes)**  | `▶ Short` + `▶ Long` — per-mode trigger buttons, each independently disabled at limit |
| **Idle + All Limits** | `Limit Reached` / `S Limit` / `L Limit` (grayed out, disabled) |
| **Running**      | Netflix progress ring with mode label `(S)` or `(L)` + `Pause` + `Stop` |
| **Paused**       | Paused ring (amber) with mode label + `Resume` + `Stop` |
| **Pending Review** | `Review` link → navigates to job detail     |
| **Disabled**     | All buttons grayed out and disabled            |

#### Netflix Progress Ring
When a job is running, the Trigger button is replaced by an animated circular progress ring:
- **Running**: green spinning ring
- **Paused**: amber static ring with pause icon overlay

#### One Job Per Channel
Only **one** video production workflow runs per channel at a time. Even if a channel supports both Short and Long modes, the scheduler picks one mode per run (short first due to higher frequency). This keeps Pause/Resume/Stop simple — they always target the single running workflow. The next scheduler run will pick the other mode if eligible.

#### Pause / Resume Toggle
A single button toggles between Pause and Resume. When paused, the button says "Resume" (green). When running, it says "Pause" (amber).

#### Weekly Video Limits
Each channel has per-mode weekly limits (`videos_per_week_short`, `videos_per_week_long` in the DB). The dashboard:
- Shows current usage vs limit (e.g. `3/7S`)
- Disables the Trigger button when all modes have hit their limit
- Resets weekly on Monday (tracked via `execution_locks` table)

---

### System Inactive / Emergency Stop — Full UI Lockdown

When the system is stopped (`emergency_stop = true`):

| Page             | Lockdown Behavior                                          |
|------------------|------------------------------------------------------------|
| **Dashboard**    | Red "System Inactive" banner. All channel toggles disabled. All Trigger buttons disabled. "+ Add Channel" becomes unclickable. |
| **Settings**     | Edit Mode toggle forced off + disabled (shows "locked"). Only the Resume button remains active. |
| **Add Channel**  | Red warning banner. Entire form grayed out (`opacity-60`, `pointer-events-none`). Submit says "System Stopped". |
| **Scheduler**    | `DailySchedulerWorkflow` checks `emergency_stop` flag and returns `system_inactive` — triggers 0 channels. |

**What happens to in-progress jobs**: Emergency stop sends `pause_workflow` (not `emergency_stop`) signal to all running Temporal workflows. Jobs are frozen at the next phase boundary, preserving all progress and API costs. When the system is resumed, `resume_workflow` is signaled to all paused workflows and they pick up where they left off.

**24h safety net**: If a paused workflow is not resumed within 24 hours, `_check_pause()` in `VideoProductionWorkflow` auto-cancels it via `asyncio.TimeoutError` handling.

---

### Active Jobs / Progress (`/dashboard/progress`)
Dedicated page listing **all currently in-progress + recently failed (24h) jobs** across all channels. Auto-refreshes every 5 seconds.

#### Grouped by Channel
Jobs are grouped under channel headers. Each channel group shows a link to the channel detail and a job count.

#### Header Stats
The header shows separate counts: `N in progress` and (if any) `M failed`.

#### Job Cards
Each job card shows:
- **Job title** (links to job detail) with **content mode badge** (blue for Short, purple for Long)
- **Failed badge** — red, shown for failed jobs
- **Cost so far** — accrued cost in USD
- **Error message** — for failed jobs, shown in a red monospace bar (truncated)
- **Mini stepper** — compact horizontal phase indicator:
  - Green circles for completed phases
  - Pulsing accent circle for the current phase
  - Red circle for failed phases (including overall job failure)
  - Gray circles for pending phases
  - Phase labels below each step
- **Quick controls**:
  - **Running jobs**: Pause and Stop buttons
  - **Failed jobs**: `Settings` link (→ channel settings page) + `Retry from <checkpoint>` button. The settings link lets users fix config issues (e.g., budget, duration, API keys) before retrying.

---

### Add Channel (`/dashboard/channels/new`)
Create a new YouTube channel entry with full production configuration.

| Field                  | Required | Default    | Description                               |
|------------------------|----------|------------|-------------------------------------------|
| Channel ID             | Yes      | —          | Unique identifier, e.g. `BS_SLEEP01`     |
| Channel Name           | Yes      | —          | Display name                              |
| Niche                  | Yes      | —          | Primary niche, e.g. `health`             |
| Sub-Niche              | No       | —          | Sub-category, e.g. `sleep_recovery`      |
| Content Modes          | Yes      | Short      | Select **Short Form**, **Long Form**, or **both** |
| Shorts / Week          | No       | 7          | Weekly limit for short-form videos        |
| Long Videos / Week     | No       | 1          | Weekly limit for long-form videos         |
| Short Duration (sec)   | No       | 60         | Target duration for shorts                |
| Long Duration (sec)    | No       | 600        | Target duration for long-form             |
| Max Daily Spend ($)    | No       | 5.00       | Per-channel daily API spend cap           |
| Human Review           | No       | First 10   | `first_10`, `always`, or `never`          |
| Auto-upload            | No       | Off        | Auto-upload after render                  |
| Enable Cron Schedule   | No       | On         | Automatic daily production triggering     |

**Content Modes**: You can select one or both. Stored as `short`, `long_form`, or `both`.

**Locked when system is stopped** — form is completely disabled with a warning banner.

---

### Channel Detail (`/dashboard/channels/<id>`)
**Read-only** view for a specific channel. Header includes a **⚙ Settings** link to the channel settings page.

#### Progress Summary Card
Displayed at the top, shows:
- **Current Status** — "Idle" or the active job's phase with a pulsing green dot
- **Weekly Usage** — per-mode used/limit counters (e.g. `3/7 Shorts`, `1/1 Long`). The active tab's mode counter is highlighted in accent color.
- **Automation Indicator** — "Cron Active" badge (blue) when `schedule_enabled` is true
- **Stats** — delivered, in-progress, total video counts

#### Job List
- **Tabs**: Only visible when the channel supports multiple modes (`both`). Single-mode channels show a static label instead of a tab bar. The initial tab auto-selects the channel's first supported mode.
- **Job rows**: Click any row to navigate to job detail. Shows title, content_id, date, status badge, cost, YouTube link (if uploaded).
- **Empty state**: Points user to the dashboard to trigger production

---

### Channel Settings (`/dashboard/channels/<id>/settings`)
Per-channel configuration editing page. Accessible via the ⚙ icon on the channel detail page.

#### Edit Mode
A header button toggles between read-only and edit mode. Save and Cancel buttons appear when editing.

#### Sections
| Section               | Fields                                                     |
|-----------------------|------------------------------------------------------------|
| **Basic Info**        | Channel Name, Niche, Content Mode (Short/Long/Both), Human Review |
| **Production Settings** | Shorts/Week, Long Videos/Week, Short Duration, Long Duration, Max Daily API Spend |
| **Automation**        | Auto-upload toggle, Cron Schedule toggle                   |

All changes are saved via `PUT /api/channels/{id}` which updates the DB and `schedule_config` JSONB.

---

### Job Detail (`/dashboard/jobs/<content_id>`)
Full detail view for a single video production job. Fixed header with status badge and cost.

#### Phase Stepper (always visible)
Visual overview of all production phases, color-coded:
- **Gray** = pending
- **Green (accent, pulsing)** = in progress
- **Green (solid)** = completed
- **Red** = failed

Numbered steps with phase labels. Live status bar at the bottom shows current phase, accrued cost, and pause indicator.

#### Failed Job Panel
When a job has failed, a red-bordered panel appears below the stepper with:
- **Error message** — the actual error from the workflow, displayed in monospace
- **"Channel Settings" button** — links to `/dashboard/channels/<id>/settings` so the user can fix the root cause (e.g., adjust budget, duration, fix voice ID, etc.)
- **"Retry from <checkpoint>" button** — starts a new workflow from the last successful phase

This is the intended config-fix flow: **View error → Channel Settings → Fix issue → Retry**.

#### Approve / Reject Panel
When a video reaches `delivered` status and hasn't been reviewed:
- **Yellow-bordered review card** appears with explanation text
- **"✓ Mark as Complete"** button — calls `POST /api/jobs/{id}/approve`, sets `approved_at` and `approved_by` in DB
- **"Reject & Regenerate"** button — calls `POST /api/jobs/{id}/reject`, sets status to `rejected`
- After action: confirmation banner (green for approved, red for rejected)
- Already-reviewed videos show the status badge in the header

#### Event Log Tab
Chronological list of all phase events with:
- Status icon and color
- Phase name and status badge
- Cost per event
- Event detail (topic, scores, etc.)
- Timestamp

#### Output Tab
- **Video player** — embedded HTML5 player for the rendered video
- **Download** — direct MinIO download link
- **YouTube** — link to uploaded video (if available)
- **Thumbnails** — generated variants displayed as image cards

#### Metadata Tab
- **Title, Description, Tags, Hashtags, Category** — all generated YouTube metadata
- **Click-to-copy** — click any field to copy to clipboard (shows "✓ Copied" feedback)
- **SEO Score** — displayed at the bottom

---

### Settings (`/dashboard/settings`)
System configuration management with enhanced UX.

#### Edit Mode
A **master toggle** in the header controls whether fields can be modified:
- **Off (default)**: All values displayed read-only. No "Edit" buttons visible.
- **On**: "Edit" buttons appear next to each non-boolean field. Boolean toggles become interactive.
- **Locked**: When system is stopped, the toggle is disabled and shows "(locked)".

#### Config Groups
| Group              | Keys                                          |
|--------------------|-----------------------------------------------|
| Channel Defaults   | `default_content_mode`, `per_video_budget_usd`, `max_daily_videos`, `auto_approve_threshold`, `human_review_required`, `quality_threshold` |
| Dashboard          | `dashboard_admin_password`, `dashboard_session_ttl_hours` |
| Notifications      | `telegram_bot_token`, `telegram_chat_id`, `notify_on_*` |
| Budget & Costs     | `monthly_budget_usd`, `daily_cost_limit_usd` (excluding keys already in Channel Defaults) |
| System             | Everything else (AI providers, thresholds, etc.) |

#### Smart Field Rendering
| Value Type        | Display                   | Edit Mode                              |
|-------------------|---------------------------|----------------------------------------|
| **Boolean** (`true`/`false`) | Toggle switch (green/gray) | Click to toggle immediately (no save/cancel needed) |
| **Sensitive** (password, token, secret, api_key) | Masked: `••••••••` | Text input (reveals value while editing) |
| **JSON Object** (`{...}`)    | Truncated preview (60 chars) | Multi-line textarea with JSON formatting + validation |
| **JSON Array** (`[...]`)     | Chip/pill display (up to 5 items + overflow count) | Chip editor: remove chips with ×, add with input + Enter |
| **Plain text/number**        | Code-styled display        | Inline text input                      |

#### Emergency Stop / Resume
Red button (top-right) — always accessible regardless of edit mode or system state.
- **"■ Emergency Stop"** → Sets `emergency_stop = true`, sends `pause_workflow` signal to all running Temporal workflows
- **"▶ Resume System"** → Sets `emergency_stop = false`, sends `resume_workflow` signal to all paused workflows

---

## Backend API Endpoints (BFF)

### Channels
| Method | Endpoint                              | Description                                    |
|--------|---------------------------------------|------------------------------------------------|
| GET    | `/api/channels`                       | List all channels with stats, weekly_usage, active_job |
| POST   | `/api/channels`                       | Create a new channel                           |
| PUT    | `/api/channels/{id}/enable`           | Enable a channel                               |
| PUT    | `/api/channels/{id}/disable`          | Disable a channel                              |

### Workflow Control
| Method | Endpoint                              | Description                                    |
|--------|---------------------------------------|------------------------------------------------|
| POST   | `/api/channels/{id}/trigger`          | Start a VideoProductionWorkflow                |
| POST   | `/api/channels/{id}/pause`            | Pause active workflow for channel              |
| POST   | `/api/channels/{id}/resume`           | Resume paused workflow for channel             |
| POST   | `/api/channels/{id}/stop`             | Emergency stop (kill) active workflow           |
| GET    | `/api/channels/{id}/workflow-status`  | Get live workflow state (phase, cost, paused, cancelled) |

### Channels (continued)
| Method | Endpoint                              | Description                                    |
|--------|---------------------------------------|------------------------------------------------|
| PUT    | `/api/channels/{id}`                  | Update channel config (name, niche, limits, durations, schedule, etc.) |

### Jobs
| Method | Endpoint                              | Description                                    |
|--------|---------------------------------------|------------------------------------------------|
| GET    | `/api/channels/{id}/jobs`             | List jobs for a channel (optional `content_mode` filter) |
| GET    | `/api/jobs/active`                    | List all in-progress + recently failed (24h) jobs |
| GET    | `/api/jobs/{id}/progress`             | Timeline + live status for a job               |
| GET    | `/api/jobs/{id}/output`               | Video URL, thumbnails, YouTube link            |
| GET    | `/api/jobs/{id}/metadata`             | YouTube metadata (title, description, tags)    |
| POST   | `/api/jobs/{id}/approve`              | Mark delivered video as approved               |
| POST   | `/api/jobs/{id}/reject`               | Reject video, set status to `rejected`         |
| POST   | `/api/jobs/{id}/retry`                | Retry a failed job from its last checkpoint    |

### System
| Method | Endpoint                              | Description                                    |
|--------|---------------------------------------|------------------------------------------------|
| GET    | `/api/stats`                          | Dashboard stats (channels, videos, cost, emergency_stop) |
| GET    | `/api/config`                         | List all system_config entries                 |
| PUT    | `/api/config`                         | Update a single config key                     |
| POST   | `/api/emergency-stop`                 | Freeze system + pause all running workflows    |
| POST   | `/api/emergency-resume`               | Un-freeze system + resume all paused workflows |

---

## Temporal Workflow Behavior

### VideoProductionWorkflow
- **Pause signal** (`pause_workflow`): Sets `_paused = True`. At the next `_check_pause()` call (between phases), the workflow blocks via `wait_condition`.
- **Resume signal** (`resume_workflow`): Sets `_paused = False`, unblocking `wait_condition`.
- **Emergency stop signal** (`emergency_stop`): Sets `_cancelled = True`. The workflow raises `RuntimeError` at the next checkpoint.
- **Auto-cancel**: If a workflow remains paused for 24 continuous hours, `_check_pause()` catches `asyncio.TimeoutError` and sets `_cancelled = True`, ending the workflow.

### DailySchedulerWorkflow
- Runs on a cron schedule.
- First call: `check_system_status` activity — reads `emergency_stop` from DB.
- If `emergency_stop = true`: returns `{"triggered": 0, "reason": "system_inactive"}` immediately.
- If budget exhausted: returns `{"triggered": 0, "reason": "budget_exhausted"}`.
- `get_eligible_channels` now returns **one entry per channel+mode** (e.g., a channel with `both` modes produces two entries: one for `short`, one for `long_form`).
- Channels with `schedule_config.enabled = false` are excluded.
- Per-mode weekly limits are checked: only modes under their limit are included.
- Locks are acquired per `channel_id-mode` (not just channel_id), allowing concurrent short + long jobs.
- Per-video budget uses `min(channel.max_daily_api_spend, remaining_global_budget / remaining_jobs)`.

### Session Management
- Login returns `token` + `expires_in` (seconds). Frontend stores expiry timestamp in `localStorage`.
- `isLoggedIn()` proactively checks expiry before making API calls — redirects to login if expired.
- Backend session TTL defaults to 24 hours (configurable via `dashboard_session_ttl_hours` in `system_config`).

---

## Running the Dashboard (Docker)

### Minimal Services Required

You only need **5 containers** (not the full 21-service stack) to run the dashboard:

| Service          | Port | Purpose                                        |
|------------------|------|------------------------------------------------|
| `postgres-app`   | 5433 | All application data (channels, videos, config) |
| `redis`          | 6380 | Caching, locks, pub/sub                        |
| `temporal`       | 7233 | Workflow engine (status queries, pause/resume)  |
| `dashboard-bff`  | 8020 | API backend (FastAPI)                          |
| `dashboard-ui`   | 3000 | Next.js frontend                               |

### Start (in order)

```bash
cd /path/to/youtube-automation

# 1. Infrastructure first — wait for health checks
sudo docker compose up -d postgres-app redis temporal

# 2. Verify health (postgres-app and redis should show "healthy")
sudo docker compose ps

# 3. Dashboard backend
sudo docker compose up -d dashboard-bff

# 4. Dashboard frontend
sudo docker compose up -d dashboard-ui
```

Open **http://localhost:3000** → Login with password `admin`

### Stop (graceful — keeps data)

```bash
sudo docker compose down
```

This stops all containers but **preserves volumes** (DB data, Redis, MinIO files).

### Full Reset (wipe all data)

```bash
sudo docker compose down -v
```

This removes all containers **and** volumes. The next `up` will re-run `init-db.sql` and `seed-data.sql` from scratch.

### Troubleshooting: Stuck Containers

If containers refuse to stop (AppArmor / permission denied errors):

```bash
# Restart Docker daemon first, then clean up
sudo systemctl restart docker
sudo docker compose down
```

### Environment Variables

For `dashboard-ui`:
- `NEXT_PUBLIC_API_URL` — Leave empty (uses same-origin + Next.js rewrite)
- `NEXT_PUBLIC_WS_URL` — Leave empty (auto-derived from `window.location`)
- `API_INTERNAL_URL` — Server-side rewrite target (defaults to `http://dashboard-bff:8020`)

### Running the Full Stack

To start **all 21 services** (application services, Temporal workers, Remotion renderer, etc.):

```bash
sudo docker compose up -d
```

To start only the dashboard + all backend services (no Remotion):

```bash
sudo docker compose up -d postgres-app redis temporal minio \
  research script voice assets thumbnail assembly delivery \
  analytics admin direction brand editor sheets-sync \
  worker-production worker-scheduler \
  dashboard-bff dashboard-ui
```
