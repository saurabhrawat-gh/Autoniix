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
- **Channel name** with badges: niche, content mode (Short/Long), auto-upload
- **Weekly usage counter** — e.g. `3/7S · 1/1L` showing videos used/limit per mode this week
- **Enable/Disable toggle** — slider switch
- **Smart action buttons** — contextual, based on channel state:

| Channel State    | Buttons Shown                                 |
|------------------|-----------------------------------------------|
| **Idle**         | `Trigger` (green, enabled if active + under weekly limit) |
| **Idle + Limit** | `Limit Reached` (grayed out, disabled)        |
| **Running**      | Netflix progress ring + `Pause` + `Stop`      |
| **Paused**       | Paused ring (amber) + `Resume` + `Stop`       |
| **Pending Review** | `Review` link → navigates to job detail     |
| **Disabled**     | All buttons grayed out and disabled            |

#### Netflix Progress Ring
When a job is running, the Trigger button is replaced by an animated circular progress ring:
- **Running**: green spinning ring
- **Paused**: amber static ring with pause icon overlay

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
Dedicated page listing **all currently in-progress jobs** across all channels. Auto-refreshes every 5 seconds.

Each job card shows:
- **Job title** (links to job detail), channel name, content mode, start time
- **Cost so far** — accrued cost in USD
- **Mini stepper** — compact horizontal phase indicator:
  - Green circles for completed phases
  - Pulsing accent circle for the current phase
  - Red circle for failed phases
  - Gray circles for pending phases
  - Phase labels below each step
- **Quick controls** — Pause and Stop buttons per job

---

### Add Channel (`/dashboard/channels/new`)
Create a new YouTube channel entry.

| Field          | Required | Description                               |
|----------------|----------|-------------------------------------------|
| Channel ID     | Yes      | Unique identifier, e.g. `BS_SLEEP01`     |
| Channel Name   | Yes      | Display name                              |
| Niche          | Yes      | Primary niche, e.g. `health`             |
| Sub-Niche      | No       | Sub-category, e.g. `sleep_recovery`      |
| Content Modes  | Yes      | Select **Short Form**, **Long Form**, or **both** |
| Auto-upload    | No       | If checked, videos upload to YouTube automatically after render |

**Content Modes**: You can select one or both. The value is stored as a comma-separated string (e.g. `short,long_form`). Remaining fields (weekly limits, voice, budget) use DB defaults from `system_config`.

**Locked when system is stopped** — form is completely disabled with a warning banner.

---

### Channel Detail (`/dashboard/channels/<id>`)
**Read-only** view for a specific channel. No action buttons — all workflow controls are on the main dashboard.

#### Progress Summary Card
Displayed at the top, shows:
- **Current Status** — "Idle" or the active job's phase with a pulsing green dot
- **Weekly Usage** — per-mode used/limit counters (e.g. `3/7 Shorts`, `1/1 Long`)
- **Stats** — delivered, in-progress, total video counts

#### Job List
- **Tabs**: Switch between Short Form and Long Form
- **Job rows**: Click any row to navigate to job detail. Shows title, content_id, date, status badge, cost, YouTube link (if uploaded).
- **Empty state**: Points user to the dashboard to trigger production

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

### Jobs
| Method | Endpoint                              | Description                                    |
|--------|---------------------------------------|------------------------------------------------|
| GET    | `/api/channels/{id}/jobs`             | List jobs for a channel (optional `content_mode` filter) |
| GET    | `/api/jobs/active`                    | List all in-progress jobs across all channels  |
| GET    | `/api/jobs/{id}/progress`             | Timeline + live status for a job               |
| GET    | `/api/jobs/{id}/output`               | Video URL, thumbnails, YouTube link            |
| GET    | `/api/jobs/{id}/metadata`             | YouTube metadata (title, description, tags)    |
| POST   | `/api/jobs/{id}/approve`              | Mark delivered video as approved               |
| POST   | `/api/jobs/{id}/reject`               | Reject video, set status to `rejected`         |

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
- Otherwise: iterates eligible channels, acquires locks, starts child `VideoProductionWorkflow` instances.

---

## Docker Deployment

For production, use Docker Compose:

```bash
docker compose up -d dashboard-bff dashboard-ui
```

- **BFF**: Port 8020, auto-connects to internal Docker network
- **UI**: Port 3000, proxies API calls to BFF via Next.js rewrites

Environment variables for `dashboard-ui`:
- `NEXT_PUBLIC_API_URL` — Leave empty (uses same-origin + rewrite)
- `NEXT_PUBLIC_WS_URL` — Leave empty (auto-derived from window.location)
- `API_INTERNAL_URL` — Server-side rewrite target (defaults to `http://dashboard-bff:8020`)
