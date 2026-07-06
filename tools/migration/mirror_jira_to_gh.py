#!/usr/bin/env python3
"""Mirror BA-session-2026-05-30 Jira tickets to GitHub Issues.

Phase A: epic + 3 bugs + 8 stories (12 issues)
Phase B: 26 sub-tasks
Phase C: update scripts/migration/state/issue_map.json
Phase D: bump labels on existing GH #216 (AE-208) and #217 (AE-209)

Run from repo root. Requires authed `gh` CLI.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = "saurabhrawat-gh/Autoniix"
MAP_PATH = Path("scripts/migration/state/issue_map.json")
JIRA_BASE = "https://autoniix.atlassian.net/browse"


def jira_link(key: str) -> str:
    return f"[{key}]({JIRA_BASE}/{key})"


def gh_create(title: str, body: str, labels: list[str]) -> int:
    cmd = ["gh", "issue", "create", "--repo", REPO, "--title", title, "--body-file", "-"]
    for lbl in labels:
        cmd += ["--label", lbl]
    res = subprocess.run(cmd, input=body, text=True, capture_output=True, check=False)
    if res.returncode != 0:
        print(f"ERROR creating {title!r}:\n{res.stderr}", file=sys.stderr)
        sys.exit(1)
    url = res.stdout.strip().splitlines()[-1]
    m = re.search(r"/issues/(\d+)", url)
    if not m:
        print(f"ERROR: cannot parse GH issue number from {url!r}", file=sys.stderr)
        sys.exit(1)
    num = int(m.group(1))
    print(f"  → #{num}  {title}")
    return num


def gh_add_labels(issue: int, labels: list[str]) -> None:
    cmd = ["gh", "issue", "edit", str(issue), "--repo", REPO]
    for lbl in labels:
        cmd += ["--add-label", lbl]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"  → #{issue} labels +{labels}")


def gh_remove_labels(issue: int, labels: list[str]) -> None:
    cmd = ["gh", "issue", "edit", str(issue), "--repo", REPO]
    for lbl in labels:
        cmd += ["--remove-label", lbl]
    subprocess.run(cmd, check=False, capture_output=True)


# ── PHASE A: epic + 3 bugs + 8 stories ─────────────────────────────────────

PHASE_A: list[tuple[str, str, str, list[str]]] = [
    (
        "AE-226",
        "[Epic] Pipeline Review & Approval Gates — Per-Stage Human-in-the-Loop Review System",
        """> Mirror of {link}. Full spec lives on Jira.

## What This Epic Is About

Autoniix's video production pipeline (`VideoProductionWorkflow`) produces 13 distinct artifacts across 10 phases. Today the pipeline runs end-to-end without human checkpoints by default — fine for power users, unsafe for new creators, unsuitable for multi-member workspaces.

This epic introduces a **configurable, per-artifact approval gate system** that lets a workspace owner decide — per channel — which artifacts require human approval before the pipeline proceeds.

## The 13 Reviewable Artifacts

| # | Phase | Artifact |
|---|---|---|
| 1 | researching | research_data |
| 2 | brand_check | brand_alignment_report |
| 3 | scripting | topic / title candidates |
| 4 | scripting | story_script |
| 5 | scripting | script_voice_data |
| 6 | scripting | script_assets_data |
| 7 | scripting | script_direction_data |
| 8 | generating_voice | voice_track |
| 9 | generating_assets | scene_images / b-roll |
| 10 | directing | remotion_v3_json |
| 11 | post_production | metadata |
| 12 | post_production | thumbnail |
| 13 | rendering | final_video |

## Locked Decisions

### Review profile presets (channel-level)
- **Hands-off** — no gates; pipeline runs straight through (current behaviour).
- **Quick** — gates on `story_script` + `final_video` only.
- **Standard** (default for new channels) — `topic/title`, `story_script`, `metadata`, `thumbnail`, `final_video`.
- **Full Control** — all 13 gates ON.
- **Custom** — toggle each gate individually.

