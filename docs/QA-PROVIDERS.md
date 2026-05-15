# Providers — Manual QA Checklist

End-to-end click-through to verify the provider management system is
truly working after the clean-slate + enable/disable switches
implementation. Pair with the automated suite
(`pytest tests/test_provider_chain_v2.py tests/test_providers_e2e.py -v`).

---

## 0. Pre-flight

```bash
make infra           # Postgres + Redis + Temporal up
make migrate         # applies 202605140002_providers_switches.sql
make bff             # in terminal 2 → http://localhost:8020
make ui              # in terminal 3 → http://localhost:3000
```

Log in as the owner account. Verify `/api/v2/providers/categories`
returns 200.

---

## 1. Wipe to a true clean slate

1. Open `/dashboard/providers`.
2. Click the red **Reset all** button in the header.
3. Type `WIPE` in the prompt.
4. **Expect:** toast "Wiped N table(s)". Every category card shows
   "No credentials — click to add". Stats strip shows `Connected: 0`.

Equivalent CLI sanity check:

```bash
make providers-wipe
psql ... -c "SELECT COUNT(*) FROM provider_credentials;"   # 0
psql ... -c "SELECT COUNT(*) FROM provider_chains_v2;"     # 0
```

---

## 2. Add a credential

1. Click any `llm.*` category (e.g. `llm.script`).
2. Click **Add credential**.
3. Provider = `openai`, label = `primary`, paste API key.
4. Pick a model (dropdown should populate from `/providers/models`).
5. Save → toast "Credential added".
6. **Expect:** credential row appears with green health switch ON, model
   badge, no "in chain" badge yet.

---

## 3. Build the workspace chain

1. Click **Add to chain** on the credential.
2. **Expect:** Priority chain section now lists it as `1.` with an
   enable switch (ON, green). Effective chain banner shows the same
   credential with origin `workspace`.

Add a second credential (label `secondary`) and add it to the chain
too. Use the up/down arrows to verify reordering persists after
refresh.

---

## 4. Toggle a chain entry off

1. Flip the small switch on credential `secondary` inside the **Priority
   chain** list (NOT the credential's master switch).
2. **Expect:** row dims, label strikes through, "disabled" badge shown.
3. The **Effective chain** banner above should now only show
   `primary` (because the resolver skips disabled entries).
4. Flip it back ON → it returns to the effective chain.

---

## 5. Toggle a credential's master switch

1. Flip the master switch (right side of the credential row, next to
   the star) on `primary`.
2. **Expect:** credential dims with "disabled" badge. The credential
   does NOT disappear from `provider_credentials` (verify with psql
   `SELECT label, enabled FROM provider_credentials;`).
3. Effective chain banner drops the row.
4. Flip back ON → it returns.

---

## 6. Default fallback star

1. Click the star icon on `primary`. **Expect:** amber "Default
   fallback" badge appears, toast confirms, the credential appears in
   the Effective chain with origin `default` even if removed from the
   chain.
2. Click again to clear.

---

## 7. Content-mode tabs

1. Switch the segmented control above the chain from `All modes` to
   `Short-form`.
2. **Expect:** Priority chain list reloads. If you haven't configured
   a short-form override, the chain looks empty here, but the
   Effective chain banner still shows the `All modes` workspace
   entries (with origin `workspace`, not `workspace+mode`).
3. Add a credential to the short-form chain only — verify the
   Effective chain now shows it with origin `workspace+mode` ahead of
   the `workspace` rows.

---

## 8. Channel-scope override

1. Open any channel: `/dashboard/channels/<id>`.
2. Click the **Providers** tab.
3. Pick the same category. Effective chain banner shows the workspace
   chain (origins `workspace` / `workspace+mode`).
4. Click **Add to override** on a credential. **Expect:** the entry
   appears as a `channel`-scoped row and jumps to the top of the
   Effective chain with origin `channel`.
5. Toggle the per-entry switch off → effective chain falls back to
   workspace inheritance.
6. Click **Clear override** → channel row removed; chain falls back to
   workspace entirely.

---

## 9. Error surfacing (no env-var ghosts)

This is the critical check that the system no longer silently invents
providers when nothing is configured.

1. Wipe again (`make providers-wipe`).
2. From the dashboard, trigger any content job that calls an LLM
   provider (e.g. /dashboard/content → Trigger).
3. **Expect:** the job fails with a structured error message
   containing `No provider configured for category 'llm.<x>'. Add a
   credential and chain entry in /dashboard/providers.` — NOT a silent
   call that uses some stale `OPENAI_API_KEY` from the environment.

If you still see a job succeed silently, the env-var fallback path
has regressed; check `src/providers/registry.py` for the
`NoProviderConfigured` raise.

---

## 10. Cache invalidation across services

1. Have at least one worker container running (`docker compose up -d worker-production`).
2. Toggle a credential off via the UI.
3. Tail worker logs: `docker compose logs -f worker-production | grep provider.invalidate`.
4. **Expect:** the worker logs an `invalidate` event from the
   `providers.invalidate` Redis pub/sub channel within ~1 second of
   the UI action.

---

## Sign-off

When all 10 sections pass, the provider management system is verified
fully working for this build.
