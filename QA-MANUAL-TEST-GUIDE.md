# QA Manual Test Guide — Autoniix Production

> **Single reference for testing every ticket currently In-Prod.** 62 test sections cover all In-Prod stories, tasks, and bugs; the **Complete In-Prod Coverage Map** at the bottom lists every AE-key and the section that tests it.
> URL: https://dash.autoniix.com  
> Open DevTools (F12) → Network tab for any API-level checks.  
> Each test is written in plain English. Mark ✅ PASS or ❌ FAIL as you go.
> When a section passes on production, run `verified #<N>` (or `verified all`) — see the end of this doc.

---

## HOW TO FILE A BUG
If you find anything broken during testing, just type in Windsurf:
```
bug: [what happened], issue #N
```
Example: `bug: provider health badge not showing, issue #353`

---

## 1. Dashboard Background API Calls (AE-263)

**What was fixed:** The dashboard was making API calls even when you weren't looking at the tab. Now it pauses when the tab is hidden.

**Test steps:**
1. Open https://dash.autoniix.com in Chrome
2. Open DevTools → Network tab → filter by "Fetch/XHR" (click the XHR button)
3. Clear the network log (trash icon)
4. **Hover** over the provider cards in the Marketplace tab — you should see **zero** network requests fire just from hovering
5. Switch to another browser tab (e.g., open google.com in a new tab)
6. Wait 30 seconds
7. Come back to the Autoniix tab
8. Check the network log — you should see **one** refresh call fire right when you came back (not during the 30 seconds you were away)

**Pass if:** No requests fire on hover. No requests fire while tab is hidden. One request fires when you return.

---

## 2. Registration is Invite-Only (AE-264)

**What was fixed:** New users cannot self-register. Only invited users can join.

**Test steps:**
1. Open an incognito/private browser window
2. Go to https://dash.autoniix.com/register
3. You should **not** see a normal sign-up form with email + password fields
4. You should see a message like "Registration is invite-only" or a login page

**Pass if:** No self-registration form is accessible. Uninvited users cannot create accounts.

---

## 3. Member Invite — Plan Limits (AE-93 / AE-182 / AE-277)

**What was fixed:** Inviting more members than your plan allows is now blocked with a race-condition fix (two invites at the same time can't both succeed when you're at your limit).

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/settings → Members tab
2. Note how many members you currently have
3. Try inviting a new member (click "Invite" and enter an email)
4. If you're on the Starter plan (max 3 members) and already have 3, the invite should fail with a clear error message like "Plan limit reached"
5. If you're below your limit, the invite should succeed and you'll see the new invite in the pending list

**Pass if:** The system correctly blocks invites when at plan capacity, with a clear error message.

---

## 4. Ownership Transfer Protection (AE-94 / AE-183)

**What was fixed:** You cannot remove or demote the last owner of a workspace. You must transfer ownership first.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/settings → Members tab
2. Find your own account (you should be listed as "Owner")
3. Try to change your role to "Member" — should show an error: "Cannot demote the last owner"
4. Try to remove yourself from the workspace — should show an error or be blocked
5. To transfer ownership: click the "..." next to another member → "Make Owner" → confirm — this should work and you'll now be a Member

**Pass if:** Demoting/removing the last owner is blocked. Transferring to another member works.

---

## 5. Slack Webhook Notifications (AE-95 / AE-184)

**What was fixed:** When you invite a member, a Slack notification is sent to your configured webhook.

**Test steps (requires a Slack workspace + webhook URL):**
1. Go to https://dash.autoniix.com/dashboard/settings → Integrations (or Workspace settings)
2. Find the "Slack Webhook URL" field and enter your Slack webhook URL
3. Save
4. Invite a new member from the Members tab
5. Check your Slack channel — you should receive a notification about the new invite

**Pass if:** Slack message arrives within ~30 seconds of sending the invite.  
**Skip if:** You don't have a Slack webhook handy — note as "Cannot test, no webhook."

---

## 6. Provider Marketplace (AE-117 / AE-174 / AE-201 / AE-202)

**What was fixed:** The Marketplace tab shows all available provider integrations (OpenAI, ElevenLabs, SerpAPI, MinIO, etc.) with their connection status.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/providers
2. Click the **Marketplace** tab
3. You should see a grid/list of providers organized by category (LLM, Voice/TTS, Search, Storage, Video)
4. Providers you've already connected should show a green badge or "Connected" label
5. Providers not yet connected should show a "Connect" button
6. Click on any provider — it should take you to a detail/setup page

**Pass if:** You can see a full catalog of providers with correct connection status badges.

---

## 7. Add an LLM Credential — OpenAI or Anthropic (AE-195)

**What was fixed:** You can add AI provider credentials (OpenAI API key, Anthropic API key) and test them.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/providers → Connected tab (or via Marketplace)
2. Find the "LLM" section, click "Connect" or "Add credential"
3. Choose OpenAI → enter your API key → Save
4. You should see a health badge on the credential card (green = working, red = invalid key)
5. Click the "Test" or "Probe" button — should confirm the key is valid

**Pass if:** Credential is saved, health badge appears, probe returns success with a valid key.

---

## 8. Add a TTS/Voice Provider — ElevenLabs (AE-196)

**What was fixed:** You can add voice synthesis providers like ElevenLabs or EdgeTTS.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/providers → Connected tab
2. Find the "Voice (TTS)" or "Speech" section
3. Click "Add credential" → choose ElevenLabs → enter your API key → Save
4. EdgeTTS (Microsoft free TTS) should be addable without any API key
5. Health badge should appear on each added credential

**Pass if:** At least one TTS provider can be added and shows a health badge.

---

## 9. Add a Search Provider — SerpAPI (AE-117 / AE-197)

**What was fixed:** SerpAPI credentials can be added for web search capabilities.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/providers
2. Find "Web Search" or "Search" category
3. Add a SerpAPI credential (enter your SerpAPI key)
4. Click Test/Probe — should show green if key is valid

**Pass if:** SerpAPI credential is saved and health check passes.

---

## 10. Add Storage — MinIO (AE-119 / AE-198)

