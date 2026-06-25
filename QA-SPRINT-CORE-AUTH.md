# QA Test Plan — Sprint: core-auth
**Tickets:** IM-39, IM-40, IM-41, IM-42, IM-43, IM-178, IM-179, IM-180, IM-181, IM-182, IM-183  
**Branch:** `develop` — delete this file once all items are checked ✅

---

## IM-39 — Login Page (UI, form validation, error states)

### Happy Path
- [ ] **H1** — Valid email + password → user lands on `/dashboard`
- [ ] **H2** — Valid email + password when `setup_required` → user lands on `/onboarding`
- [ ] **H3** — Legacy mode enabled → password-only form shown (no email field)
- [ ] **H4** — MFA-enabled user → after credentials step, MFA code step appears inline

### Sad / Error Path
- [ ] **S1** — Wrong password → `401` error shown inline, no redirect
- [ ] **S2** — Non-existent email → `401` (same generic message, no email enumeration)
- [ ] **S3** — Empty email → form validation blocks submit
- [ ] **S4** — Invalid email format → form validation blocks submit
- [ ] **S5** — Empty password → form validation blocks submit

### Edge Cases
- [ ] **E1** — Already logged-in user visits `/login` → redirected to `/dashboard`
- [ ] **E2** — "Forgot password?" link visible and navigates to `/forgot-password`
- [ ] **E3** — "No account? Create one" link visible and navigates to `/register`
- [ ] **E4** — `?reason=no_workspace_access` query param → specific error banner shown

---

## IM-40 — Register Page (UI, form validation, workspace creation flow)

### Happy Path
- [ ] **H1** — Valid name, email, password, workspace name → account created, lands on `/onboarding`
- [ ] **H2** — Display name pre-populated from `display_name` if provided

### Sad / Error Path
- [ ] **S1** — Duplicate email → `409` error shown
- [ ] **S2** — Password < 8 chars → form validation blocks submit
- [ ] **S3** — Password ≠ confirm password → mismatch error shown
- [ ] **S4** — Empty workspace name → form validation blocks submit
- [ ] **S5** — Name < 2 chars → form validation blocks submit

### Edge Cases
- [ ] **E1** — Already logged-in user visits `/register` → redirected to `/dashboard`
- [ ] **E2** — Special characters in workspace name (e.g. `O'Brien & Co.`) → accepted

---

## IM-41 — Forgot Password + Reset Password Flow

### Happy Path
- [ ] **H1** — Enter valid email → success message shown (no indication if user exists)
- [ ] **H2** — Click reset link from email → lands on reset password page with token in URL
- [ ] **H3** — Enter valid new password (≥8 chars) + confirm → password changed, redirected to login

### Sad / Error Path
- [ ] **S1** — Invalid/expired reset token → `400` error shown
- [ ] **S2** — New password < 8 chars → form validation blocks submit
- [ ] **S3** — New password ≠ confirm → mismatch error shown
- [ ] **S4** — Non-existent email on forgot page → same success message (no enumeration)
- [ ] **S5** — Reuse expired reset link (used once already) → `400`

### Edge Cases
- [ ] **E1** — Reset link used → login with new password works
- [ ] **E2** — Old password no longer works after reset

---

## IM-42 — Accept Invite Flow (token validation + workspace join)

### Happy Path
- [ ] **H1** — Valid invite token for new user → set-password form shown → after submit, user is workspace member, lands on `/dashboard`
- [ ] **H2** — Valid invite token for existing user (already has account) → skips password step, joins workspace
- [ ] **H3** — Accepted invite → correct workspace role assigned (member/viewer per invite)

### Sad / Error Path
- [ ] **S1** — Expired invite token → `410 Gone` error shown
- [ ] **S2** — Already-used invite token → `409` error shown
- [ ] **S3** — Tampered/invalid token → `400` or `404`
- [ ] **S4** — Password < 8 chars (new user) → form validation blocks submit
- [ ] **S5** — Password ≠ confirm → mismatch error

