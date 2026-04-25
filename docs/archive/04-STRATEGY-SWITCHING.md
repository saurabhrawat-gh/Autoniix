# Strategy Switching & System Controls

---

## Strategy Switching Feasibility

### Switch Matrix

| From → To | Feasibility | What Changes | Effort | Downtime |
|-----------|------------|-------------|--------|----------|
| A → B | ✅ Easy | Reduce long-form, increase Shorts | 30 min | 0 |
| A → C | ✅ Easy | Add daily Shorts scheduling | 30 min | 0 |
| B → A | ✅ Easy | Increase long-form, reduce Shorts | 30 min | 0 |
| B → C | ✅ Easy | Gradually increase long-form | 30 min | 0 |
| C → A | ✅ Easy | Fix at 1L+2S/week | 30 min | 0 |
| C → B | ✅ Easy | Reduce long-form, increase Shorts | 30 min | 0 |

**All switches are trivial** because strategy differences are ONLY in Workflow A scheduling:

```
Channel_DNA controls strategy:
  videos_per_week_long = 0.25 (B) or 1 (A) or 2 (C steady)
  videos_per_week_short = 2 (A) or 7 (B) or 3 (C steady)

To switch: change 2 cells in Channel_DNA.
Next execution cycle uses new values automatically.
```

### Per-Channel Strategy Mixing

Different strategies can run on different channels simultaneously:

```
BS001 (Health):     Strategy C (2L+3S/week) — best performer
FIN001 (Finance):   Strategy B (1L/month+7S/week) — new channel
CRIME001 (Crime):   Strategy A (1L+2S/week) — balanced
```

Workflow A reads each channel's values independently.

---

## System Controls: Start / Stop / Pause / Emergency

### Control Levels

#### Level 1: Per-Channel Control
```
Channel_DNA.status:
  "active"   → scheduled normally
  "paused"   → skipped (existing work finishes)
  "disabled" → fully ignored

HOW: Edit 1 cell in Google Sheets.
```

#### Level 2: Multi-Channel Batch Control
```
To pause 10 channels: set status="paused" for 10 rows
To pause a niche: filter by niche, set all to "paused"

Or via Admin API:
  POST /admin/pause { "scope": "niche", "target": "health" }
```

#### Level 3: System-Wide Pause
```
System_Config.system_status = "paused"

Every workflow checks at entry → STOP if not "active"
In-progress workflows finish current section, then stop at checkpoint.

HOW: Edit 1 cell. Or POST /admin/pause { "scope": "system" }
```

#### Level 4: Emergency Stop
```
System_Config.emergency_stop = "true"

Every workflow checks at EVERY checkpoint (not just entry).
If true → save state → STOP immediately → notify admin.

HOW: Edit 1 cell. Or POST /admin/emergency-stop
```

#### Level 5: n8n Hard Stop
```
Disable all workflows in n8n UI. Nothing runs.
n8n API: PUT /workflows/{id} { "active": false }
```

### Control Flow in Every Workflow

```
Entry:
  ├─ emergency_stop? → YES → STOP immediately
  ├─ system_status? → "paused" → STOP gracefully
  ├─ daily_budget exceeded? → YES → STOP + notify
  └─ PROCEED

Between major sections (checkpoints):
  ├─ emergency_stop? → YES → Save state + STOP
  ├─ channel.status? → "paused" → Save state + STOP
  └─ CONTINUE
```

### Checkpoint Resume System

When paused, state is saved to Output_Log:
```json
{
  "content_id": "VID_BS001_20250417_001",
  "status": "paused_at_checkpoint",
  "checkpoint": "B1_script_v1_complete",
  "checkpoint_data_url": "https://drive.google.com/.../data.json",
  "paused_at": "2025-04-17T10:30:00Z",
  "resume_from": "B1_hook_engine"
}
```

On resume:
1. Set system back to "active"
2. Workflow A detects paused content_ids
3. Triggers appropriate workflow at checkpoint
4. No re-running completed sections (saves money)

### Admin API Endpoints

```
GET  /admin/status         → health, active channels, running workflows, budget
POST /admin/pause          → { "scope": "system|channel|niche", "target": "..." }
POST /admin/resume         → resume system/channel, trigger checkpoint resumes
POST /admin/emergency-stop → immediate halt
POST /admin/budget         → { "daily_limit": 75 }
POST /admin/strategy       → { "channel_id": "BS001", "videos_per_week_long": 2, ... }
```
