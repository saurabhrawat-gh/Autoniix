# QA Walkthrough — In-Prod Tickets (started 2026-06-03)

**Goal:** Walk through all 31 In-Prod tickets. Lock each as PASS or FAIL. At the end:
- All PASS tickets → bulk transition to **Done** + close + unassign
- All FAIL tickets → fix at once, then re-test

## Status Legend
- ⏳ pending
- 🧪 in-progress
- ✅ PASS — ready to close
- ❌ FAIL — needs fix
- 🚫 BLOCKED — depends on another fix

## Walkthrough Order

| # | Key | Priority | Status | Type | Notes |
|---|-----|----------|--------|------|-------|
| 1 | AE-263 | Highest | ✅ | Bug | Fixed: visibilityState gate on stats poll + prefetch=false on marketplace links |
| 2 | AE-264 | Highest | ✅ | Bug | Resolved by AE-285 invite-only; follow-up GH#350 |
| 3 | AE-277 | High | ✅ | Bug | Core invite lock fixed; follow-up GH#351 for role/transfer/accept + regression tests |
| 4 | AE-93 | Medium | ✅ | Test | _PLAN_MEMBER_LIMITS enforced in workspace.py + pg_advisory_xact_lock |
| 5 | AE-94 | Medium | ✅ | Test | transfer_ownership + last-owner guard both in workspace.py |
| 6 | AE-95 | Medium | ✅ | Test | workspace_integrations CRUD + _notify_slack() firing on invite |
| 7 | AE-117 | Medium | ✅ | Impl | SerpAPI registered in ProviderRegistry, wizard + health_check tested |
| 8 | AE-119 | Medium | ✅ | Impl | MinIO registered, connect/_connect tested, wizard fields tested |
| 9 | AE-122 | Medium | ✅ | Impl | youtube_oauth.py has full PKCE flow: auth/callback/status/disconnect |
| 10 | AE-174 | Medium | ✅ | Impl | Marketplace tab in providers/page.tsx with full catalog CRUD |
| 11 | AE-175 | Medium | ✅ | Impl | Drag-and-drop chain editor in providers/[category]/page.tsx |
| 12 | AE-176 | Medium | ✅ | Impl | Content-mode aware chain editing; pipeline_mode in chain cache key |
| 13 | AE-177 | Medium | ✅ | Impl | src/workers/provider_health_beat.py — Temporal workflow + Redis pub/sub |
| 14 | AE-178 | Medium | ✅ | Impl | change_requests.py full state machine; _notify_stub (non-blocking) |
| 15 | AE-179 | Medium | ✅ | Impl | rotate_credential with safe-swap health-check gate in providers.py |
| 16 | AE-182 | Medium | ✅ | Impl | _PLAN_MEMBER_LIMITS + advisory lock + 402 on overflow |
| 17 | AE-183 | Medium | ✅ | Impl | transfer_ownership endpoint + cannot-remove-last-owner guard |
| 18 | AE-184 | Medium | ✅ | Impl | GET/PUT /integrations + _notify_slack + _notify.py dispatcher |
| 19 | AE-195 | Medium | ✅ | Test | test_configure_llm_credentials.py — CredentialIn, wizard, custom_openai_compat |
| 20 | AE-196 | Medium | ✅ | Test | test_configure_tts_credentials.py — EdgeTTS, ElevenLabs, FishAudio |
| 21 | AE-197 | Medium | ✅ | Test | test_configure_search_credential.py — registered, health_check, wizard |
| 22 | AE-198 | Medium | ✅ | Test | test_configure_storage_credential.py — config, connect, wizard, registered |
| 23 | AE-199 | Medium | ✅ | Test | youtube_oauth.py fully implemented; auth/callback/status/disconnect |
| 24 | AE-200 | Medium | ✅ | Test | test_provider_health_smoke.py — all categories + every provider has health_check |
| 25 | AE-201 | Medium | ✅ | Test | test_provider_catalog_migration.py — migration file + SQL statements verified |
| 26 | AE-202 | Medium | ✅ | Test | providers/page.tsx marketplace tab — catalog browsing, connect, filter |
| 27 | AE-203 | Medium | ✅ | Test | test_provider_chain_v2.py — resolution order, dedup, fallback, invalidation |
| 28 | AE-204 | Medium | ✅ | Test | test_router_test_mode.py + pipeline_mode in chain cache key |
| 29 | AE-205 | Medium | ✅ | Test | provider_health_beat.py — Temporal workflow, Redis pub/sub, metrics |
| 30 | AE-206 | Medium | ✅ | Test | change_requests.py — create/admin-review/owner-review/apply state machine |
| 31 | AE-207 | Medium | ✅ | Test | test_credential_rotation_safe_swap.py — abort on fail, promote on pass |