### Edge Cases
- [ ] **E1** — Invite to a workspace that is `pending_deletion` → should show appropriate error (workspace unavailable)
- [ ] **E2** — Rate limit: >5 accept-invite attempts in 1 min from same IP → `429`

---

## IM-43 — Onboarding Wizard (workspace name, logo, timezone)

### Happy Path
- [ ] **H1** — Fresh user after register → `/onboarding` shown
- [ ] **H2** — Fill workspace name → saved, visible in workspace switcher after
- [ ] **H3** — Complete all onboarding steps → `onboarding_completed = true`, redirected to `/dashboard`

### Sad / Error Path
- [ ] **S1** — Skip workspace name (empty) → form validation blocks progression
- [ ] **S2** — Already-completed onboarding user visits `/onboarding` → redirected to `/dashboard`

### Edge Cases
- [ ] **E1** — Reload mid-onboarding → current step preserved (or starts from beginning — document expected behaviour)
- [ ] **E2** — Back-navigation between steps works without state loss

---

## IM-179 — Onboarding Completion Verification + `needs_workspace_setup` Redirect

### Happy Path
- [ ] **H1** — User with `needs_workspace_setup = true` (force-deleted workspace) → redirected to onboarding on login
- [ ] **H2** — After completing onboarding, `needs_workspace_setup = false` in DB
- [ ] **H3** — `WorkspaceGuard` component: user with no workspaces → redirected to onboarding

### Sad / Error Path
- [ ] **S1** — User with `needs_workspace_setup = true` tries to access `/dashboard` directly → redirected
- [ ] **S2** — Middleware blocks dashboard access for users with no workspace

### Edge Cases
- [ ] **E1** — User invited to a workspace while `needs_workspace_setup = true` → accepting invite clears flag, redirects to dashboard

---

## IM-180 — DELETE /workspaces/{id} Cascade Endpoint

### Happy Path
- [ ] **H1** — Owner calls `DELETE /api/v2/workspaces/:id` → soft-delete initiated, `200 {status:"pending_deletion"}`
- [ ] **H2** — Response includes `grace_days` (default 7)
- [ ] **H3** — After soft-delete: `GET /api/v2/workspaces/:id/deletion-status` → shows `pending_deletion` + scheduled date
- [ ] **H4** — Superadmin can delete any workspace

### Sad / Error Path
- [ ] **S1** — Non-owner member tries to delete → `403`
- [ ] **S2** — Unauthenticated request → `401`
- [ ] **S3** — Workspace already `pending_deletion` → `409`
- [ ] **S4** — Non-existent workspace ID → `404`

### Edge Cases
- [ ] **E1** — `WORKSPACE_DELETION_GRACE_DAYS` env var overrides default → verify `delete_scheduled_at` reflects the override
- [ ] **E2** — All active invitations suspended on soft-delete (check `workspace_invitations.suspended_at` set)
- [ ] **E3** — All active sessions for workspace members revoked on soft-delete

---

## IM-181 — Workspace Soft-Delete + 7-Day Grace Period + Hard-Delete Pipeline

### Happy Path
- [ ] **H1** — Soft-deleted workspace: `deleted_at` set, `status = pending_deletion`, `delete_scheduled_at = NOW() + 7 days`
- [ ] **H2** — Cancel deletion within grace period → `200 {status:"active"}`, `deleted_at` cleared, invitations un-suspended
- [ ] **H3** — Hard-delete cron runs after `delete_scheduled_at` passes → workspace + all FK-dependent data deleted
- [ ] **H4** — `GET /api/v2/workspaces/:id/deletion-status` returns correct state at each stage

### Sad / Error Path
- [ ] **S1** — Cancel deletion after grace period expires → `410 Gone`
- [ ] **S2** — Cancel deletion on workspace not in `pending_deletion` → `422`
- [ ] **S3** — Non-owner tries to cancel → `403`
- [ ] **S4** — Hard-delete on workspace not yet past `delete_scheduled_at` → cron skips it