### Mechanics
- Gate config stored as `channels.review_config JSONB`.
- Each gate uses Temporal signal/wait (`workflow.wait_condition` on `approval_<artifact>` signal).
- Unified inbox at `/dashboard/review`.
- Owner/Member can approve; Viewer cannot.
- Decision = approve / edit / reject. Reject re-runs producing phase (max 3 retries).
- Out of scope v1: per-artifact assignees, SLAs, multi-approver quorum, push notifications.

## Child Stories
- Review-Infra-1 — `channels.review_config` + API
- Review-Infra-2 — Temporal `await_approval()` utility
- Review-Infra-3 — `approvals` table + unified inbox API
- Review-UI-1 — Channel settings profile picker
- Review-UI-2 — Unified inbox page
- Review-UI-3 — Per-artifact viewer/editor
- _Review-Gate-1..13 — to be created per artifact once infra lands_

## How to Know This Epic Is Done

- [ ] Any of the 13 artifacts can be gated independently per channel via UI
- [ ] Pipeline correctly pauses, presents the artifact, accepts approve/reject/edit, and resumes
- [ ] All gate decisions are auditable per workspace, per channel, per video
- [ ] Default profile for newly-created channels is **Standard** (5 gates)
- [ ] Existing channels migrated to **Hands-off** (no behaviour change for in-flight videos)
""",
        ["epic", "type:epic", "priority:high", "ready-for-dev"],
    ),
    (
        "AE-223",
        '[Bug] Prod | UI | Provider scope dropdown shows cryptic "Set up per-channel override" CTA when workspace has zero channels',
        """> Mirror of {link}.

**Bug Type:** Production (UX nit — not blocking) · **Parent Story:** #24 (AE-26) · **Layer:** UI

## Description

On `/dashboard/providers/[category]` the scope context-switcher dropdown shows only "Workspace (default)" plus a CTA labelled "Set up per-channel override" when the workspace has no channels. The CTA is actually a `<Link>` to `/dashboard/channels/new` — it creates a channel, it does not "set up an override". Label is misleading.

## Expected
Empty-state CTA should clearly indicate it creates a channel, e.g. `+ Create a channel` with sub-text "to scope credentials per-channel".

## Actual
CTA reads "Set up per-channel override" with a `+` icon and routes to `/dashboard/channels/new`.

## Environment
- Branch: `main` (production) · URL: `https://dash.autoniix.com/dashboard/providers/llm`
- File: `dashboard/src/app/dashboard/providers/[category]/page.tsx` lines 425–435

## Acceptance Criteria
- [ ] Empty-state CTA label rewritten to clearly indicate channel creation
- [ ] Optionally add a one-line helper text under the CTA
- [ ] No regression on AE-26 6-layer resolver behaviour
- [ ] Verified on `https://dash.autoniix.com` after deploy
""",
        ["bug", "bug:production", "type:bug", "priority:high", "ready-for-dev", "providers"],
    ),
    (
        "AE-224",
        "[Bug] Prod | UI | Feature Flags page (/dashboard/settings/flags) is unreachable from any navigation",
        """> Mirror of {link}.

**Bug Type:** Production (UX) · **Parent Story:** #25 (AE-27) · **Layer:** UI

## Description

The route `/dashboard/settings/flags` exists and is fully functional, but there is no navigation link, button, or tab from anywhere in the dashboard UI that points to it. Users must know the URL and type it manually. `grep` of the entire codebase for `/settings/flags` returns zero matches.

## Expected
Either:
- Add a "Feature Flags" tab/section to the main Settings page (Owner-gated), OR
- Add a sidebar sub-item under Settings, OR
- Add a card on the Settings landing page linking to `/dashboard/settings/flags`

