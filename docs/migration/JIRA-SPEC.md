# Autoniix Jira Workflow Spec

Living document — captures all BA decisions for the Autoniix Jira project (`AE`). Built one decision at a time via `/ba-agent` sessions.

**Status:** � Complete — all decisions locked

---

## 1. Project Identity

| Field | Value |
|---|---|
| Workspace | `https://autoniix.atlassian.net` |
| Cloud ID | `73672c49-7089-4f35-adde-e3fa0d1e438f` |
| Jira project key | `AE` |
| Confluence space key | `AE` |
| Project type | **Team-managed Kanban** (current — open to change) |
| Title format — Epic | `Autoniix \| Epic \| <Domain>` |
| Title format — Story | `Autoniix \| Story \| <Layer> \| <Description>` |
| Title format — Task | `Autoniix \| <Layer> \| <Description>` |
| Title format — Bug | `Autoniix \| <Layer> \| <QA\|Prod> \| <Description>` |

### Users / Agents

| Display Name | Email | accountId | Role |
|---|---|---|---|
| Saurabh Rawat | `admin@autoniix.com` | `712020:47a3741d-b21c-4faa-9ad7-73b9c44f1451` | **Lead** — final say, hotfix authority |
| BA Agent | `admin+ba-agent@autoniix.com` | `712020:35d567c0-f80a-4413-8b24-080462c36c72` | Issue creation, requirements gathering |
| Dev Agent | `admin+dev-agent@autoniix.com` | `712020:863fd585-7c67-4cac-86c6-8885e80502b3` | Implementation, PR work |
| QA Agent | `admin+qa-agent@autoniix.com` | `712020:2575a2a0-33aa-422e-b26e-a99456cf0359` | Testing, QA verification |
| DevOps Agent | `admin+devops-agent@autoniix.com` | `712020:6a18d77f-86a4-47d3-86da-48af39dac4a8` | Deploy orchestration |

---

## 2. Issue Types & Hierarchy

```
Epic                 (container — domain-level)
 └─ Story            (container — feature-level capability)
     └─ Task         (work item — full lifecycle)
         └─ Sub-task (work item — full lifecycle, smaller unit)
     └─ Bug          (work item — defect, full lifecycle, can hotfix)
```

| Type | Role |
|---|---|
| **Epic** | Container for a major product domain |
| **Story** | Container for a vertical-slice user-facing capability |
| **Task** | The actual unit of dev work, the QA/deploy lifecycle applies here |
| **Sub-task** | Decomposition of a Task — full lifecycle, smaller unit |
| **Bug** | Defect — full lifecycle, with hotfix shortcut |

---

## 3. Workflows (per Issue Type)

### 3.1 Epic & Story — Container Lifecycle

```
To Do  →  In Progress  →  Done
```

- Status reflects rollup of children
- Manually transitioned by lead (automation later in Phase 2)
- Reaches **Done** only when all children Done

### 3.2 Task / Sub-task / Bug — Full Lifecycle

```
To Do                       (groomed, awaiting dev)
   ↓
In Progress                 (dev actively working)
   ↓
Dev Done                    (PR merged to develop, awaiting QA)
   ↓
In QA                       (QA actively testing on staging)
   ↓
QA Verified                 (QA signed off — ready for prod queue)
   ↓
Ready to Deploy             (in release window, deploy pending)
   ↓
In Prod                     (deployed, awaiting prod verification)
   ↓
Prod Verified               (verified working in prod)
   ↓
Done                        (closed)
```

**Send-back from QA** *(decision Q4)*:
- QA finds issues during `In QA` testing
- QA adds a comment listing what's broken
- QA changes assignee back to the developer
- QA transitions issue back to **`In Progress`**

### 3.3 Bug — Hotfix Sub-flow

For P0 production bugs that can't wait for normal QA:

```
In Progress  →  In Prod  →  Prod Verified  →  Done
```