**What was fixed:** MinIO (S3-compatible object storage) credentials can be configured.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/providers
2. Find "Storage" category → Add MinIO credential
3. Enter: endpoint URL, access key, secret key, bucket name
4. Click Test — should connect successfully

**Pass if:** MinIO credential saves and test connection succeeds.

---

## 11. Connect YouTube Account — OAuth (AE-122 / AE-199)

**What was fixed:** You can connect a YouTube/Google account via OAuth2 for video uploads.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/providers → **Accounts** tab
2. Find "YouTube" → click "Connect YouTube" (or "Add account")
3. A Google OAuth popup/redirect should open
4. Sign in with your Google account and grant permissions
5. After connecting, you should see your YouTube channel name and thumbnail in the list

**Pass if:** OAuth completes, channel appears in the accounts list.

---

## 12. Provider Chain Editor (AE-175 / AE-203)

**What was fixed:** You can set a priority order (chain) for providers in each category. The system tries them top-to-bottom.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/providers → click on a category with 2+ credentials (e.g., LLM if you have OpenAI + Anthropic)
2. You should see a "Priority chain" or "Chain" section showing your credentials in order
3. Drag one credential to a different position in the list
4. The new order should save automatically (or with a Save button)
5. The first item in the chain = primary provider used by the pipeline

**Pass if:** Drag-and-drop reorder works and the new order is persisted.

---

## 13. Test vs Prod Provider Chains (AE-176 / AE-204)

**What was fixed:** You can set different provider chains for different content modes (Short, Long, etc.) so the pipeline uses different providers per content type.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/providers → click on a category
2. Look for content mode tabs or buttons (e.g., "Short form", "Long form", "All")
3. Switch between modes — each should show its own chain configuration
4. You can set a different primary provider for Short vs Long content

**Pass if:** Switching content modes shows mode-specific chains that can be configured independently.

---

## 14. Provider Health Status (AE-177 / AE-200 / AE-205)

**What was fixed:** Every provider credential shows a live health badge. A background job checks health every 5 minutes automatically.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/providers → Connected tab
2. Each credential card should have a green (healthy) or red (down) badge
3. There may also be a small sparkline/history chart showing recent health
4. Look for a "Probe all" or "Check health" button — clicking it should refresh all badges immediately
5. Wait ~5 minutes then refresh the page — badges should update automatically even if you didn't click anything

**Pass if:** Health badges are visible on all credential cards with correct status.

---

## 15. Provider Change Request Workflow (AE-178 / AE-206)

**What was fixed:** Members can request a credential change (e.g., new API key). Owners/admins approve or reject.

**Test steps (as a Member-role user):**
1. Go to https://dash.autoniix.com/dashboard/providers → click on a credential
2. Look for a "Request change" or "Submit change request" option
3. Enter a new API key value and submit
4. As an Owner (in another tab/account), go to the same provider → you should see a "Pending approval" notification
5. Approve → the new key should be applied. Reject → the old key remains.

**Pass if:** Change request can be submitted, shows as pending, and applying it updates the credential.  
**Skip if:** You only have one account — note as "Cannot test multi-user flow."

---

## 16. Credential Rotation Safe-Swap (AE-179 / AE-207)

**What was fixed:** Rotating (replacing) an API key is safe — the system tests the new key first. If it fails, the old key stays.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/providers → click on any connected provider credential
2. Find the "Rotate key" or "..." menu → "Update key" option
3. Enter a **valid** new API key → the system should test it, then apply it → you see a "Last rotated: [timestamp]"
4. Try again with an **invalid/garbage** key (e.g., "invalid123") → the system should reject it and keep the old key working

**Pass if:** Valid new key gets applied; invalid key is rejected without breaking the existing credential.

---

## 17. Channel Creation — YouTube Only (AE-218 / AE-219)

**What was fixed:** When creating a new channel, the platform is now locked to YouTube. You can no longer select TikTok, Instagram, etc.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/channels/new
2. You should be on the "Basics" step
3. Find the "Platform" field — it should show a **static YouTube badge** (red dot + "YouTube" text), NOT a dropdown
4. There should be no way to select any other platform
5. Complete the rest of the wizard and create the channel
6. Verify the created channel shows "Platform: YouTube" in its settings

**Pass if:** No platform dropdown exists. Static YouTube badge is shown. Channel creates successfully.

---

## 18. Workspace Roles — Owner / Member / Viewer Only (AE-227)

**What was fixed:** The workspace now has only 3 roles (Owner, Member, Viewer). Old roles like Admin, Producer, Editor, Reviewer no longer exist.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/settings → Members tab
2. Click the role dropdown next to any member
3. You should see exactly **3 options**: Owner, Member, Viewer — nothing else
4. Invite a new member → role picker should also show only 3 options
5. Members should be able to access content/pipeline features. Viewers should see things but not edit.

**Pass if:** Only 3 roles are available everywhere in the UI.

---

## 19. Open Registration (AE-80)

**What was built:** Anyone can self-register a new workspace at /register without an invite (creates a brand-new tenant).

**Test steps:**
1. Open an incognito window → https://dash.autoniix.com/register
2. Enter a fresh email, password, your name, and a workspace name (e.g. "Test Studio 2026")
3. Click Register
4. You should be auto-logged in and redirected to **/onboarding**
5. Check your email for a "Welcome to Autoniix" message
6. **Note:** If section #2 (AE-264) made registration invite-only, this flow is now gated — see ticket comment for clarification

**Pass if:** New workspace + new user + auto-login + redirect to onboarding all happen in one click.

---

## 20. Onboarding Wizard (AE-81)

**What was built:** First-time workspace owners walk through a 4-step setup wizard.