## Acceptance Criteria
- [ ] Settings page has a visible Owner-gated entry point to `/dashboard/settings/flags`
- [ ] Entry point labelled "Feature Flags" with a brief subtitle
- [ ] No regression on `/dashboard/settings` or `/dashboard/settings/flags` themselves
- [ ] Verified on `https://dash.autoniix.com` after deploy
""",
        ["bug", "bug:production", "type:bug", "priority:high", "ready-for-dev"],
    ),
    (
        "AE-225",
        '[Bug] Prod | UI | Members section shows no plan-limit indicator (no "X/Y members" or plan name)',
        """> Mirror of {link}.

**Bug Type:** Production (UX) · **Parent Story:** AE-23 (plan limits — deferred) · **Layer:** UI

## Description

Workspace → Members section displays a member count badge (e.g. "Members 2") but provides no visibility into the plan's seat limit. Users have no idea how many seats they have, what plan they're on, or how close they are to the cap until they hit a 402. Backend defines: starter = 3, growth = 10, scale = unlimited. UI surfaces none.

## Expected
Members header (or sidebar / page header) shows:
- The plan name (e.g. "Growth plan")
- Current usage vs limit (e.g. "4/10 seats used (2 members + 2 pending)")
- An "Upgrade" CTA when usage is at/near limit

## Acceptance Criteria
- [ ] Members section shows plan name + seat usage (e.g. "Growth — 4/10 seats")
- [ ] Counts include pending invites in the "used" tally to match backend
- [ ] Upgrade CTA appears when usage ≥ 80% of limit
- [ ] No regression on AE-23 backend gate

**Note:** AE-23 (plan-limits enforcement) is currently `deferred` pending Billing epic. This UI surface is informational and can ship independently.
""",
        ["bug", "bug:production", "type:bug", "priority:high", "ready-for-dev", "workspace"],
    ),
    (
        "AE-227",
        "[Story] Role Preset Consolidation — Collapse 5 UI roles to 3 (Owner / Member / Viewer)",
        """> Mirror of {link}. Parent epic: #13 (AE-7).

## User Story
As a workspace owner, I want a simple 3-choice role picker (Owner / Member / Viewer) so I don't have to puzzle over Admin / Producer / Editor / Reviewer.

## Why
Shipped 5-role model (AE-22) created UX confusion in production QA. Industry standard at our stage is **3 roles max** (Notion, Linear, Figma free tier, GitHub free tier). The 32-permission matrix (AE-78) stays as the internal engine — this story only consolidates the **visible presets**.

## Locked Decisions
- **Owner**: exactly one per workspace. Full permissions. Owns billing.
- **Member**: full content/pipeline permissions but no people-management, no billing.
- **Viewer**: read-only.
- Existing rows migrated: `admin → member`, `producer → member`, `editor → member`, `reviewer → viewer`.
- No custom roles UI in v1.

## Acceptance Criteria
- [ ] No UI surface offers Admin / Producer / Editor / Reviewer
- [ ] DB CHECK constraint enforces `role IN ('owner','member','viewer')`
- [ ] All existing rows migrated without data loss
- [ ] `GET /auth/me` returns correct resolved permissions for each preset
- [ ] `prod-verified` walk-through: invite, change role, remove — all 3 roles
- [ ] No regression on workspace switcher, invite emails, ownership transfer

## Sub-tasks
See child issues for BE migration, BE API/preset mapping, FE pickers.
""",
        ["story", "type:story", "priority:high", "ready-for-dev", "workspace"],
    ),
    (
        "AE-228",
        "[Story] Platform-Agnostic Channel Abstraction — Add `platform` discriminator (YouTube shipped, others stubbed)",
        """> Mirror of {link}. Parent epic: #13 (AE-7).

## User Story
As a product owner, I want `channel` to be platform-agnostic from day one so we can add Instagram, TikTok, X, LinkedIn without a schema migration later.