## Failure log

_(no open failures — all 31 tickets resolved)_


## Pass log

- **AE-263** — PASS (fixed). `AppStateProvider.tsx` stats poll gated behind `document.visibilityState`; `prefetch={false}` added to provider marketplace card links. Pushed in commit `38ad3e0`.
- **AE-277** — PASS. Core advisory-lock fix confirmed in workspace.py; follow-up GH#351 for set_member_role/transfer_ownership/accept_invite + regression tests.
- **AE-264** — PASS. Verified `/register` returns invite-only block; `/dashboard/users` shows only `admin@autoniix.com` as Superadmin. Follow-up `GH#350` filed for future public self-serve signup + Stripe-paid workspace creation (defer until pre-launch).
- **AE-93** — PASS. `_PLAN_MEMBER_LIMITS` dict + advisory lock + 402 on overflow confirmed in `workspace.py`.
- **AE-94** — PASS. `transfer_ownership` endpoint + last-owner demote/remove guards confirmed in `workspace.py`.
- **AE-95** — PASS. `workspace_integrations` CRUD endpoints + `_notify_slack()` firing on invite confirmed.
- **AE-117** — PASS. `serpapi` registered in `ProviderRegistry`; `test_configure_search_credential.py` covers health_check + wizard.
- **AE-119** — PASS. `minio` registered; `test_configure_storage_credential.py` covers connect + wizard + registered.
- **AE-122** — PASS. `youtube_oauth.py` has complete PKCE flow: `/auth`, `/callback`, `/status`, `/disconnect`.
- **AE-174** — PASS. Marketplace tab in `providers/page.tsx` with catalog browsing, connected status, add/remove.
- **AE-175** — PASS. Drag-and-drop chain editor in `providers/[category]/page.tsx` with reorder + add/remove.
- **AE-176** — PASS. Content-mode segmented control in chain editor; `pipeline_mode` in chain cache key confirmed.
- **AE-177** — PASS. `src/workers/provider_health_beat.py` — Temporal workflow fires every 5 min, Redis pub/sub on status change, Prometheus metrics.
- **AE-178** — PASS. `change_requests.py` implements full state machine: pending_admin → pending_owner → applied/rejected. Note: notifications are a stub (`_notify_stub`) — wired for future integration.
- **AE-179** — PASS. `rotate_credential` in `providers.py` implements health-check gate (422 on fail, promote on pass). `rotated_at` updated; `ROTATION_WARN_DAYS` badge logic present.
- **AE-182** — PASS. Same as AE-93 — member limits enforced server-side with advisory lock.
- **AE-183** — PASS. Same as AE-94 — `transfer_ownership` + guards confirmed.
- **AE-184** — PASS. Same as AE-95 — GET/PUT `/integrations` + `_notify.py` dispatcher confirmed.
- **AE-195** — PASS. `test_configure_llm_credentials.py` covers `CredentialIn`, `WizardCredentialIn`, field split, validation, `custom_openai_compat`.
- **AE-196** — PASS. `test_configure_tts_credentials.py` covers EdgeTTS, ElevenLabs, FishAudio, chain instantiation.
- **AE-197** — PASS. `test_configure_search_credential.py` covers SerpAPI registration, health_check, wizard, instantiation.
- **AE-198** — PASS. `test_configure_storage_credential.py` covers MinIO config, connect, wizard, registered.
- **AE-199** — PASS. `youtube_oauth.py` fully implemented with token refresh, vault storage, channel info fetch.
- **AE-200** — PASS. `test_provider_health_smoke.py` verifies all categories registered, every provider has `health_check`, test-mode providers pass health gate.
- **AE-201** — PASS. `test_provider_catalog_migration.py` verifies migration file exists + SQL key statements present.
- **AE-202** — PASS. `providers/page.tsx` marketplace tab with full catalog CRUD confirmed.
- **AE-203** — PASS. `test_provider_chain_v2.py` covers resolution order, dedup, partial override, fallback, invalidation.
- **AE-204** — PASS. `test_router_test_mode.py` covers test-mode routing; `pipeline_mode` in cache key confirmed.
- **AE-205** — PASS. `provider_health_beat.py` — Temporal activity + workflow + Redis pub/sub + Prometheus metrics all implemented.
- **AE-206** — PASS. `change_requests.py` full create/admin-review/owner-approve/reject/auto-apply confirmed.
- **AE-207** — PASS. `test_credential_rotation_safe_swap.py` — abort on failed health, promote on passing health, staging path format all covered.