- Skips Dev Done, In QA, QA Verified, Ready to Deploy
- Triggered by **"Hotfix Deploy"** transition (label `hotfix` required)
- Accept the risk: no QA gate
- Optional: backfill with a regression test as a follow-up Task

---

## 4. Resolution Field (single terminal state)

All issues end at `Done`. The **Resolution** field captures *why* it ended:

| Resolution | Meaning |
|---|---|
| `Fixed` | Default — work completed normally |
| `Won't Do` | Decided not to do |
| `Duplicate` | Same as another issue (link to original) |
| `Out of Scope` | Decided to defer or remove from MVP |
| `Cannot Reproduce` | Bug couldn't be reproduced (Bug-only) |
| `Hotfix` | Closed via hotfix sub-flow (Bug-only) |

A required dialog should prompt for Resolution when transitioning to `Done`.

---

## 5. Reopen Rules — NEVER REOPEN

**Rule:** Once an issue reaches `Done` (with any Resolution), it is **immutable**. No reopen transition exists in the workflow. Any further work creates a **new linked issue**.

### Why
- Preserves accurate cycle time, velocity, and sprint reports
- Eliminates "zombie" tickets that span months/years
- Clean audit trail — each ticket has one scope, one set of ACs, one outcome
- Removes whole class of permission disputes ("who can reopen?")

### Replacement Patterns

| Original scenario | Action |
|---|---|
| Bug fixed → `Done` → reappears in prod | Create **new Bug**, link `Regression of` → original |
| Story `Done` → user wants extension/enhancement | Create **new Story**, link `Related to` → original |
| Story `Done` with `Won't Do` → team changes mind | Create **new Story**, link `Replaces` → original |
| Two issues turn out to be same | Close the duplicate with Resolution `Duplicate`, link `Duplicate of` → kept one |
| Discovered work was incomplete | Create **new Task**, link `Related to` → original; comment on original explaining |

### Link Types Used

| Type | Built-in to Jira? |
|---|---|
| `Blocks` / `Blocked by` | Yes |
| `Duplicate of` / `Duplicates` | Yes |
| `Relates to` | Yes |
| `Regression of` (caused by → causes) | Yes — use Jira's `Caused by` link |
| `Replaces` | Yes |

---

## 6. Transitions Matrix

### 9-State Workflow — Hybrid Transitions

**Phase 1 (current — fastest path):** Pre-deploy chain uses Jira's auto-generated **global "Any Status → X"** transitions. Deploy chain uses **explicit directional** transitions.

| # | From | To | Transition Name | Type | Notes |
|---|---|---|---|---|---|
| 1 | (Start) | `To Do` | Create | Auto | Issue creation lands here |
| 2 | Any | `To Do` | Move to Backlog | Global | Send anything back to backlog |
| 3 | Any | `In Progress` | Start work | Global | Dev claims work |
| 4 | Any | `Dev Done` | PR Merged | Global | After PR merge to develop |
| 5 | Any | `In QA` | Pick for QA | Global | QA grabs from queue (also: send-back uses this) |
| 6 | Any | `QA Verified` | QA Pass | Global | QA signs off |
| 7 | `QA Verified` | `Ready to Deploy` | Mark Ready to Deploy | Explicit | In release window |
| 8 | `Ready to Deploy` | `In Prod` | Deploy to Prod | Explicit | Deployed successfully |
| 9 | `In Prod` | `Prod Verified` | Verify in Prod | Explicit | Smoke test passed (currently named "Close" — needs rename) |
| 10 | `Prod Verified` | `Done` | Close | Explicit | Final closure with Resolution |

**Send-back from QA** is implemented by transitioning `In QA → In Progress` via the global "Any Status → In Progress" transition. QA agent must also add a comment + reassign per spec.

**Hotfix transition** (`In Progress → In Prod`) is deferred to Phase 2 — current workflow doesn't have it. For now, hotfix uses normal deploy chain.