## Locked Decisions
- New column `channels.platform TEXT NOT NULL DEFAULT 'youtube'` with CHECK constraint `platform IN ('youtube','instagram','tiktok','twitter','linkedin')`.
- Existing rows backfilled to `youtube`.
- APIs accept `platform` (default `youtube`); non-youtube values return `501 Not Implemented` with clear message.
- UI shows platform icon/label; create-channel form lists all options but non-YouTube **disabled with "Coming soon" tooltip**.

## Acceptance Criteria
- [ ] `channels.platform` column exists with default + CHECK
- [ ] All existing channels backfilled to `youtube`
- [ ] APIs accept + return `platform`
- [ ] FE renders platform icon/label
- [ ] Create-channel UI shows disabled "Coming soon" tooltips for non-YouTube
- [ ] Non-youtube POST returns 501 with clear message
- [ ] No regression on YouTube channel creation, OAuth, upload, analytics
""",
        ["story", "type:story", "priority:high", "ready-for-dev", "providers"],
    ),
    (
        "AE-229",
        "[Story] Review-Infra-1 — `channels.review_config` JSONB column + API CRUD",
        """> Mirror of {link}. Parent epic: AE-226 (will be linked once mirror lands).

## User Story
As the pipeline, I need to know which artifacts to gate for human review on a per-channel basis.

## Scope
- Migration: `channels.review_config JSONB NOT NULL DEFAULT '{{"profile":"hands_off","gates":{{}}}}'`
- New channels via UI default to `standard` profile (5 gates); existing channels = `hands_off`.
- API endpoints:
  - `GET /channels/{{id}}/review-config`
  - `PATCH /channels/{{id}}/review-config` — accepts `profile` (auto-fills gates) or explicit `gates` (forces `custom`).
- Owner/Member can modify; Viewer read-only.

## Acceptance Criteria
- [ ] Migration applied, default in place, existing rows backfilled to `hands_off`
- [ ] API endpoints return correct config
- [ ] `profile=standard` auto-fills the 5 standard gates
- [ ] Explicit `gates` flips `profile` to `custom`
- [ ] Schema validation rejects unknown gate keys
- [ ] Unit + API tests green
""",
        ["story", "type:story", "priority:high", "ready-for-dev"],
    ),
    (
        "AE-230",
        "[Story] Review-Infra-2 — Temporal `await_approval(artifact_key)` workflow utility",
        """> Mirror of {link}. Parent epic: AE-226.

## Scope
- New module `src/temporal_workflows/review_gate.py`.
- `await_approval(channel_id, video_id, artifact_key, artifact_payload) -> ApprovalResult`:
  1. Reads `channels.review_config` (via activity).
  2. Gate OFF → returns `Approved(payload)` immediately.
  3. Gate ON → inserts pending row in `approvals`, then `workflow.wait_condition`.
  4. On signal: dispatches `approve` / `edit` / `reject`.
- Signal handler `submit_approval(artifact_key, decision, edited_payload?, comment)`.
- Default timeout 30 days (workflow heartbeat).

## Acceptance Criteria
- [ ] Gate OFF path adds < 5 ms overhead per artifact
- [ ] Gate ON path correctly pauses workflow until signal
- [ ] Approve / Edit / Reject all dispatch correctly
- [ ] Unit tests using Temporal time-skipping framework
- [ ] Integration test with at least one phase wired to the utility
""",
        ["story", "type:story", "priority:high", "ready-for-dev"],
    ),
    (
        "AE-231",
        "[Story] Review-Infra-3 — `approvals` table + pending-approvals unified inbox API",
        """> Mirror of {link}. Parent epic: AE-226.

## Scope
- `approvals` table: `(id, workspace_id, channel_id, video_id, artifact_key, status, requested_at, decided_at, decided_by, decision, comment, original_payload_jsonb, edited_payload_jsonb, workflow_id, signal_name)`. Indexes `(workspace_id, status)` and `(workflow_id)`.
- API:
  - `GET /approvals?status=pending&workspace_id=...` paginated + filters.
  - `GET /approvals/{{id}}` includes artifact payload.
  - `POST /approvals/{{id}}/decide` — Owner/Member, sends Temporal signal.
