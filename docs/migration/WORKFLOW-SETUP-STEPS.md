# Autoniix Jira Workflow — Step-by-Step Setup Guide

Configure the `AE` project workflow from scratch. Every status, every transition, every setting.

**Time:** ~20 minutes. Do this once.

---

## 🔴 CURRENT STATE — What Still Needs UI Action

Everything done via API. Only 3 things left requiring browser clicks:

### A. Add 4 Missing Workflow Statuses (~3 min)

1. Open: `https://autoniix.atlassian.net/jira/software/projects/AE/boards/2`
2. Click **"..."** (top-right) → **"Board settings"**
3. Click **"Columns"** tab
4. Click **"+ Add column"** for each of these (in order):

| Column/Status Name | Category |
|---|---|
| `Ready to Deploy` | In Progress |
| `In Prod` | In Progress |
| `Prod Verified` | Done |
| `Done` | Done |

5. Save. Re-run `python3 01_setup_jira.py` to verify all 9 show green.

### B. Add Custom Fields to Issue Screens (~5 min)

1. Open: `https://autoniix.atlassian.net/jira/software/projects/AE/settings/issuetypes`
2. Click **Task** → **Fields** tab → **Add field** → add: `Environment`, `Severity`, `Layer`
3. Repeat for **Bug**, **Story**, **Sub-task**

### C. Set Up 4 Automation Rules (~5 min)

1. Open: **Project Settings → Automation** → **Create rule**
2. Create these 4 rules (one by one):

| # | Trigger | Action |
|---|---|---|
| 1 | Issue created | Assign issue to BA Agent |
| 2 | Status changed → `In Progress` | Assign issue to Dev Agent |
| 3 | Status changed → `Dev Done` | Assign issue to QA Agent |
| 4 | Status changed → `Ready to Deploy` | Assign issue to DevOps Agent |

> Agent user IDs are in JIRA-SPEC.md § Users / Agents

### D. Create 8 Components (~3 min)

1. Open: **Project Settings → Components** → **Create component**
2. Create: `Frontend`, `API Gateway`, `Backend Services`, `Database`, `Authentication`, `Background Workers`, `Infrastructure`, `Test Suite`
3. Set default assignees per JIRA-SPEC.md § 10

---

---

## Phase 1: Open the Workflow Editor

1. Open your browser to: `https://autoniix.atlassian.net/jira/software/projects/AE/settings/issuetypes`
2. You'll see a list of work types: **Epic, Story, Task, Sub-task, Bug**
3. Click on **`Task`** (any work type works — they all share the same workflow in team-managed projects)
4. In the Task settings page, look at the top tabs. Click **"Workflow"** (might also be labeled **"Statuses"** in the new UI)
5. You should see a workflow diagram. Click **"Edit workflow"** (top-right) if not already in edit mode

You're now in the workflow editor.

---

## Phase 2: Configure All 9 Statuses

For each status below, do the following:

**If the status DOESN'T exist:**
- Click **"+ Add status"** (top toolbar)
- Type the exact **Name**
- Pick the exact **Category**
- Click **Create**

**If the status DOES exist:**
- Click on the status box in the diagram
- Verify the right panel shows the correct **Name** and **Category**
- If wrong, edit and save

### Status 1: `To Do`

| Setting | Value |
|---|---|
| **Name** | `To Do` (exact, case-sensitive) |
| **Category** | **To Do** (grey/blue) |
| **Purpose** | Issue is groomed (BA done) and waiting in the backlog for a developer to pick up. |

### Status 2: `In Progress`

| Setting | Value |
|---|---|
| **Name** | `In Progress` |
| **Category** | **In Progress** (yellow) |
| **Purpose** | Developer is actively working. PR may be open. Not yet merged. |

### Status 3: `Dev Done`

| Setting | Value |
|---|---|
| **Name** | `Dev Done` |
| **Category** | **In Progress** (yellow) |
| **Purpose** | PR merged to `develop`. Code is on staging environment. Awaiting QA pickup. |

### Status 4: `In QA`

| Setting | Value |
|---|---|
| **Name** | `In QA` |
| **Category** | **In Progress** (yellow) |
| **Purpose** | QA is actively testing on the staging environment. |

### Status 5: `QA Verified`

| Setting | Value |
|---|---|
| **Name** | `QA Verified` |
| **Category** | **In Progress** (yellow) |
| **Purpose** | QA has signed off. Ready to be queued for production release. |

### Status 6: `Ready to Deploy`

| Setting | Value |
|---|---|
| **Name** | `Ready to Deploy` |
| **Category** | **In Progress** (yellow) |
| **Purpose** | Inside a release window. Awaiting actual production deploy. |

### Status 7: `In Prod`

| Setting | Value |
|---|---|
| **Name** | `In Prod` |
| **Category** | **In Progress** (yellow) |
| **Purpose** | Code has been deployed to production. Awaiting smoke-test / verification. |

### Status 8: `Prod Verified`

| Setting | Value |
|---|---|
| **Name** | `Prod Verified` |
| **Category** | **Done** (green) |
| **Purpose** | Smoke-tested in production. Behavior confirmed working. |

### Status 9: `Done`

| Setting | Value |
|---|---|
| **Name** | `Done` |
| **Category** | **Done** (green) |
| **Purpose** | Terminal state. Issue closed with a Resolution reason. Immutable. |

---

## Phase 3: Configure All 11 Transitions

