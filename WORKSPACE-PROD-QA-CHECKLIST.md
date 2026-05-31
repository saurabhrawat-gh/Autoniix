# Workspace Section — Production Verification Checklist

> **Owner runbook for E2E verification on https://dash.autoniix.com after the workspace QA pass.**
> Tick items as you go. Each item links to the Jira test case it verifies.
> Estimated time: **45–60 minutes** for the full pass.

**Date of this run:** ____________  **Operator:** ____________

---

## Pre-flight

- [ ] Open **two** browsers side-by-side: Chrome (regular profile) + Chrome incognito (or different browser entirely)
- [ ] Have 3 throwaway email addresses ready. Gmail `+` aliases work: `yourname+ae-qa-01@gmail.com`, `+02`, `+03`
- [ ] Open **DevTools → Application → Cookies** in both browsers (you'll be checking `access_token`, `refresh_token` cookies)
- [ ] Open **DevTools → Network** in incognito browser (you'll inspect responses)
- [ ] Confirm prod is reachable: `curl -sI https://dash.autoniix.com/ | head -1` → expect `HTTP/2 200`

---

## §1 — Solo-mode lifecycle (AE-275) · ~10 min

**Goal:** verifies AE-264 privilege-escalation hotfix end-to-end + new-user happy path.

### 1.1 Fresh registration → workspace creation
- [ ] Incognito → `/register` with `+ae-qa-01@gmail.com`, password `Test1234!`, workspace name "QA Solo 01"
- [ ] Expected redirect to `/dashboard` (or `/onboarding`)
- [ ] DevTools → Cookies: `access_token` exists, **HttpOnly: ✓, Secure: ✓, SameSite: Lax/Strict**
- [ ] GET `https://dash.autoniix.com/api/v2/auth/me` (paste in URL bar of the same incognito):
  - [ ] Response `user.role` = `"viewer"` (NOT `"owner"` — that's the AE-264 fix)
  - [ ] Response `ws_role` = `"owner"`
  - [ ] Response `wid` = a NEW workspace id (not 1)

### 1.2 Solo workspace UX
- [ ] Navigate to `/dashboard/workspace`
- [ ] Members card shows: **1/3 seats — Starter** (or similar)
- [ ] Invite UI is visible (CTA present)
- [ ] No "Remove" or "Transfer ownership" actions visible against yourself (you're the only owner)

### 1.3 Cannot demote/remove self (last-owner protection)
- [ ] Try changing your own role via the API:
  ```bash
  # In incognito DevTools → Console:
  fetch('/api/v2/workspace/members/<YOUR_USER_ID>/role',
    {method:'PUT', headers:{'Content-Type':'application/json'},
     body:JSON.stringify({role:'member'})})
    .then(r => r.json()).then(console.log)
  ```
- [ ] Expected: **400** with `"last owner"` in detail
- [ ] Try removing yourself: `fetch('/api/v2/workspace/members/<YOUR_USER_ID>', {method:'DELETE'})`
- [ ] Expected: **400** with `"last owner"` in detail

### 1.4 Logout / login cycle persists workspace
- [ ] Logout → land on login page
- [ ] Cookies cleared
- [ ] Login again with same credentials
- [ ] `/api/v2/auth/me` → same `wid`, role still `viewer`+`owner`

**§1 verdict:** ☐ PASS ☐ FAIL — note any AC numbers from AE-275 that failed: _____________

---

## §2 — Permission grid spot-check (AE-267) · ~8 min

**Goal:** 18 negative cases are unit-tested (72/72 pytest green) — these are 5 high-value manual spot-checks to prove the wiring works on prod.

> **Prerequisite:** create a member user. Easiest path: from your owner browser, invite `+ae-qa-02@gmail.com` as `member`, accept the invite in a 3rd incognito window, log in.

### 2.1 Member cannot invite (WS-PERM-03)
- [ ] Logged in as the `member` user, DevTools → Console:
  ```js
  fetch('/api/v2/workspace/invites',
    {method:'POST', headers:{'Content-Type':'application/json'},
     body:JSON.stringify({email:'foo@bar.com', role:'viewer'})})
    .then(r => r.status).then(console.log)
  ```
- [ ] Expected: **403**
- [ ] Response detail contains: `"Permission denied: workspace.members.invite"`

### 2.2 Member cannot rename workspace (WS-PERM-01)
- [ ] As member: navigate to `/dashboard/workspace/settings`
- [ ] "Save" button should be **disabled** or attempting save returns **403**
- [ ] Direct API: `fetch('/api/v2/workspace', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:'Hacked'})}).then(r => r.status)`
- [ ] Expected: **403**, detail: `"Permission denied: workspace.settings.edit"`

### 2.3 Member cannot transfer ownership (WS-PERM-10)
- [ ] `fetch('/api/v2/workspace/transfer-ownership', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({new_owner_user_id:1, current_password:'Test1234!'})}).then(r => r.status)`
- [ ] Expected: **403**

### 2.4 Viewer can read but not write
- [ ] Invite a 3rd email as `viewer`. Accept in another incognito.
- [ ] As viewer: `fetch('/api/v2/workspace').then(r => r.status)` → **200**
- [ ] As viewer: `fetch('/api/v2/workspace/integrations').then(r => r.status)` → **403** (WS-PERM-13)
- [ ] As viewer: `fetch('/api/v2/workspace/members/<owner_id>/role', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({role:'viewer'})}).then(r => r.status)` → **403**

### 2.5 Error message contract (FE/Sentry rely on this)
- [ ] At least one of the above 403s has a detail string **starting with exactly** `"Permission denied: "` (capital P, space after colon)

### 2.5b ⚠️ SECURITY — Token brute-force rate limit (AE-269 WS-ACC-15)

> Static code review couldn't confirm a rate limiter on `/api/v2/auth/accept-invite`. Verify on prod.

- [ ] In incognito (no auth needed — endpoint is public), DevTools → Console:
  ```js
  // Fire 200 random-token POSTs as fast as the browser will let us
  const results = await Promise.all(
    Array.from({length: 200}, (_, i) => {
      const fakeToken = Array.from({length:64}, () =>
        '0123456789abcdef'[Math.floor(Math.random()*16)]).join('');
      return fetch('/api/v2/auth/accept-invite', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({token: fakeToken, password: 'irrelevant1'})
      }).then(r => r.status);
    })
  );
  // Count distinct status codes
  const counts = results.reduce((acc, s) => (acc[s]=(acc[s]||0)+1, acc), {});
  console.log(counts);
  ```
- [ ] **Expected (rate limiter present):** `{400: <=N, 429: 200-N}` where 429 starts firing within the first ~10–50 attempts
- [ ] **CURRENT (suspected gap):** `{400: 200}` with zero 429s → **rate limiter MISSING**
- [ ] If rate limiter is missing, file new bug:
  - Title: `bug | Public /accept-invite has no rate limit — token brute-force possible`
  - Labels: `bug:production`, `priority:critical`, `security`, `workspace`
  - Reference: AE-269 WS-ACC-15

**§2 verdict:** ☐ PASS ☐ FAIL — _____________

---

## §3 — Invitation lifecycle (AE-268 / AE-269) · ~12 min

### 3.1 Happy-path invite
- [ ] Owner: invite `+ae-qa-04@gmail.com` as `member`, expires_days=7
- [ ] **Check inbox** — email arrives within 60s with subject containing "workspace" or "invitation"
- [ ] Open invite link from email — lands at `/accept-invite?token=...`
- [ ] Form prompts for password (account creation flow) since email isn't registered yet
- [ ] Submit → redirected into the OWNER's workspace as `member`
- [ ] Owner refreshes members page — sees 2 members + 0 pending

### 3.2 Expired invite (WS-PLAN / WS-ACCEPT)
- [ ] Invite `+ae-qa-05@gmail.com` with `expires_days=1` (can't easily simulate expiry without DB; alternative: revoke immediately)
- [ ] Owner: open `/dashboard/workspace`, locate the pending invite, click **Revoke**
- [ ] Confirm in DB or via list_invites that the invite is gone (or `accepted_at` is null and it's removed)
- [ ] Try to use the original (now-revoked) invite link → expect **404** or `"invite_not_found"` or `"invite_expired"`

### 3.3 Duplicate invite (AE-262 regression)
- [ ] Owner: invite `+ae-qa-06@gmail.com` as `viewer`
- [ ] Immediately invite the SAME email again as `viewer`
- [ ] Expected: **409 Conflict** — `"A pending invitation already exists"` (NOT a duplicate row)
- [ ] **If a second invite is accepted with 200**, AE-262 is still broken → comment on AE-262

### 3.4 Plan limit enforcement (WS-PLAN-01..05)
- [ ] In a Starter workspace at 2/3 seats (you should be there from the above invites)
- [ ] Invite one more email → expected **200** (now 3/3)
- [ ] Invite one MORE → expected **402** with detail mentioning `"Plan limit reached"` and `"starter"`
- [ ] FE: Members card shows "Upgrade" CTA

### 3.5 Cross-workspace token rejection
- [ ] Take an unaccepted invite token URL from Workspace A
- [ ] Logout, login as a user in Workspace B (a totally separate one)
- [ ] Paste the WS-A accept URL while logged in as WS-B user
- [ ] Expected: invite either creates membership in WS-A (correct) OR rejects cleanly (also correct); **MUST NOT** silently grant WS-B membership or fail with 500

**§3 verdict:** ☐ PASS ☐ FAIL — _____________

---

## §4 — Role change + ownership transfer (AE-270 / AE-272) · ~5 min

### 4.1 Promote member → owner (creates 2 owners)
- [ ] Owner: PUT `/api/v2/workspace/members/<member_id>/role` body `{"role":"owner"}`
- [ ] Expected: **200**
- [ ] Owner count is now 2

### 4.2 Demote one owner safely
- [ ] Demote either owner back to `member` → **200**
- [ ] Last owner standing — try to demote them → **400** `"last owner"`

### 4.3 Ownership transfer with password
- [ ] Owner: POST `/api/v2/workspace/transfer-ownership` with `{"new_owner_user_id": <member_id>, "current_password": "wrong-password"}`
- [ ] Expected: **401/403** invalid password
- [ ] Retry with correct password → **200**
- [ ] Both rows: original owner is now `member`, target is now `owner`
- [ ] Owner email: `workspaces.owner_user_id` updated (DB-level check optional)

**§4 verdict:** ☐ PASS ☐ FAIL — _____________

---

## §5 — Member removal + revocation cascade (AE-271) · ~5 min

### 5.1 Remove a member
- [ ] Owner: DELETE `/api/v2/workspace/members/<member_id>`
- [ ] Expected: **200**
- [ ] Removed user opens their browser — **API calls return 403 `workspace_access_revoked`**
- [ ] Cookies are NOT auto-cleared (security note) — but every authenticated call fails

### 5.2 Removed user cannot re-enter via old session
- [ ] In the removed user's browser, navigate to `/dashboard/workspace`
- [ ] Expected: redirect to login OR 403 banner OR empty state
- [ ] If they had `active_workspace_id` pointing to the removed workspace: API returns 403 and FE handles gracefully

### 5.3 Last-owner cannot be removed
- [ ] Solo workspace owner tries to DELETE themselves → **400** `"last owner"`

**§5 verdict:** ☐ PASS ☐ FAIL — _____________

---

## §6 — SECURITY — cross-workspace data isolation (AE-273 + bug AE-276) · ~8 min

> ⚠️ **AE-276 is filed as `bug:production` `priority:critical`.** Until the fix lands, these tests will FAIL on prod. That's expected. **Re-run §6 after the fix deploys** as the verification step.

### 6.1 Setup — two workspaces
- [ ] You should have access to **Workspace A** (your original) and **Workspace B** (the one you transferred to, or create a new one).
- [ ] Note: WS-A id = ____, WS-B id = ____

### 6.2 Read leak (AE-276 — WS-ISO-08)
- [ ] Logged in as a user in WS-A only, DevTools → Console:
  ```js
  fetch('/api/v2/workspace/settings?scope=workspace&scope_id=<WS-B-ID>')
    .then(r => r.json()).then(console.log)
  ```
- [ ] **CURRENT (BROKEN):** returns 200 with WS-B's settings → confirms AE-276 still reproduces. Comment on AE-276.
- [ ] **AFTER FIX:** expected **403** or **404**
- [ ] Test all 6 scope types: `workspace`, `brand`, `channel`, `series`, `campaign`, `project` (substitute any valid id from WS-B)

### 6.3 Write leak (AE-276 — WS-ISO-09 — SEVERE)
- [ ] Logged in as WS-A user with `workspace.settings.edit` perm (= owner of WS-A):
  ```js
  fetch('/api/v2/workspace/settings', {method:'PUT',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({scope:'workspace', scope_id:'<WS-B-ID>',
                          key:'qa_canary', value:{tampered:true}, locked:false})})
    .then(r => r.status).then(console.log)
  ```
- [ ] **CURRENT (BROKEN):** 200 — you just wrote to a workspace you don't own. Confirms AE-276.
- [ ] Log out, log in as WS-B owner, navigate to workspace settings — verify the `qa_canary` key exists with `{tampered:true}` → **confirms cross-tenant write succeeded** (do NOT skip this proof)
- [ ] **AFTER FIX:** expected **403**

### 6.4 Other cross-workspace surfaces
- [ ] As WS-A user: try `fetch('/api/v2/workspace/brands/<brand_id_from_WS_B>')` → expected **404** (brand handler filters by workspace_id, should be fine)
- [ ] As WS-A user: try `fetch('/api/v2/workspace/projects/<project_id_from_WS_B>')` → expected **404**
- [ ] **If either returns 200**, file a new bug like AE-276

### 6.5 Plan-limit race (AE-277 — WS-RACE-06)
- [ ] In a Starter workspace at **2/3 seats** (1 seat remaining):
- [ ] DevTools → Console:
  ```js
  await Promise.all([
    fetch('/api/v2/workspace/invites', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email:'race-a@test.com', role:'viewer'})}),
    fetch('/api/v2/workspace/invites', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email:'race-b@test.com', role:'viewer'})}),
    fetch('/api/v2/workspace/invites', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email:'race-c@test.com', role:'viewer'})}),
  ]).then(rs => rs.map(r => r.status));
  ```
- [ ] **CURRENT (BROKEN):** multiple 200s (overflow). Confirms AE-277.
- [ ] **AFTER FIX:** expected exactly **one 200**, the rest **402**
- [ ] Cleanup: revoke the orphan invites afterwards

**§6 verdict:** ☐ PASS ☐ FAIL (expected FAIL until AE-276/277 fix lands) — comments left on _________

---

## §7 — UI / Audit log smoke (AE-274) · ~5 min

### 7.1 Members page
- [ ] `/dashboard/workspace` renders with: header, plan badge, seat count, members table, invites table, integrations card
- [ ] Empty-pending state shows "No pending invites" (or equivalent)
- [ ] Owner sees "Remove" + "Change role" + "Transfer ownership" buttons; member sees none; viewer sees only the read view

### 7.2 Audit log visible to owner
- [ ] Navigate to `/dashboard/workspace/audit` (or wherever audit log lives in your build)
- [ ] Owner: sees recent events (invite.create, settings.upsert, etc. from your testing today)
- [ ] Member: hits **403** at the API → FE shows access-denied banner
- [ ] Viewer: same — **403**

### 7.3 Toast / error UX
- [ ] Trigger any 403 (e.g. as member, click some owner-only button if present, OR run a manual fetch)
- [ ] Confirm there is a visible error toast/banner, NOT a silent failure or raw stack trace

**§7 verdict:** ☐ PASS ☐ FAIL — _____________

---

## §8 — Wrap-up

- [ ] Total **PASS** sections: ___/7
- [ ] Total **FAIL** sections (expected vs unexpected): _______
- [ ] Bugs filed during this run (new only, in addition to AE-276/277): _____________________
- [ ] All test-throwaway workspaces archived/deleted? (optional cleanup)
- [ ] Post one-line summary on **AE-266** (epic): *"Prod manual QA pass complete {date}. N/7 sections green. Bugs filed: AE-XXX, AE-YYY."*

---

## Quick reference — what's expected to FAIL until hotfixes deploy

| Section | Bug | Expected behaviour today | After fix |
|---|---|---|---|
| §3.3 | **AE-262** | duplicate invite rows possible | 409 |
| §6.2 §6.3 | **AE-276** | cross-WS read AND write succeed (200) | 403 |
| §6.5 | **AE-277** | seat overflow possible via parallel calls | exactly one 200 |

All other sections must be green for the workspace section to be production-hardened.

---

## When to mark AE-266 (epic) verified

Mark `AE-266` → **Prod Verified** ONLY when ALL of the following are true:
1. ✅ §1, §2, §4, §5, §7 are PASS on prod
2. ✅ §3 is PASS after AE-262 fix lands
3. ✅ §6 is PASS after AE-276 + AE-277 fixes land
4. ✅ All 9 child stories (AE-267..275) are in **Done** or **Prod Verified**
5. ✅ Zero open `bug:production` issues against the workspace section

Until then, the epic stays **In QA** and the next QA pass starts the day after each hotfix deploys.