- Audit log: every decision recorded.

## Acceptance Criteria
- [ ] Table created with FKs + indexes
- [ ] APIs respect workspace isolation
- [ ] Decide endpoint correctly transitions status and signals Temporal
- [ ] Viewer 403 on decide
- [ ] Pagination + filters working
- [ ] Audit log written
""",
        ["story", "type:story", "priority:high", "ready-for-dev"],
    ),
    (
        "AE-232",
        "[Story] Review-UI-1 — Channel settings: review profile picker + per-artifact toggles",
        """> Mirror of {link}. Parent epic: AE-226.

## Scope
- New section on `/dashboard/channels/[id]/settings` → "Review Profile".
- Profile preset chips: Hands-off / Quick / Standard / Full Control / Custom.
- Selecting a preset auto-fills the 13 toggles below.
- Toggling any gate flips profile to `Custom`.
- 13 toggles grouped by pipeline phase.
- Save posts to `PATCH /channels/{{id}}/review-config`.

## Acceptance Criteria
- [ ] All 5 presets visible and selectable
- [ ] Preset auto-fills toggles
- [ ] Toggle flips to `Custom`
- [ ] Save persists; reload reflects state
- [ ] Viewer sees read-only view
- [ ] Save shows success toast
""",
        ["story", "type:story", "priority:high", "ready-for-dev"],
    ),
    (
        "AE-233",
        "[Story] Review-UI-2 — Unified inbox `/dashboard/review` with diff-style artifact viewer",
        """> Mirror of {link}. Parent epic: AE-226.

## Scope
- New route `/dashboard/review`.
- Left rail: pending approvals list, filterable by channel + artifact type.
- Main pane: selected artifact viewer (delegated to AE-234).
- Approve / Edit / Reject action bar fixed at bottom.
- Reject requires comment modal.
- Edit opens inline editor (AE-234).
- Real-time refresh via polling.
- Sidebar nav: add "Review" item with count badge.

## Acceptance Criteria
- [ ] Route accessible to Owner + Member only
- [ ] List shows correct pending approvals scoped to workspace
- [ ] Selecting an item loads it in main pane
- [ ] Approve / Reject / Edit work end-to-end with Temporal signal
- [ ] Badge count matches list count
- [ ] Empty state shown when zero pending
""",
        ["story", "type:story", "priority:high", "ready-for-dev"],
    ),
    (
        "AE-234",
        "[Story] Review-UI-3 — Per-artifact viewer/editor (script, JSON, image, video)",
        """> Mirror of {link}. Parent epic: AE-226.

## Scope
Each artifact has a dedicated viewer/editor:

| Artifact | Viewer | Editor |
|---|---|---|
| research_data | Bullet list w/ sources | Add/remove/edit bullets |
| brand_alignment_report | Markdown panel | Read-only |
| topic_title | Title candidates list | Pick / edit text |
| story_script | Rich text panel | Inline rich-text editor |
| script_voice_data | Segmented script | JSON editor (Monaco) |
| script_assets_data | Per-scene prompts | Edit prompts inline |
| script_direction_data | Per-scene direction | Edit direction text |
| voice_track | Audio player | Re-run only |
| scene_images | Image grid | Replace frames (upload) |
| remotion_v3_json | Monaco JSON + preview | Edit JSON |
| metadata | Form | Edit form |
| thumbnail | Image viewer | Upload replacement |
| final_video | Video player | Re-run only |