**Test steps:**
1. After registering a fresh workspace (from #19), you should land on /onboarding
2. **Step 1:** Confirm workspace name → click Continue
3. **Step 2:** Invite a teammate (or click "Skip for now")
4. **Step 3:** "Connect a YouTube channel" button — you can click it (opens channel connect flow) or Skip
5. **Step 4:** "You're all set!" → click "Go to Dashboard"
6. You arrive at /dashboard
7. **Resume check:** Log out at Step 2, log back in → you should resume at the same step (not restart)

**Pass if:** All 4 steps render, progress bar updates, skip buttons work, resume works, final redirect to /dashboard works.

---

## 21. Named Permission System (AE-78)

**What was built:** Backend enforces fine-grained permissions per role (32-permission matrix). Owner has all, Member subset, Viewer read-only.

**Test steps:**
1. Log in as your **Owner** account
2. Open DevTools → Network. Go to Settings → Members → click "Transfer Ownership" — request should succeed (200 status, modal appears)
3. Log out, log in as a **Viewer** (invite one if you don't have one, set role to Viewer)
4. As Viewer: navigate to /dashboard/settings → Members tab — you should NOT see the "Invite", "Change Role", or "Remove" buttons
5. As Viewer: try opening a provider credential edit page → you should see fields read-only or get a "permission denied" toast
6. As Viewer: in DevTools, manually POST to `/api/v2/workspace/invites` → expect 403 with "permission denied"

**Pass if:** Owner can do everything, Viewer sees no edit buttons and gets 403 from direct API calls.

---

## 22. Role-Based UI Navigation (AE-79)

**What was built:** The sidebar hides nav items the current user doesn't have permission to access.

**Test steps:**
1. Log in as Owner — sidebar should show all sections (Channels, Content, Providers, Settings, Analytics, etc.)
2. Log in as Member — sidebar should hide owner-only items (e.g. Billing, Workspace Settings)
3. Log in as Viewer — sidebar should hide create/edit-related items; should still show read views
4. Click a hidden URL directly in browser (e.g. as Viewer, type /dashboard/settings/billing) — should show "not authorized" or redirect away

**Pass if:** Sidebar items change per role. Direct URL access to forbidden pages is blocked.

---

## 23. Transactional Email — 8 Templates (AE-83)

**What was built:** Resend integration sends 8 different transactional emails. Each must arrive within a few minutes and look professional.

**Test the 8 triggers:**
1. **welcome-new-user** → register a new account (from #19) → check inbox for "Welcome to Autoniix"
2. **workspace-invite** → invite a teammate → check teammate's inbox for invite with green "Accept Invitation" button
3. **forgot-password** → click "Forgot password" on login → check inbox for reset link
4. **password-changed** → reset your password → check inbox for "Your password was changed" confirmation
5. **ownership-transferred-new** → transfer ownership to a member → that member's inbox should get "You are now the Owner"
6. **ownership-transferred-old** → after transfer, your inbox should get "Ownership of {workspace} has been transferred"
7. **member-removed** → remove a member from Settings → Members → that member's inbox should get "You've been removed from {workspace}"
8. **invite-accepted** (if present) → have an invitee click their link → inviter should get a notification (verify in Slack if email isn't wired)

**Pass if:** All 8 emails arrive within 2 minutes, render correctly (no broken HTML), and contain the expected workspace/user names.

---

## 24. Ownership Transfer — Full Flow (AE-84)

**What was built:** A safe, password-confirmed ownership transfer with audit logging and email notifications to both parties.

**Test steps:**
1. As Owner with at least one Member in the workspace: Settings → Members → click "Transfer Ownership"
2. A modal appears asking for **your current password** and the **new owner**
3. Try with wrong password → "Password is incorrect"
4. Try transferring to yourself → "Cannot transfer ownership to yourself"
5. Pick the member, enter correct password → submit
6. You should be demoted to "member", they become "owner"
7. Both of you receive emails (per #23 steps 5 & 6)
8. As the new owner, log in → confirm full owner permissions (see all sidebar items, can invite, etc.)
9. As the old owner, you can no longer access owner-only features (e.g. billing, delete workspace)

**Pass if:** Atomic role swap, both emails sent, audit log entry visible (if you have audit log UI), no orphan owner state.

---

## 25. Multi-Workspace Switcher (AE-85)

**What was built:** Users in multiple workspaces can switch between them via a sidebar dropdown.

**Test steps (you need ≥2 workspaces):**
1. Register a second workspace using a different email OR get yourself invited to one
2. Log in
3. Look in the top-left of the sidebar — there should be a workspace name with a chevron/dropdown
4. Click it — you should see a list of all workspaces you belong to with the current one highlighted
5. Click a different workspace
6. The page should reload showing **that** workspace's data (channels, members, content)
7. The URL doesn't need to change but the data should
8. Open DevTools → Application → Cookies → the active_workspace cookie should update

**Pass if:** Dropdown lists all workspaces, click switches context, data refreshes accordingly, no logout required.

---

## 26. Immediate Session Revocation (AE-86)

**What was built:** When a member is removed, their active browser session is immediately killed (within ~30 seconds, due to membership cache TTL).

**Test steps (you need two browsers):**
1. **Browser A:** Log in as Owner
2. **Browser B (incognito or different browser):** Log in as a Member of the same workspace
3. In Browser B, navigate around the dashboard normally — works fine
4. In Browser A, go to Settings → Members → click "Remove" on the Browser B user
5. In Browser B, do anything that triggers an API call (click a tab, refresh)
6. Within ~30 seconds, Browser B should:
   - Get a 403 "workspace_access_revoked" error
   - Be redirected to /login OR see a banner "You have been removed from this workspace"
7. Browser B's cookie/session should be cleared

**Pass if:** Removed user is kicked out within 30 seconds even if they were already logged in.

---

## 27. Provider Health Beat — 5-min Background Job (AE-75)

**What was built:** A background Temporal worker pings every provider's health endpoint every 5 minutes and updates the green/red dot in the Marketplace.

**Test steps:**
1. Go to /dashboard/providers
2. Note the colored status dots next to each provider card (green = healthy, red = down)
3. Open DevTools → Network → filter "health" — you should see periodic `/credentials/health` requests
4. Manually invalidate one provider's credential (e.g. paste a fake API key into LLM provider)
5. Wait ~5 minutes (or click "Run Health Check Now" if there's a button)
6. The dot should turn red and a "last health: failed" message should appear
7. Fix the credential → within 5 min, dot turns green again

**Pass if:** Health dots update automatically every 5 min. Bad credentials surface red. Fixed credentials recover.

---

## 28. User Management Page is Owner-Only (AE-278)

**What was fixed:** `/dashboard/users` and the user-management API used to be reachable by ANY logged-in user. It is now gated to Owner role only.

**Test steps:**
1. Log in as your **Owner** account → open https://dash.autoniix.com/dashboard/users — page loads, you see the platform user list.
2. Log out, log in as a **Member** (or Viewer) account.
3. In the browser address bar, type https://dash.autoniix.com/dashboard/users and hit enter.
4. You should be **blocked** — either redirected away, or shown "Not authorized" / 403. The user list must NOT render.
5. Open DevTools → Network. As the Member, directly call the user-management API: in the Console run
   ```js
   fetch('/api/v2/users', {credentials:'include'}).then(r=>console.log(r.status))
   ```
6. Expect **403** (not 200).

**Pass if:** Only Owner can open `/dashboard/users` and hit the user-management API. Members/Viewers get blocked in UI and 403 from the API.

---

## 29. Global Role Enforcement — Owner Checks Use Global Role (AE-279)

**What was fixed:** The JWT used to encode the *workspace* role, so `require_role("owner")` passed for anyone who owned *any* workspace. It now checks the **global platform role**.

**Test steps:**
1. Set up: have a user who is **Owner of their own workspace** but should NOT be a platform/global admin (a normal Member on the main workspace).
2. Log in as that user.
3. Try to access a global-admin-only action — e.g. open `/dashboard/users` (platform user list) or call a platform admin endpoint.
4. Open DevTools → Application → decode the JWT (or check `/api/v2/auth/me`) — the role used for global gates should reflect the **global** role, not "owner just because they own a workspace".
5. The global-admin action must be **denied** for this user.

**Pass if:** Owning a workspace does NOT grant platform-admin powers. Global gates only pass for true global admins.

---

## 30. Member Cannot Disable/Enable Platform Users (AE-280)

**What was fixed:** A Member used to be able to disable/enable any platform user (including the Owner). Only authorized admins can now toggle user accounts.

**Test steps:**
1. Log in as a **Member** account.
2. Open DevTools → Console and attempt to disable another user directly:
   ```js
   fetch('/api/v2/users/{SOME_USER_ID}/disable', {method:'POST', credentials:'include'}).then(r=>console.log(r.status))
   ```
   (replace `{SOME_USER_ID}` with any real user id, e.g. the Owner's).
3. Expect **403 Forbidden** — the call must be rejected.
4. If a disable/enable toggle is visible in the UI for a Member, it should be hidden or disabled.
5. Log in as **Owner/admin** → the same disable/enable action should succeed.

**Pass if:** Members get 403 when trying to disable/enable any user; only admins can toggle accounts; the Owner can never be disabled by a Member.

---

## 31. Registration Rate Limit (AE-281)

**What was fixed:** `POST /auth/register` had no rate limit — a script could create unlimited accounts and burn the email quota. It is now rate-limited.

**Test steps:**
1. Open DevTools → Console on https://dash.autoniix.com (or use a terminal with `curl`).
2. Fire several rapid registration attempts in a loop:
   ```js
   for (let i=0;i<15;i++){ fetch('/api/v2/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:`spam${i}@test.com`,password:'Xx12345!',name:'spam'})}).then(r=>console.log(i, r.status)); }
   ```
3. The first few may return 200/400, but after the threshold you should start seeing **429 Too Many Requests**.

**Pass if:** Rapid repeated registration calls get throttled with HTTP 429 after a small number of attempts.

---

## 32. Last Global Owner Protection (AE-282)

**What was fixed:** The sole global Owner could be demoted to Viewer, locking everyone out of admin. The system now blocks demoting the last global owner.

**Test steps:**
1. Ensure there is exactly **one** global Owner (you).
2. Go to the user/role management screen and try to change your own global role from Owner to Viewer/Member.
3. The action must be **blocked** with a message like "Cannot demote the last owner" / "At least one owner is required".
4. To confirm it's not a blanket block: add a second global Owner, then demoting the first one should now be allowed.

**Pass if:** The last/sole global owner cannot be demoted; demotion is only allowed when another owner exists.

---

## 33. Owner Cannot Self-Disable (AE-283)

**What was fixed:** An Owner could disable their own account, causing a permanent lockout. Self-disable is now blocked.

**Test steps:**
1. Log in as your **Owner** account.
2. Go to the user management screen, find your own row, and try to disable/deactivate yourself.
3. The action must be **blocked** with a clear error (e.g. "You cannot disable your own account").
4. Confirm via API too — in Console:
   ```js
   fetch('/api/v2/users/{YOUR_USER_ID}/disable',{method:'POST',credentials:'include'}).then(r=>console.log(r.status))
   ```
   Expect a 4xx error, not 200.

**Pass if:** An owner cannot disable their own account from the UI or the API.

---

## 34. Add-Credential Dialog No Longer Crashes (AE-288)

**What was fixed:** Opening the "Add credential" dialog used to crash with "Something went wrong — B.filter is not a function" because a JSON config column arrived as a raw string. The dialog now parses it correctly.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/providers
2. Pick **any** category, especially **Storage** (this was the worst offender): open it and click "Add credential" (or visit `/dashboard/providers/storage?add=1`).
3. The dialog should open and render the credential form fields normally.
4. Repeat for LLM, Voice/TTS, Search, Video categories.
5. There should be **no** "B.filter is not a function" error and the page should not go blank.

**Pass if:** The Add-credential dialog opens and renders fields for every category without crashing.

---

## 35. Approvals Drawer Clarity (AE-289)

**What was fixed:** The approvals drawer had a confusing blank section tile. It now shows clear, labelled content.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard (or wherever the approvals/notifications drawer lives — usually a bell icon or side drawer).
2. Open the **Approvals** drawer.
3. Confirm there is **no blank/empty tile** — every section has a clear heading and, when empty, a friendly empty state (e.g. "No pending approvals").
4. If there are pending approvals, each item should be clearly labelled (what needs approving, by whom, when).

**Pass if:** The approvals drawer is readable with no confusing blank tiles; empty states are explained.

---

## 36. Duplicate Pending Invites Blocked (AE-208 / AE-262)

**What was fixed:** The same email could be invited multiple times, creating duplicate pending invites. There is now a uniqueness check on (workspace, email).

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/settings → Members tab.
2. Invite a new email, e.g. `dupe-test@example.com` → it appears in the pending list.
3. Try inviting the **exact same email again** while the first invite is still pending.
4. The second attempt should be **rejected** with a clear message (e.g. "This email already has a pending invite").
5. Confirm the pending list shows only **one** entry for that email.

**Pass if:** A second invite to an already-pending email is blocked; no duplicate pending rows are created.

---

## 37. Pending Invites Don't Pre-Consume Plan Slots (AE-209)

**What was fixed:** Pending (unaccepted) invitations used to count against your plan's member limit, so one email could fill all slots. Slots are now only consumed on acceptance (per the agreed rule — verify against the ticket).

**Test steps:**
1. Note your plan's member limit (e.g. Starter = 3) and your current member count.
2. Send invites to fill up toward the limit but **don't** have them accepted yet.
3. Confirm the counting behaviour matches the fixed rule: a pending invite should not unfairly block legitimate capacity (e.g. inviting one person shouldn't lock out all remaining slots).
4. Cancel a pending invite → the slot should free up immediately if it was reserved.

**Pass if:** Member-limit accounting for pending invites matches the corrected behaviour and a single pending invite cannot consume all slots.

---

## 38. Trigger a Manual Production Run (AE-46 / AE-159)

**What was built:** From the dashboard you can manually kick off a video production run for a channel.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/channels and open a channel that has providers + a YouTube account connected.
2. Find the **"Run now" / "Generate video" / "Trigger production"** button.
3. Click it → you should see a confirmation and a new run/job appear (status "running" / "queued").
4. Go to the Jobs page (#42 below) — the new run should be listed with a live status.

**Pass if:** Manual trigger starts a real run that shows up in Jobs with a progress status.

---

## 39. Video Pipeline Stages — End to End (AE-35–AE-42 / AE-125–AE-143)

**What was built:** The full pipeline: Research → Script → Voice → Thumbnail → Asset sourcing → Assembly → Delivery to YouTube.

**Test steps (watch one run progress through every stage):**
1. Trigger a run (from #38). Open the run's detail/Jobs view.
2. **Research (AE-35):** stage produces topic candidates — confirm a chosen topic appears.
3. **Script (AE-36):** a formatted script is generated for that topic.
4. **Voice (AE-37):** a clean audio file is produced (you can play it).
5. **Thumbnail (AE-38):** a thumbnail image is generated.
6. **Asset sourcing (AE-39):** B-roll / images are found and ranked.
7. **Assembly (AE-40):** audio + assets + thumbnail combine into an MP4 (preview/download available).
8. **Delivery (AE-41):** the video uploads to YouTube with SEO title/description/tags.
9. **Full E2E (AE-42):** the run completes end-to-end with **no errored stage**.

**Pass if:** Each stage produces its expected artifact and the run reaches "completed" with a delivered video. Note any stage that errors and file a bug.

---

## 40. Music Selection + Beat Analysis (AE-66 / AE-146)

**What was built:** The pipeline selects a music track and produces a beat grid so cuts can sync to the beat.

**Test steps:**
1. On a completed run, open the assembly/music details.
2. Confirm a **music track was selected** and attached to the video.
3. Confirm a **beat grid / timing data** exists (visible in run metadata or logs).
4. Watch the output — cuts/transitions should feel aligned to the music rhythm.

**Pass if:** A track is selected and a beat grid is produced; the final video has background music synced reasonably to beats.

---

## 41. Cold Open + Intro/Outro Variants (AE-67 / AE-148)

**What was built:** Netflix-style cinematic structure — a cold open plus intro/outro variants selected by a bandit algorithm.

**Test steps:**
1. On a completed video, watch the first ~10 seconds — there should be a **cold open** hook before the intro.
2. Confirm an **intro** and **outro** segment are present.
3. Across multiple runs, the chosen intro/outro **variant** should vary (bandit selection) — check run metadata for the variant id picked.

**Pass if:** Videos open with a cold-open hook, include intro/outro, and variant selection is recorded per run.

---

## 42. Human Review System — Pause-Per-Stage Approval (AE-47 / AE-68 / AE-150 / AE-160)

**What was built:** Production can pause at configured stages for human approval before continuing; multi-level approval chain; approve/reject a generated video before delivery.

**Test steps:**
1. On a channel, enable review/approval gates (if there's a setting) for at least one stage (e.g. script or final video).
2. Trigger a run → it should **pause** at the gated stage and show up as "awaiting approval".
3. Go to the review/approvals area → open the artifact (script or video) and **Reject** it → the run should stop / not deliver.
4. Trigger again, this time **Approve** → the run should continue past the gate to delivery.
5. Confirm approve/reject actions are recorded (who, when).

**Pass if:** Runs pause at gated stages, reject halts delivery, approve resumes, and decisions are logged.

---

## 43. Budget Cap + Cost Tracking (AE-69 / AE-152)

**What was built:** Per-run hard kill on budget overrun, a monthly per-channel cap, and cost reporting.

**Test steps:**
1. Open a channel's settings → find **Budget / Cost** controls. Set a low monthly cap and/or per-run cap for testing.
2. Trigger runs and watch the **cost accumulate** in the cost report.
3. When a run would exceed the per-run cap, it should be **hard-killed** with a clear "budget exceeded" status.
4. When the monthly cap is hit, further runs for that channel should be blocked until reset.

**Pass if:** Costs are tracked per run/channel, per-run overruns are killed, and the monthly cap blocks new runs.

---

## 44. Production Scheduling + Weekly Quota (AE-70 / AE-154)

**What was built:** Per-channel cron schedule, weekly quota enforcement, and a schedule settings UI.

**Test steps:**
1. Open a channel → **Schedule** settings.
2. Set a posting schedule (e.g. cron or "X videos/week") and a weekly quota.
3. Confirm the schedule saves and shows the next scheduled run time.
4. Confirm that once the weekly quota is reached, additional scheduled runs are **not** triggered that week.

**Pass if:** Schedule saves, next-run time shows, and quota enforcement caps weekly production.

---

## 45. Create Workspace & Brand (AE-43 / AE-156)

**What was built:** Create a workspace and define its brand from the dashboard.

**Test steps:**
1. Go to workspace settings (or onboarding) → create/confirm a workspace name.
2. Define brand basics (name, description, niche).
3. Save → reload → the workspace + brand details persist.

**Pass if:** A workspace with brand details can be created and persists across reloads.

---

## 46. Configure Brand DNA for a Channel (AE-45 / AE-158)

**What was built:** Per-channel "Brand DNA" — voice style, content guidelines, niche templates that steer generation.

**Test steps:**
1. Open a channel → **Brand DNA** (or Brand/Style) settings.
2. Set voice style (e.g. "energetic, concise"), content guidelines, and pick a niche template.
3. Save → reload → settings persist.
4. Trigger a run → the generated script/voice should reflect the configured style (spot-check tone).

**Pass if:** Brand DNA saves, persists, and visibly influences generated content.

---

## 47. Video Library (AE-54 / AE-167)

**What was built:** Produced videos appear in a Library with correct metadata.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/library
2. Completed videos should be listed with thumbnail, title, status, duration, and date.
3. Click a video → detail view shows full metadata (description, tags, channel, run link).

**Pass if:** Produced videos appear with accurate metadata and a working detail view.

---

## 48. Content Calendar (AE-55 / AE-168)

**What was built:** A calendar showing scheduled and published videos.

**Test steps:**
1. Go to the **Calendar** view in the dashboard.
2. Scheduled videos appear on their planned dates; published videos appear on their publish dates (visually distinct).
3. Navigate months → data loads correctly for each.

**Pass if:** Calendar shows both scheduled and published items on the correct dates.

---

## 49. Quality Gate Scores Scripts (AE-56 / AE-169)

**What was built:** A quality gate scores scripts and blocks low-quality content from proceeding.

**Test steps:**
1. Trigger a run and open the **Quality** details for the script stage.
2. A quality score should be shown for the script.
3. Confirm that a script scoring below the threshold is **blocked** (run stops or regenerates) rather than proceeding to delivery.

**Pass if:** Scripts get scored and low-scoring scripts are blocked/regenerated, not delivered.

---

## 50. Diversity Floor — No Near-Duplicate Topics (AE-57 / AE-170)

**What was built:** A diversity floor blocks near-duplicate topics within a 30-day window.

**Test steps:**
1. Look at recent topics/videos for a channel.
2. Trigger research and confirm the chosen topic is **not** a near-duplicate of one produced in the last 30 days.
3. If you force a duplicate-ish topic, the system should reject/replace it.

**Pass if:** Recently-used topics are not repeated within 30 days; near-duplicates get blocked.

---

## 51. Fleet Health Page (AE-58 / AE-171)

**What was built:** A page showing all ~8 services and worker status.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard (Fleet health / System health page).
2. All core services should be listed (gateway, dashboard API, worker(s), Temporal, Postgres, Redis, etc.) with a green/healthy status.
3. Worker status should show active workers.

**Pass if:** Every service is listed with an accurate health status.

---

## 52. Jobs Page with Log Access (AE-59 / AE-172)

**What was built:** A Jobs page listing production runs with status, duration, and log access.

**Test steps:**
1. Go to the **Jobs** page.
2. Recent runs are listed with status (running/completed/failed), duration, and channel.
3. Click a job → you can view its **logs** / stage timeline.

**Pass if:** Jobs list shows status + duration and you can open logs for any run.

---

## 53. Real-Time Notifications (AE-60 / AE-173)

**What was built:** A notifications page/drawer showing system events in real time.

**Test steps:**
1. Open the **Notifications** drawer/page.
2. Trigger an event (start a run, invite a member) → a notification should appear **without a manual refresh** (within a few seconds).
3. Notifications show clear text + timestamp.

**Pass if:** New events surface in near-real-time with readable content.

---

## 54. Analytics Retention Curves (AE-61 / AE-187)

**What was built:** Analytics ingestion produces retention curves for published videos.

**Test steps:**
1. Go to the **Analytics** area for a published video (requires `yt-analytics.readonly` scope — see #57).
2. A **retention curve** chart should render for the video.
3. Numbers should look plausible (not all-zero) for videos with watch data.

**Pass if:** Retention curves render for published videos with real data.

---

## 55. NichePulse Daily Trends (AE-62 / AE-188)

**What was built:** NichePulse runs daily and updates topic opportunity scores.

**Test steps:**
1. Open the **NichePulse / Trends** section.
2. Topic opportunity scores are shown and have a recent "last updated" timestamp (within ~24h).
3. Scores differ across topics (not flat/placeholder).

**Pass if:** NichePulse shows recently-updated, varied opportunity scores.

---

## 56. A/B Experiment Tracking + Pattern Miner (AE-63 / AE-189 / AE-64 / AE-190)

**What was built:** Create an A/B variant and track results across runs; a pattern miner surfaces winning content attributes after 10+ videos.

**Test steps:**
1. Open the **Experiments / A/B** area → create a variant (e.g. two thumbnail or title styles).
2. Confirm the experiment is tracked and results accumulate across runs.
3. For a channel with 10+ videos, open **Pattern miner / Insights** → it should surface winning attributes (e.g. "titles with numbers perform better").

**Pass if:** A/B experiments can be created and tracked; pattern miner shows insights once enough videos exist.

---

## 57. OAuth Analytics Scope + YouTube Connect (AE-52 / AE-165 / AE-44 / AE-157)

**What was built:** The Google OAuth client requests `yt-analytics.readonly`; you can add a YouTube channel via OAuth credential.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/providers → Accounts → Connect YouTube.
2. On the Google consent screen, confirm the requested scopes include **YouTube Analytics (read-only)** in addition to upload.
3. After connecting, the channel appears and analytics (#54) become available.

**Pass if:** OAuth consent includes the analytics scope and the connected channel powers the analytics views.

---

## 58. Infra / Deploy Ops Checks (AE-161 / AE-162 / AE-163 / AE-164)

**What was built:** Full-stack VPS deploy, DB migrations applied, 5 Temporal schedules registered, and a production smoke test. These are **ops-level** checks rather than click-through UI tests.

**Test steps:**
1. **Deploy (AE-161):** https://dash.autoniix.com loads over HTTPS with a valid cert and no 5xx.
2. **Migrations (AE-162):** the app runs with no "missing column/table" errors; new features (providers, workspaces) work — implies migrations are applied.
3. **Schedules (AE-163):** in the schedule UI (or Temporal), confirm the expected production schedules are registered and have a next-run time.
4. **Smoke test (AE-164):** core flows (login, load dashboard, open providers, trigger a run) all succeed end-to-end.

**Pass if:** Production is reachable, migrations are clearly applied, schedules are registered, and the core smoke path works.

---

## 59. Finishing Pipeline — LUT Colour Grade + Audio Mastering (AE-294 / AE-296)

**What was built:** Every produced video passes through a `finishing_activity` Temporal stage between assembly and delivery. It applies a per-channel LUT colour grade (one of 7 cinematic presets) plus a full audio mastering chain (denoise → EQ → compress → music duck → loudnorm -14 LUFS → true peak -1.5 dBTP).

**Test steps:**
1. Open a channel → click the **Finishing** tab in channel settings.
2. Confirm the `channel_finishing_config` row was seeded for this channel — the tab should load with a default preset (`cinematic`) and all audio toggles on.
3. Select a different preset (e.g. `warm_gold`) and save.
4. Trigger a production run. Watch the job progress — after Assembly you should see a **Finishing** stage appear.
5. On the completed job detail page, look for a **finishing badge** (e.g. `🎨 warm_gold`) — confirms the finishing stage ran.
6. If the finishing stage was skipped (service unavailable), an amber **`⚠ Colour grade skipped`** warning badge should appear instead.
7. Check audio quality: narration track should be consistent and clean — no sudden volume spikes or overly quiet segments.

**Pass if:** Finishing stage appears in the job timeline, badge shows the correct preset, skipped finishing shows the amber warning, audio sounds broadcast-level.

---

## 60. Finishing Settings UI — Colour Grade Preset Picker + Audio Controls (AE-297)

**What was built:** A new **Finishing** tab in channel settings for configuring per-channel colour grade preset and audio mastering options.

**Test steps:**
1. Go to https://dash.autoniix.com/dashboard/channels → open any channel → click the **Finishing** tab.
2. Confirm a grid of **7 colour grade preset cards** renders: Cinematic, Clean & Bright, Warm Gold, Cool Blue, Vintage, Documentary, Neon Dark. Each card shows name + description.
3. Click a different preset card — it should show a highlighted ring + checkmark.
4. Click **Save** → success toast appears. Reload the page — the selected preset should persist.
5. Under **Audio Mastering**, confirm 4 toggle switches exist: Denoise, EQ, Compress, Music Duck.
6. Confirm 2 numeric inputs: **Loudness Target** and **True Peak Ceiling**.
7. Turn off one toggle, save, reload — the toggle should remain off.
8. Enter an out-of-range loudness value (e.g. `-50` or `0`) — the Save button should disable with a red inline validation error.
9. Log in as a **Viewer** and open the same Finishing tab — controls should be read-only (no Save button or save is disabled).

**Pass if:** All 7 preset cards render, selection persists on save, toggles + numerics work, invalid loudness shows inline error, Viewer cannot edit.

---

## 61. Review Gate Config — Per-Channel Review Settings (AE-229 / AE-241 / AE-242 / AE-243)

**What was built:** Channels now have a `review_config` JSONB column storing which pipeline artifacts need human approval before proceeding. Five built-in profiles exist (Hands Off, Quick, Standard, Full Control, Custom). A new **Review** tab in channel settings lets you manage this.

**Test steps:**
1. Go to a channel → look for a **Review** tab — click it.
2. Confirm a **profile selector** shows at least: Hands Off, Quick, Standard, Full Control, Custom.
3. Select **Standard** → 5 gate toggles should auto-enable (e.g. script, voice, thumbnail, assembly, final video).
4. Select **Hands Off** → all gate toggles should turn off (pipeline runs fully automated).
5. Select **Full Control** → all gates should enable.
6. With **Standard** selected, manually toggle off one gate — the profile label should automatically switch to **Custom**.
7. Click **Save** → success toast. Reload — the correct profile and gate states persist.
8. Log in as a **Viewer** → open the Review tab → controls should be read-only; no Save button visible or it's disabled.
9. **API check (optional):** In DevTools Console:
   ```js
   fetch('/api/v2/channels/YOUR_CHANNEL_ID/settings/review', {credentials:'include'}).then(r=>r.json()).then(console.log)
   ```
   Should return `{"profile":"...", "gates":{...}}`.

**Pass if:** Profile selector correctly populates gate toggles, manual override sets profile to Custom, settings persist on reload, Viewer is blocked, API returns correct JSON.

---

## 62. resolve-finisher Service — Health Check (AE-295)

**What was built:** A new `resolve-finisher` Docker service (Phase 1B scaffold) wired into the compose stack on port 8014. Currently a stub — it accepts job submissions and marks them complete immediately. The full DaVinci Resolve integration ships in Phase 1B.

**Test steps (ops-level — requires VPS/server access):**
1. Run: `docker compose ps resolve-finisher` — should be listed as **Up (healthy)**.
2. Run: `curl http://localhost:8014/health` — should return `{"status": "ok", "resolve_connected": false}` (false = stub mode, DaVinci not installed yet).
3. Submit a stub job:
   ```sh
   curl -s -X POST http://localhost:8014/finish \
     -H "Content-Type: application/json" \
     -d '{"job_id":"qa-test-1","input_path":"/tmp/test.mp4","preset":"cinematic"}'
   ```
   Should return a `job_id` and status `queued` or `completed`.
4. Check the Fleet Health page (`#51`) — `resolve-finisher` should appear in the service list as healthy.

**Pass if:** Service is running healthy in Docker, `/health` returns `ok`, stub job submission is accepted without error. `resolve_connected: false` is **expected** until Phase 1B lands.

---

## COMPLETE IN-PROD COVERAGE MAP

Every ticket currently in **In Prod** status maps to a test section above. Duplicate engineering/test-task mirrors point to the same section as their feature.

### Providers & credentials
| Ticket | Feature | Section |
|--------|---------|---------|
| AE-263 | Background API call fix | #1 |
| AE-117/AE-174/AE-201/AE-202/AE-71/AE-72 | Provider marketplace & catalog | #6 |
| AE-195/AE-29 | LLM credentials | #7 |
| AE-196/AE-30 | TTS/Voice credentials | #8 |
| AE-117/AE-197/AE-31 | SerpAPI credentials | #9 |
| AE-119/AE-198/AE-32 | MinIO storage | #10 |
| AE-122/AE-199/AE-33 | YouTube OAuth | #11 |
| AE-175/AE-203/AE-73 | Provider chain editor | #12 |
| AE-176/AE-204/AE-74 | Test vs Prod chains | #13 |
| AE-177/AE-200/AE-205/AE-34/AE-75 | Provider health + 5-min beat | #14, #27 |
| AE-178/AE-206/AE-76 | Change request workflow | #15 |
| AE-179/AE-207/AE-77 | Credential rotation | #16 |
| AE-288 | Add-credential dialog crash fix | #34 |

### Workspace, auth & roles
| Ticket | Feature | Section |
|--------|---------|---------|
| AE-264 | Invite-only registration | #2 |
| AE-93/AE-182/AE-277 | Plan limit enforcement | #3 |
| AE-94/AE-183/AE-24 | Ownership transfer protection | #4 |
| AE-95/AE-184/AE-25 | Slack webhook notifications | #5 |
| AE-227 | 3-role preset consolidation | #18 |
| AE-80 | Open Registration | #19 |
| AE-81 | Onboarding Wizard | #20 |
| AE-78 | Named Permission System | #21 |
| AE-79 | Role-Based UI Navigation | #22 |
| AE-83 | Transactional Email — 8 templates | #23 |
| AE-84 | Ownership Transfer — Full Flow | #24 |
| AE-85 | Multi-Workspace Switcher | #25 |
| AE-86 | Immediate Session Revocation | #26 |
| AE-278 | User-management page Owner-only | #28 |
| AE-279 | Global role enforcement | #29 |
| AE-280 | Member cannot disable users | #30 |
| AE-281 | Registration rate limit | #31 |
| AE-282 | Last global owner protection | #32 |
| AE-283 | Owner cannot self-disable | #33 |
| AE-289 | Approvals drawer clarity | #35 |
| AE-208/AE-262 | Duplicate pending invites blocked | #36 |
| AE-209 | Pending invites & plan slots | #37 |

### Finishing pipeline
| Ticket | Feature | Section |
|--------|---------|------|
| AE-293 | Finishing pipeline epic | (epic — no test needed) |
| AE-294 | Phase 1A ffmpeg finishing activity | #59 |
| AE-296 | Channel Finishing Settings API + DB | #59 |
| AE-297 | Dashboard Finishing Settings UI | #60 |
| AE-295 | Phase 1B resolve-finisher scaffold | #62 |

### Review gate config
| Ticket | Feature | Section |
|--------|---------|------|
| AE-229 | `channels.review_config` JSONB + API CRUD | #61 |
| AE-241 | review_config migration subtask | #61 |
| AE-242 | review-config API endpoints subtask | #61 |
| AE-243 | review_config unit + API tests subtask | #61 |

### Channels & video pipeline
| Ticket | Feature | Section |
|--------|---------|---------|
| AE-218/AE-219 | YouTube-only platform lock | #17 |
| AE-43/AE-156 | Create workspace & brand | #45 |
| AE-44/AE-157 | Add YouTube channel (OAuth) | #57, #11 |
| AE-45/AE-158 | Brand DNA config | #46 |
| AE-46/AE-159 | Manual production run | #38 |
| AE-35/AE-125 | Research stage | #39 |
| AE-36/AE-128 | Script generation | #39 |
| AE-37/AE-131 | Voice synthesis | #39 |
| AE-38/AE-133 | Thumbnail generation | #39 |
| AE-39/AE-136 | Asset sourcing | #39 |
| AE-40/AE-138 | Video assembly | #39 |
| AE-41/AE-141 | Delivery to YouTube | #39 |
| AE-42/AE-143 | Full E2E pipeline run | #39 |
| AE-66/AE-146 | Music selection + beat analysis | #40 |
| AE-67/AE-148 | Cold open + intro/outro variants | #41 |
| AE-47/AE-68/AE-150/AE-160 | Human review / approve-reject | #42 |
| AE-69/AE-152 | Budget cap + cost tracking | #43 |
| AE-70/AE-154 | Scheduling + weekly quota | #44 |

### Content, intelligence & dashboard
| Ticket | Feature | Section |
|--------|---------|---------|
| AE-54/AE-167 | Video library | #47 |
| AE-55/AE-168 | Content calendar | #48 |
| AE-56/AE-169 | Quality gate scores scripts | #49 |
| AE-57/AE-170 | Diversity floor | #50 |
| AE-58/AE-171 | Fleet health page | #51 |
| AE-59/AE-172 | Jobs page + logs | #52 |
| AE-60/AE-173 | Real-time notifications | #53 |
| AE-61/AE-187 | Analytics retention curves | #54 |
| AE-62/AE-188 | NichePulse daily trends | #55 |
| AE-63/AE-189 | A/B experiment tracking | #56 |
| AE-64/AE-190 | Pattern miner | #56 |

### Infrastructure & deploy
| Ticket | Feature | Section |
|--------|---------|---------|
| AE-52/AE-165 | OAuth yt-analytics scope | #57 |
| AE-161 | VPS full-stack deploy | #58 |
| AE-162 | DB migrations applied | #58 |
| AE-163 | Temporal schedules registered | #58 |
| AE-164 | Production smoke test | #58 |

> **Epics** (AE-7, AE-10, AE-11, AE-12, AE-13, AE-14, AE-15, AE-16, AE-17) are containers — they close automatically when all their child stories above are verified. No separate test needed.

---

## HOW TO MARK TICKETS VERIFIED

Once you've tested a section and it passes on production, mark the ticket verified in one shot:
```
verified #<GH-issue-number>
```
or verify everything currently In-Prod at once:
```
verified all
```
This auto-ticks the acceptance criteria, adds `prod-verified`, and closes the issue.
