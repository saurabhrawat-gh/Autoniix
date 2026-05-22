---
description: Verified command — mark one or all tested issues as verified. Works for both local QA (in-qa → qa-verified) and production (in-prod → prod-verified + auto-tick ACs + close).
---

# /verified — Issue Verification Command

Use this workflow when you have finished testing and want to mark an issue as verified.

**Usage:**
```
verified #42           — verify a specific issue
verified #42 #45 #47   — verify multiple issues at once
verified all           — verify every issue currently in-qa (local) or in-prod (production)
```

This workflow handles both QA and production contexts automatically — it detects the stage of each issue from its labels.

---

## Step 1 — Parse the command

- Read the input. Extract issue numbers if specific ones are given.
- If `all` is used: call `mcp0_list_issues` with `labels=in-qa,state=open` AND a separate call with `labels=in-prod,state=open`. Collect all matching issue numbers.
- Skip any issue that is a pull request.

---

## Step 2 — For each issue: detect context

Call `mcp0_get_issue` to read the issue's current labels and body.

| Current label | Context | Action |
|---|---|---|
| `in-qa` | Local QA testing complete | QA-verified flow (Step 3) |
| `in-prod` | Production testing complete | Prod-verified flow (Step 4) |
| Neither | Wrong state | Print warning: "Issue #N is not in-qa or in-prod — skipping" |

---

## Step 3 — QA-Verified flow (`in-qa` issues)

**3.1 Announce**
Print:
```
✅ Marking #N as qa-verified.
   Story: {issue title}
   Stage: Local QA → QA Verified → (auto) Ready to Deploy → In Prod
```

**3.2 Update labels**
Call `mcp0_update_issue`:
- Remove label: `in-qa`
- Add label: `qa-verified`

**3.3 Transition Jira**
- Look up the Jira key for this issue via `scripts/migration/state/issue_map.json`
- Call `mcp0_transitionJiraIssue` with cloudId `73672c49-7089-4f35-adde-e3fa0d1e438f`, transition id `51` (→ QA Verified)

**3.4 Post comment**
Call `mcp0_add_issue_comment`:
```
✅ **QA Verified** — confirmed by product owner after local testing on `develop`.

GitHub Actions will now automatically:
1. Add `ready-to-deploy`
2. Create and merge the `develop → main` release PR
3. Set `in-prod` after deploy completes

Next: verify at https://dash.autoniix.com once deployed.
```

**3.5 Continue to next issue.**

---

## Step 4 — Prod-Verified flow (`in-prod` issues)

**4.1 Announce**
Print:
```
✅ Marking #N as prod-verified.
   Story: {issue title}
   Stage: In Prod → (auto-tick ACs) → Prod Verified → Done
```

**4.2 Auto-tick all acceptance criteria checkboxes**
- Read the issue body (already fetched in Step 2).
- Replace every occurrence of `- [ ]` with `- [x]` in the body text.
- If there are zero `- [ ]` patterns, skip this step (already ticked).
- Call `mcp0_update_issue` with the updated `body` to write the ticked checkboxes back.
- Print: "Ticked {N} acceptance criteria checkboxes."

**4.3 Transition Jira**
- Look up the Jira key for this issue via `scripts/migration/state/issue_map.json`
- Call `mcp0_transitionJiraIssue` with cloudId `73672c49-7089-4f35-adde-e3fa0d1e438f`, transition id `4` (→ Prod Verified)
- Then call `mcp0_transitionJiraIssue` with transition id `5` (→ Done)

**4.4 Add prod-verified label**
Call `mcp0_update_issue`:
- Add label: `prod-verified`

GitHub Actions `on-prod-verified` job fires automatically:
- Sees zero unchecked ACs → posts "✅ Production Verified — Closing" → closes the issue
- Epic rollup runs if this was a child story

**4.5 Post comment**
Call `mcp0_add_issue_comment`:
```
✅ **Production Verified** — confirmed by product owner on https://dash.autoniix.com.

All acceptance criteria have been marked complete.
GitHub Actions is closing this issue now.
```

**4.6 Continue to next issue.**

---

## Step 5 — Final summary

After processing all issues, print a summary:

```
── VERIFIED SUMMARY ──────────────────────────────────────────
  QA Verified (local → deploying):
    ✅ #42 feat | UI | Add workspace settings page
    ✅ #45 task | DB | Migrate provider catalog

  Prod Verified (closing):
    ✅ #19 story | Auth | Session Refresh Rotation

  Skipped (wrong state):
    ⚠️  #38 not in-qa or in-prod — current label: ready-for-dev
──────────────────────────────────────────────────────────────
```

---

## Rules

- Never run the prod-verified flow on an issue that has `in-qa` — check label carefully.
- Never remove labels other than `in-qa` during QA flow. GHA handles all subsequent transitions.
- Auto-tick ACs ONLY during the prod-verified flow, never during QA flow.
- If an issue body has no `- [ ]` checkboxes at all, skip the auto-tick step silently and proceed.
- If `mcp0_update_issue` fails for the body update, print the error, pause, and do NOT add `prod-verified` — ask the user to retry.
- `verified all` in a mixed session (some `in-qa`, some `in-prod`) processes BOTH groups correctly.
