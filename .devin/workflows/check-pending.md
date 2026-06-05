---
description: Review PENDING.md and surface only items whose trigger has fired
---

When the user invokes `/check-pending`, do this:

1. Read `PENDING.md` from the workspace root.
2. For each item, evaluate its **Trigger** against current evidence:
   - For deploy-gated items (`P7-deploy`): ask the user if a deploy
     happened recently, or check git log for deployment-related commits.
   - For DB-pressure items (`postgres-read-replicas`): hit
     `/api/fleet-health` if reachable, look at `db_pool.pressure`.
   - For queue-depth items (`worker-auto-scaling`): same.
   - For tenant items (`multi-tenancy`): check if any new auth records
     suggest a second user — usually no, so default to "trigger not fired."
   - For data-volume items (`cross-niche-transfer-learning`): query
     `gate_thresholds` row count or just ask the user how long the
     calibrator has been running in production.
3. Report **only** items whose trigger is plausibly fired. Do not list
   the others — the whole point of trigger-gating is to avoid pre-emptive
   work.
4. If no triggers have fired, say so plainly: "Nothing actionable. Keep
   shipping." Do not invent reasons to do work.

Output format: short bulleted list of fired triggers with a one-line
recommendation per item. Skip the "deferred but not fired" items
unless the user explicitly asks for the full list.