**Phase 2 (post-migration improvement):** Migrate global transitions to explicit directional ones; add hotfix shortcut; add validators for required Resolution on Done.

### 3-State Convention (Epic, Story)

Epic and Story use the same workflow but conventionally only transition through:

| # | From | To | Transition Name |
|---|---|---|---|
| 1 | (Start) | `To Do` | Create |
| 2 | `To Do` | `In Progress` | Activated (≥1 child In Progress) |
| 3 | `In Progress` | `Done` | All children Done |

*Rationale:* keeps the project to ONE workflow (simpler) while convention restricts Epic/Story usage. Can split into 2 workflows later if needed.

---

## 7. Permissions / Who Can Do What

### Creation
- **Default path:** BA agent creates issues from owner conversations
- **Bypass:** Lead (you) can create directly when needed
- **No one else** creates issues — keeps quality high

### Transitions (see matrix above)
- Each transition has 1–2 allowed actors
- Hotfix (`In Progress → In Prod`) is **Lead only** — you accept the risk
- All agents are restricted via Jira's permission scheme (configured in Phase 2)

### Field Editing
- **Open issues:** all fields editable by assignee + Lead
- **Done issues:** **locked** except labels and links (preserves immutability)

### Resolution (mandatory on Done)
- Transition to `Done` triggers a required Resolution picker
- Values: `Fixed` (default), `Won't Do`, `Duplicate`, `Out of Scope`, `Cannot Reproduce` (Bug), `Hotfix` (Bug)

### Assignment
- **On creation:** smart-route by label → component owner; fallback to unassigned
- **On transition:** auto-reassign per matrix (e.g. `In QA` → assign QA agent)

---

## 8. Automation Rules

> Jira Cloud Free: **100 rule runs/month** — rules designed to be low-frequency.

### 8.1 Auto-Assignment on Transition

| Trigger | Action | Actor |
|---|---|---|
| Issue created | Assign to **BA Agent** | System |
| Transition → `In Progress` | Assign to **Dev Agent** | System |
| Transition → `Dev Done` | Assign to **QA Agent** | System |
| Transition → `Ready to Deploy` | Assign to **DevOps Agent** | System |
| Transition → `Done` | Assign to **Lead** | System |

### 8.2 Label-Based Routing (GitHub → Jira bridge, Phase 2)

GitHub Actions webhook fires on label changes → updates Jira issue status via REST API.

| GitHub Label | Jira Transition |
|---|---|
| `ready-for-dev` added | → `To Do` |
| `in-progress` added | → `In Progress` |
| `in-qa` added | → `Dev Done` then `In QA` |
| `qa-verified` added | → `QA Verified` |
| `ready-to-deploy` added | → `Ready to Deploy` |
| `in-prod` added | → `In Prod` |
| `prod-verified` added | → `Prod Verified` then `Done` |

### 8.3 Phase 1 Rules (Configure Now — Manual Jira Automation UI)

Priority rules to set up in **Project Settings → Automation**:

1. **Auto-assign on creation**: Trigger=Issue Created → Action=Assign to BA Agent (`712020:35d567c0-f80a-4413-8b24-080462c36c72`)
2. **Auto-assign Dev**: Trigger=Status Changed to `In Progress` → Action=Assign to Dev Agent (`712020:863fd585-7c67-4cac-86c6-8885e80502b3`)
3. **Auto-assign QA**: Trigger=Status Changed to `Dev Done` → Action=Assign to QA Agent (`712020:2575a2a0-33aa-422e-b26e-a99456cf0359`)
4. **Auto-assign DevOps**: Trigger=Status Changed to `Ready to Deploy` → Action=Assign to DevOps Agent (`712020:6a18d77f-86a4-47d3-86da-48af39dac4a8`)

---

## 9. Custom Fields