For each transition: click **"+ Add Transition"** in the top toolbar.

> Tip: Jira's transition dialog has 3 fields → **From statuses** (source), **To status** (target), **Name** (label).

### Transition 1: Create (Start → To Do)

| Setting | Value |
|---|---|
| **From statuses** | (leave empty — this is the "Create" transition) |
| **To status** | `To Do` |
| **Name** | `Create` |
| **Purpose** | The initial transition when an issue is filed. Usually auto-exists. |

This one is **automatic** when you create the first status with category "To Do" — don't manually add unless missing.

### Transition 2: Start work (To Do → In Progress)

| Setting | Value |
|---|---|
| **From statuses** | `To Do` |
| **To status** | `In Progress` |
| **Name** | `Start work` |
| **Purpose** | Developer claims the ticket and starts coding. |

### Transition 3: PR Merged (In Progress → Dev Done)

| Setting | Value |
|---|---|
| **From statuses** | `In Progress` |
| **To status** | `Dev Done` |
| **Name** | `PR Merged` |
| **Purpose** | Code merged to `develop`. Auto-triggered later via GitHub automation. |

### Transition 4: Pick for QA (Dev Done → In QA)

| Setting | Value |
|---|---|
| **From statuses** | `Dev Done` |
| **To status** | `In QA` |
| **Name** | `Pick for QA` |
| **Purpose** | QA agent grabs the next item in the QA queue. |

### Transition 5: Send back to Dev (In QA → In Progress)

| Setting | Value |
|---|---|
| **From statuses** | `In QA` |
| **To status** | `In Progress` |
| **Name** | `Send back to Dev` |
| **Purpose** | QA found bugs. Comments listed. Reassigned to dev. |

### Transition 6: QA Pass (In QA → QA Verified)

| Setting | Value |
|---|---|
| **From statuses** | `In QA` |
| **To status** | `QA Verified` |
| **Name** | `QA Pass` |
| **Purpose** | QA signed off. Ready for release queue. |

### Transition 7: Mark Ready to Deploy (QA Verified → Ready to Deploy)

| Setting | Value |
|---|---|
| **From statuses** | `QA Verified` |
| **To status** | `Ready to Deploy` |
| **Name** | `Mark Ready to Deploy` |
| **Purpose** | DevOps adds to current release window. |

### Transition 8: Deploy to Prod (Ready to Deploy → In Prod)

| Setting | Value |
|---|---|
| **From statuses** | `Ready to Deploy` |
| **To status** | `In Prod` |
| **Name** | `Deploy to Prod` |
| **Purpose** | Deploy job completed successfully. Code is live. |

### Transition 9: Verify in Prod (In Prod → Prod Verified)

| Setting | Value |
|---|---|
| **From statuses** | `In Prod` |
| **To status** | `Prod Verified` |
| **Name** | `Verify in Prod` |
| **Purpose** | Smoke test passed. Feature confirmed working in production. |

### Transition 10: Close (Prod Verified → Done)

| Setting | Value |
|---|---|
| **From statuses** | `Prod Verified` |
| **To status** | `Done` |
| **Name** | `Close` |
| **Purpose** | Lead closes with Resolution = Fixed. Terminal. |

### Transition 11: Hotfix Deploy (In Progress → In Prod)

| Setting | Value |
|---|---|
| **From statuses** | `In Progress` |
| **To status** | `In Prod` |
| **Name** | `Hotfix Deploy` |
| **Purpose** | P0 production bug. Skips QA. **Lead-only.** Risk accepted. |

---

## Phase 4: Verify Diagram and Save

Before clicking save, your diagram (or Text view) should show:

```
START → To Do → In Progress → Dev Done → In QA → QA Verified → Ready to Deploy → In Prod → Prod Verified → Done
                    ↑___________ Send back to Dev ___|
                    |__________________________________ Hotfix Deploy ______________↑
```

### Checks Before Saving

- [ ] All 9 statuses are present, exact names, correct categories
- [ ] All 11 transitions are present (or 10 if Create is automatic)
- [ ] No status has the orange warning "needs a transition"
- [ ] No status has the warning "cannot be reached from start"

### Save

Click the blue **"Update workflow"** button (top-right).

Wait for confirmation. All dashed borders become solid.

---

## Phase 5: Programmatic Verification

Run from your terminal:

```bash
cd /home/saurabh/Desktop/YouTube/Autonix/scripts/migration && python3 01_setup_jira.py
```

Expected output:
```
[1/2] Ensuring issue types exist:
  - 'Story' already exists globally (id=10007)
  - 'Bug' already exists globally (id=10008)

[2/2] Probing workflow statuses:
  Current statuses in project: ['Dev Done', 'Done', 'In Progress', 'In Prod', 'In QA',
                                'Prod Verified', 'QA Verified', 'Ready to Deploy', 'To Do']

  All required statuses present.

== Phase 1 complete ==
```

If you see this output, the workflow is ready. Reply **"workflow saved"** and migration begins.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| Can't find "+ Add status" button | Click "Diagram" tab (not "Text"), then look at top toolbar |
| "Status name already exists" error | A different work type already uses this status — that's fine, click "Use existing" |
| Categories don't match | Click the status → Right panel → Category dropdown → pick correct value → Save |
| Transition won't save: "must have a name" | Type any name in the Name field; can't be empty |
| Update workflow button disabled | One status is missing a transition; check warnings on the right panel |