### Edge Cases
- [ ] **E1** — Grace period = 0 days (env override) → `delete_scheduled_at` is today; cron runs next tick and hard-deletes
- [ ] **E2** — Workspace has channels, members, invitations, sessions — verify all cascade-deleted cleanly (no FK orphan errors)
- [ ] **E3** — Hard-delete cron logs workspace ID and outcome on each run (check application logs)

---

## IM-183 — Orphaned User Protection on Workspace Deletion

### Happy Path
- [ ] **H1** — Owner with 2+ workspaces can delete one → `200 {status:"pending_deletion"}` returned
- [ ] **H2** — Superadmin can delete owner's only workspace with `?force=true` → `200 {status:"pending_deletion", last_workspace:true}`
- [ ] **H3** — After force-delete, owner's `needs_workspace_setup` column is `true` in DB

### Sad / Error Path
- [ ] **S1** — Owner deletes their only workspace (no `?force`) → `400 {error:"last_workspace_deletion"}`
- [ ] **S2** — Superadmin deletes owner's only workspace without `?force=true` → `400` with message prompting `?force=true`
- [ ] **S3** — Non-owner member tries to delete workspace → `403`
- [ ] **S4** — Delete already-pending workspace → `409 "Workspace is already pending deletion"`
- [ ] **S5** — Delete non-existent workspace ID → `404`
- [ ] **S6** — Unauthenticated request → `401`

### Edge Cases
- [ ] **E1** — Owner has exactly 2 workspaces; deletes one → allowed (remaining count = 1 after delete, but at delete-time count is 1 remaining ≠ 0 so should allow)
- [ ] **E2** — Owner's workspace count is computed live (soft-deleted workspaces excluded) — create + soft-delete a workspace first, then check the count guard
- [ ] **E3** — Race condition: two concurrent delete requests for the same workspace → only one succeeds with 200, second gets 409

---

## IM-182 — Email Notifications on Workspace Deletion

### Happy Path
- [ ] **H1** — Soft-delete a workspace → within ~60s, `workspace_deletion_notifications` table has a row with `event='soft_delete'` for every active member
- [ ] **H2** — Cancel deletion → `workspace_deletion_notifications` row inserted with `event='cancelled'`
- [ ] **H3** — 48h warning cron fires for workspaces with `delete_scheduled_at` between 47–48 hours away → `event='warning_48h'` rows inserted

### Sad / Error Path
- [ ] **S1** — Workspace has a member with `NULL` email → row skipped (no crash), warning logged
- [ ] **S2** — Resend API key not set in env → email send fails gracefully (fire-and-forget, does NOT block the delete or cancel HTTP response)
- [ ] **S3** — Resend returns `4xx` → error logged, idempotency row still not written (so retry will attempt again)

### Edge Cases / Idempotency
- [ ] **E1** — Trigger soft-delete twice (second blocked by 409) → only one set of notification rows exists (no duplicates)
- [ ] **E2** — Cancel and immediately re-delete → two separate notification events recorded correctly
- [ ] **E3** — Workspace with 0 members (owner only, `workspace_members` has 1 row) → only owner notified
- [ ] **E4** — Workspace with >500 members (simulate by checking batch-chunking logic) → emails batched in 100s, 1s delay between batches, no OOM

### API Contract
- [ ] **A1** — `DELETE /api/v2/workspaces/:id` still returns before emails are sent (fire-and-forget — response time < 500ms under normal conditions)
- [ ] **A2** — `POST /api/v2/workspaces/:id/cancel-deletion` same — response not blocked by email

---

## IM-178 — MFA Frontend UI

### Login Challenge Flow

#### Happy Path
- [ ] **H1** — MFA-disabled user logs in → goes straight to `/dashboard` (no MFA step)
- [ ] **H2** — MFA-enabled user logs in with correct credentials → redirected to inline MFA step (not dashboard)
- [ ] **H3** — MFA-enabled user enters correct 6-digit TOTP → logs in successfully, lands on `/dashboard`
- [ ] **H4** — MFA step shows "← Back" button → clicking it returns to credentials step