| Field | Jira Field ID | Type | Options | Applied To |
|---|---|---|---|---|
| **Environment** | `customfield_10073` | Select | `local`, `dev`, `staging`, `prod` | Bug, Task |
| **Severity** | `customfield_10074` | Select | `P0-Critical`, `P1-High`, `P2-Medium`, `P3-Low` | Bug, Task |
| **Layer** | `customfield_10075` | Select | `UI`, `Gateway`, `Service`, `DB`, `Auth`, `Worker`, `Infra`, `Test` | All work items |
| **Resolution** | `resolution` (built-in) | Select | `Fixed`, `Won't Do`, `Duplicate`, `Out of Scope`, `Cannot Reproduce`, `Hotfix` | All |

### Usage Rules

- **Layer** — mandatory on all Tasks and Bugs (BA Agent sets this on creation)
- **Severity** — mandatory on Bugs (set by QA Agent on `In QA` entry or BA Agent on creation)
- **Environment** — optional on Tasks; mandatory on Bugs (`dev`=found in dev, `staging`=found in QA, `prod`=production bug)
- **Resolution** — mandatory when transitioning to `Done`

### Adding Fields to Issue Screens

Go to: `https://autoniix.atlassian.net/jira/software/projects/AE/settings/issuetypes`
Click each issue type → **Fields** tab → **Add field** → pick `Environment`, `Severity`, `Layer`

---

## 10. Components

Components are used for issue routing and filtering. Each maps to a `Layer` value.

| Component | Maps to Layer | Default Assignee |
|---|---|---|
| Frontend | UI | Dev Agent |
| API Gateway | Gateway | Dev Agent |
| Backend Services | Service | Dev Agent |
| Database | DB | Dev Agent |
| Authentication | Auth | Dev Agent |
| Background Workers | Worker | Dev Agent |
| Infrastructure | Infra | DevOps Agent |
| Test Suite | Test | QA Agent |

> Create these in **Project Settings → Components**. Use the default assignee to pre-route issues on creation.

---

## Open Decisions Queue

- [x] Q1: Per-type workflow (all work items full 9-state)
- [x] Q2: Epic/Story container lifecycle (3-state)
- [x] Q3: Hotfix path (sub-flow)
- [x] Q4: Send-back from QA (back to In Progress)
- [x] Q5: Resolution field for cancellation reasons
- [x] Q6-Q11: Reopen rules — locked: never reopen, always create new linked issue
- [x] Q12-Q16: Permissions + creation + assignment + field editing + resolution
- [x] Automation rules — see Section 8
- [x] Custom fields — Environment, Severity, Layer created via API (see Section 9)
- [x] Sprints vs continuous — **Decision: Kanban (continuous)**. No sprint ceremonies. Backlog is the queue. Suits solo dev + AI agent setup.
- [x] Release/Fix Version strategy — **Decision: use Jira Fix Versions** (available on Free). Create a new version per release (e.g. `v0.1.0`). Close version when all linked issues are Done.

---

## 11. Migration Status

| Step | Status | Notes |
|---|---|---|
| Issue types (Epic, Story, Task, Bug, Subtask) | ✅ Done | All exist in project AE |
| Workflow statuses (5/9) | ⚠️ Partial | `To Do`, `In Progress`, `Dev Done`, `In QA`, `QA Verified` done |
| Workflow statuses (4 missing) | 🔴 UI Required | `Ready to Deploy`, `In Prod`, `Prod Verified`, `Done` — add via board settings |
| QA Verified category fix | ✅ Done | Changed from Done → In Progress via API |
| Custom fields | ✅ Done | Environment, Severity, Layer created via API |
| Add fields to issue screens | 🔴 UI Required | Project Settings → Issue types → Fields → Add field |
| Automation rules (Phase 1) | 🔴 UI Required | Project Settings → Automation (4 rules) |
| Components | 🔴 UI Required | Project Settings → Components (8 components) |
| Seed issues / migration data | ⏳ Pending | Run after all statuses present |
