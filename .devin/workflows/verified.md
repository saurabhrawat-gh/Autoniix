---
description: Verified command — mark one or all tested issues as verified in production (in-prod → prod-verified + auto-tick ACs + close).
---

# /verified — Issue Verification Command

Use this workflow when you have finished testing on production and want to mark an issue as verified.

**Usage:**
```
verified #42           — verify a specific issue
verified #42 #45 #47   — verify multiple issues at once
verified all           — verify every issue currently in-prod
```

This workflow handles production verification only — issues must have the `in-prod` label.

---

## Step 1 — Parse the command

- Read the input. Extract issue numbers if specific ones are given.
- If `all` is used: call `mcp0_list_issues` with `labels=in-prod,state=open`. Collect all matching issue numbers.
- Skip any issue that is a pull request.

---

## Step 2 — For each issue: verify it is in-prod

Call `mcp0_get_issue` to read the issue's current labels and body.

| Current label | Action |
|---|---|
| `in-prod` | Prod-verified flow (Step 3) |
| Anything else | Print warning: "Issue #N is not in-prod — skipping" |

---

## Step 3 — Prod-Verified flow (`in-prod` issues)

**3.1 Announce**
Print:
```
✅ Marking #N as prod-verified.
   Story: {issue title}
   Stage: In Prod → (auto-tick ACs) → Prod Verified → Done
```

**3.2 Auto-tick all acceptance criteria checkboxes**
- Read the issue body (already fetched in Step 2).
- Replace every occurrence of `- [ ]` with `- [x]` in the body text.
- If there are zero `- [ ]` patterns, skip this step (already ticked).
- Call `mcp0_update_issue` with the updated `body` to write the ticked checkboxes back.
- Print: "Ticked {N} acceptance criteria checkboxes."

**3.3 Transition Jira**
- Look up the Jira key for this issue via `scripts/migration/state/issue_map.json`
- Call `mcp0_transitionJiraIssue` with cloudId `73672c49-7089-4f35-adde-e3fa0d1e438f`, transition id `4` (→ Prod Verified)
- Then call `mcp0_transitionJiraIssue` with transition id `5` (→ Done)

**3.4 Add prod-verified label**
Call `mcp0_update_issue`:
- Add label: `prod-verified`

GitHub Actions `on-prod-verified` job fires automatically:
- Sees zero unchecked ACs → posts "✅ Production Verified — Closing" → closes the issue
- Epic rollup runs if this was a child story

**3.5 Post comment**
Call `mcp0_add_issue_comment`:
```
✅ **Production Verified** — confirmed by product owner on https://dash.autoniix.com.

All acceptance criteria have been marked complete.
GitHub Actions is closing this issue now.
```

**3.6 Continue to next issue.**

---

## Step 4 — Final summary

After processing all issues, print a summary:

```
── VERIFIED SUMMARY ──────────────────────────────────────────
  Prod Verified (closing):
    ✅ #42 feat | UI | Add workspace settings page
    ✅ #19 story | Auth | Session Refresh Rotation

  Skipped (wrong state):
    ⚠️  #38 not in-prod — current label: ready-for-dev
──────────────────────────────────────────────────────────────
```

---

## Rules

- Only process issues with the `in-prod` label — skip everything else with a warning.
- Auto-tick ACs before adding `prod-verified`.
- If an issue body has no `- [ ]` checkboxes at all, skip the auto-tick step silently and proceed.
- If `mcp0_update_issue` fails for the body update, print the error, pause, and do NOT add `prod-verified` — ask the user to retry.