#### Sad / Error Path
- [ ] **S1** — MFA-enabled user enters wrong TOTP code → inline error message shown, not redirected
- [ ] **S2** — MFA-enabled user enters expired TOTP (>30s old) → `401` from backend, error shown clearly
- [ ] **S3** — `mfa_pending_token` expires (5 min) before user enters code → `401` shown, must restart login
- [ ] **S4** — MFA step submitted with empty/partial code (< 6 digits) → form validation blocks submission

#### Edge Cases
- [ ] **E1** — Reload page mid-MFA-step → back to credentials step (token state lost, must re-enter credentials)
- [ ] **E2** — Legacy-mode login (legacy auth enabled) → MFA step never appears (legacy path bypasses it)

---

### Profile Page — Enable MFA

#### Happy Path
- [ ] **H1** — Navigate to `/dashboard/profile` → MFA section shows status badge "Disabled"
- [ ] **H2** — Click "Enable MFA" → "Generate QR code" button appears
- [ ] **H3** — Click "Generate QR code" → QR code image loads, backup secret text shown below it
- [ ] **H4** — Scan QR with authenticator app → enter correct code → "Activate MFA" → success toast, badge flips to "Enabled"
- [ ] **H5** — After enabling, page shows "Disable MFA" button (not "Enable MFA")

#### Sad / Error Path
- [ ] **S1** — Enter wrong TOTP during setup verify → inline error "Invalid code — try again", QR remains visible
- [ ] **S2** — Submit with < 6 digits → "Activate MFA" button stays disabled
- [ ] **S3** — `/mfa/setup` called while already enabled → backend returns error, shown to user
- [ ] **S4** — Unauthenticated call to `/api/v2/auth/mfa/setup` → `401`

#### Edge Cases
- [ ] **E1** — Click "Cancel" during setup step → returns to idle state, no MFA enabled
- [ ] **E2** — Click "Cancel" during QR/verify step → returns to idle, MFA still disabled
- [ ] **E3** — Refresh page after enabling MFA → badge still shows "Enabled" (persisted via `/me` response)
- [ ] **E4** — QR image fallback: `otpauth://` URL is shown as text below QR so manual entry in authenticator is possible

---

### Profile Page — Disable MFA

#### Happy Path
- [ ] **H1** — Click "Disable MFA" → code input shown
- [ ] **H2** — Enter correct current TOTP → "Confirm disable MFA" → success toast, badge flips to "Disabled"
- [ ] **H3** — After disabling, page shows "Enable MFA" button

#### Sad / Error Path
- [ ] **S1** — Enter wrong code when disabling → inline error, MFA remains enabled
- [ ] **S2** — Submit with < 6 digits → "Confirm disable MFA" button stays disabled
- [ ] **S3** — Unauthenticated call to `/api/v2/auth/mfa/disable` → `401`

#### Edge Cases
- [ ] **E1** — Click "Cancel" during disable step → returns to idle, MFA still enabled
- [ ] **E2** — Legacy-mode user (`source === 'legacy'`) → entire MFA section hidden (not shown)

---

### `/me` endpoint — mfa_enabled field

- [ ] **X1** — `GET /api/v2/auth/me` for MFA-disabled user → `data.mfa_enabled === false`
- [ ] **X2** — `GET /api/v2/auth/me` for MFA-enabled user → `data.mfa_enabled === true`
- [ ] **X3** — After enabling MFA via profile page, next `GET /api/v2/auth/me` reflects `mfa_enabled: true` without page reload

---

## Cross-Ticket Regression Checks

- [ ] **R1** — Existing login flow (no MFA) still works end-to-end after login page changes
- [ ] **R2** — Workspace deletion (IM-183 guard) doesn't interfere with email firing (IM-182)
- [ ] **R3** — Cancelled deletion + re-deletion fires two independent email batches (no idempotency cross-contamination)
- [ ] **R4** — Profile page loads cleanly for legacy-mode users (no JS errors in console, MFA section hidden)
- [ ] **R5** — `cargo test -p gateway --test auth_test` — all 9 tests pass (including `test_mfa_setup_requires_auth`)