## Acceptance Criteria
- [ ] Each artifact opens in the correct viewer
- [ ] Edit mode persists edited payload via signal
- [ ] Cancel discards edits
- [ ] All editors validate before submit (e.g. JSON parse)
- [ ] Loading + error states for each viewer
""",
        ["story", "type:story", "priority:high", "ready-for-dev"],
    ),
]

# ── PHASE B: 26 sub-tasks (jira_key, parent_jira_key, title, body, extra_labels) ──

# Common labels for sub-tasks: subtask, type:subtask, priority:high, ready-for-dev

SUB = [
    ("AE-235", "AE-227", "[Sub] BE — Migration: collapse roles + CHECK constraint",
     "Migration `2026XXXX_role_preset_consolidation.sql`:\n- `UPDATE workspace_members SET role='member' WHERE role IN ('admin','producer','editor');`\n- `UPDATE workspace_members SET role='viewer' WHERE role='reviewer';`\n- Same on `workspace_invitations`.\n- `ADD CONSTRAINT chk_role CHECK (role IN ('owner','member','viewer'))`.\n- Rollback script included.",
     ["layer:infra"]),
    ("AE-236", "AE-227", "[Sub] BE — Role preset → permission bundle mapping + API validation",
     "- `auth.py` role-bundle config: map `owner|member|viewer` → permission sets (reuse AE-78 32-permission matrix).\n- `workspace.py` invite/role-change: validate `role IN {owner, member, viewer}`; 400 otherwise.\n- Confirm `GET /auth/me` returns correct resolved `permissions[]`.",
     []),
    ("AE-237", "AE-227", "[Sub] FE — 3-option role picker on all surfaces + e2e tests",
     "Update invite modal, member edit dropdown, onboarding wizard role step to show 3 options with tooltips. E2E test: invite Member, accept, verify capability boundaries.",
     []),
    ("AE-238", "AE-228", "[Sub] BE — Migration: `channels.platform` column + CHECK + backfill",
     "Migration `2026XXXX_channels_platform.sql`:\n- `ADD COLUMN platform TEXT NOT NULL DEFAULT 'youtube'`\n- `ADD CONSTRAINT chk_platform CHECK (platform IN ('youtube','instagram','tiktok','twitter','linkedin'))`\n- Backfill covered by DEFAULT.\n- Rollback script included.",
     ["layer:infra"]),
    ("AE-239", "AE-228", "[Sub] BE — `channels.py` API: accept/return `platform`, 501 for non-youtube",
     "- POST/PATCH/GET /channels accept and return `platform` (default `youtube`).\n- Validate against reserved set; unknown → 400.\n- Non-youtube valid → 501 with message `\"platform 'X' will be supported in a future release\"`.\n- Regenerate OpenAPI schema.",
     []),
    ("AE-240", "AE-228", "[Sub] FE — Platform-aware channel UI + disabled \"Coming soon\" pickers",
     "- Update TS `Channel` type with `platform`.\n- Channel cards show platform icon + label.\n- Create form: platform select with `youtube` enabled + non-YouTube disabled with \"Coming soon\" tooltip.\n- String audit for hardcoded \"YouTube channel\" copy.",
     []),
    ("AE-241", "AE-229", "[Sub] BE — Migration: `channels.review_config` JSONB column + default",
     "`ALTER TABLE channels ADD COLUMN review_config JSONB NOT NULL DEFAULT '{\"profile\":\"hands_off\",\"gates\":{}}'::jsonb`. Existing rows = `hands_off`. New-via-UI = `standard` (set by API). Rollback script included.",
     ["layer:infra"]),
    ("AE-242", "AE-229", "[Sub] BE — GET/PATCH `/channels/{id}/review-config` + profile resolver",
     "- `GET` — Owner/Member/Viewer can read.\n- `PATCH` — Owner/Member only. Accepts `profile` or `gates`. `gates` forces profile=custom.\n- Validation: unknown gate keys → 400. Schema validates against 13 artifact keys.",
     []),
    ("AE-243", "AE-229", "[Sub] Tests — review_config API + resolver unit tests",
     "- Unit: preset → gates resolver (5 cases × snapshot).\n- API: GET returns default for new channel.\n- API: PATCH `profile=standard` auto-fills 5 gates.\n- API: explicit gates → profile=custom.\n- API: 400 on unknown gate key.\n- Authorization: Viewer 403 on PATCH.",
     ["test-case"]),
    ("AE-244", "AE-230", "[Sub] BE — `src/temporal_workflows/review_gate.py` module + `await_approval()`",
     "- `ApprovalResult` dataclass + `ReviewRejected` exception.\n- `async def await_approval(channel_id, video_id, artifact_key, artifact_payload) -> ApprovalResult`.\n- Activity-based config read.\n- Gate OFF → immediate return.\n- Gate ON → insert approval row + `wait_condition`.",
     []),
    ("AE-245", "AE-230", "[Sub] BE — Signal handler `submit_approval()` + decision dispatch",
     "- `@workflow.signal` method `submit_approval(artifact_key, decision, edited_payload?, comment)`.\n- `self._decisions` dict keyed by artifact_key.\n- Approve / Edit / Reject dispatch.\n- Reject retry max 3 then propagate.",
     []),
    ("AE-246", "AE-230", "[Sub] Tests — Temporal time-skip tests + one wired-phase integration",
     "- Time-skipping: gate OFF returns immediately (< 5ms).\n- Time-skipping: gate ON pauses until signal.\n- Approve/Edit/Reject path tests.\n- Integration: wire `await_approval` into research_data phase end-to-end.",
     ["test-case"]),
    ("AE-247", "AE-231", "[Sub] BE — Migration: `approvals` table + indexes",
     "Create `approvals` table per AE-231 spec. Indexes `(workspace_id, status)` and `(workflow_id)`. FKs ON DELETE RESTRICT for workspace_id / channel_id / video_id / decided_by.",
     ["layer:infra"]),
    ("AE-248", "AE-231", "[Sub] BE — Approvals APIs (list / get / decide) + permission gating",
     "- `GET /approvals` paginated + filters scoped to workspace.\n- `GET /approvals/{id}` includes payload.\n- `POST /approvals/{id}/decide` — Owner/Member, Viewer 403. Sends Temporal signal. Atomic status transition.",
     []),
    ("AE-249", "AE-231", "[Sub] BE — Audit log integration + tests",
     "- Every decide writes to `audit_log` with actor, before/after.\n- Tests: filters, pagination, signal mock, audit row, Viewer 403, cross-workspace 404.",
     ["test-case"]),
    ("AE-250", "AE-232", "[Sub] FE — Review Profile picker component (presets + 13 toggles)",
     "- New section on `/dashboard/channels/[id]/settings` → \"Review Profile\".\n- 5 preset chips.\n- 13 grouped toggles.\n- Preset → toggles auto-fill.\n- Toggle → `Custom` profile.\n- Tooltip per toggle.",
     []),
    ("AE-251", "AE-232", "[Sub] FE — API integration + persistence + tests",
     "- Wire to GET/PATCH `/channels/{id}/review-config`.\n- Save → toast + state refresh.\n- Viewer read-only with lock icon.\n- Tests: preset, toggle, save round-trip, viewer read-only.",
     ["test-case"]),
    ("AE-252", "AE-233", "[Sub] FE — `/dashboard/review` route + sidebar nav with count badge",
     "- New Next.js route. Owner/Member only.\n- Sidebar adds \"Review\" item with pending-count badge.\n- Badge polls `/approvals?status=pending&limit=1` every 30s.\n- Empty state when no pending.",
     []),
    ("AE-253", "AE-233", "[Sub] FE — Approvals list + filters (channel, artifact, status)",
     "- Left rail: channel · video · artifact_key badge · relative time.\n- Filters: channel select, artifact_key multi-select, status (default pending).\n- Infinite/cursor pagination.",
     []),
    ("AE-254", "AE-233", "[Sub] FE — Action bar (Approve / Edit / Reject) + decision flow",
     "- Fixed bottom bar.\n- Approve → POST decide.\n- Edit → opens AE-234 editor; submit posts decide+edited_payload.\n- Reject → modal with required comment.\n- On success: remove + advance.",
     []),
    ("AE-255", "AE-233", "[Sub] Tests — Playwright E2E for review inbox",
     "Playwright: badge=list count; Member can approve; Viewer 403; reject requires comment; empty state.",
     ["test-case"]),
    ("AE-256", "AE-234", "[Sub] FE — Artifact viewer dispatcher + routing by `artifact_key`",
     "Central component takes an approval row and renders correct viewer based on `artifact_key`. Handles loading/error/edit-mode/cancel.",
     []),
    ("AE-257", "AE-234", "[Sub] FE — Text/script viewer + rich-text editor (research_data, story_script, ...)",
     "Rich text for: research_data (bullets), brand_alignment_report (md, read-only), topic_title (candidates + edit), story_script (rich-text editor), script_direction_data (per-scene editable list). Non-empty validation.",
     []),
    ("AE-258", "AE-234", "[Sub] FE — JSON viewer/editor (Monaco) for script_voice_data, script_assets_data, remotion_v3_json",
     "Monaco editor: JSON schema validation, diff view, pretty-print + collapse, per-artifact schema hint via TS types.",
     []),
    ("AE-259", "AE-234", "[Sub] FE — Image viewer + replace flow (scene_images, thumbnail)",
     "- scene_images: grid + enlarge + per-frame replace upload (server-side validated MIME/size).\n- thumbnail: single image viewer with replace.\n- Upload returns asset URL → injected into edited payload.",
     []),
    ("AE-260", "AE-234", "[Sub] FE — Audio/video players (voice_track, final_video) + metadata form",
     "- voice_track: audio player. Approve/reject only (reject re-runs voice phase).\n- final_video: HTML5 video with frame-step. Approve/reject only.\n- metadata: editable form (title, description, tags chips, end-screen).\n- All players show duration/size/scrubber.",
     []),
]

# ── EXECUTE ─────────────────────────────────────────────────────────────────


def main() -> None:
    if not MAP_PATH.exists():
        print(f"ERROR: {MAP_PATH} not found. Are you in repo root?", file=sys.stderr)
        sys.exit(1)
    mapping = json.loads(MAP_PATH.read_text())
    # Reverse map: AE-key → gh#
    reverse = {v: int(k) for k, v in mapping.items()}

    print("\n── Phase A: epic + 3 bugs + 8 stories ──")
    for key, title, body_tmpl, labels in PHASE_A:
        body = body_tmpl.format(link=jira_link(key))
        num = gh_create(title, body, labels)
        mapping[str(num)] = key
        reverse[key] = num

    print("\n── Phase B: 26 sub-tasks ──")
    base_sub_labels = ["subtask", "type:subtask", "priority:high", "ready-for-dev"]
    for key, parent_key, title, body_text, extra in SUB:
        parent_gh = reverse.get(parent_key)
        parent_ref = f"#{parent_gh} ({parent_key})" if parent_gh else parent_key
        body = (
            f"> Mirror of {jira_link(key)}. Parent story: {parent_ref}.\n\n"
            f"## Scope\n\n{body_text}\n"
        )
        labels = base_sub_labels + extra
        num = gh_create(title, body, labels)
        mapping[str(num)] = key
        reverse[key] = num

    print("\n── Phase C: write issue_map.json ──")
    MAP_PATH.write_text(json.dumps(mapping, indent=2) + "\n")
    print(f"  → wrote {len(mapping)} mappings to {MAP_PATH}")

    print("\n── Phase D: bump labels on existing GH #216 (AE-208) and #217 (AE-209) ──")
    for gh_num in (216, 217):
        gh_remove_labels(gh_num, ["priority:medium"])
        gh_add_labels(gh_num, ["priority:high"])
        print(f"  → #{gh_num} bumped to priority:high")

    print("\n✅ Done.")


if __name__ == "__main__":
    main()
