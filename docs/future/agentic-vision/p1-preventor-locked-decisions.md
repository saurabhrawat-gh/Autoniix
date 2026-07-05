# P1 — Preventor Service & Safety Ring — Locked Decisions (Draft)

**Jira Epic:** [`AE-343`](https://autoniix.atlassian.net/browse/AE-343)
**Parent:** `AE-341` (Agentic Vision Master)
**Depends on:** `AE-342` (P0 Foundation)
**Blocks:** `AE-344` (P2 — The Brain), all downstream phases that need safety
**BA Session date:** 2026-06-18
**Status:** ⚠️ **PROPOSED — pending product-owner sign-off**

> This document captures the decisions proposed in Step 1 of the BA Agent
> session for P1. **None of these are locked until the product owner
> explicitly approves**, at which point the BA Agent proceeds to Steps
> 2–9 (Users, Happy Path, Failure Cases, UX, Data, Security/Cost, Rollout,
> Story Breakdown).

---

## 1. Vision in one paragraph

The Preventor Service is the **safety circuit breaker** of the Autoniix
production pipeline. Every video must pass the Safety Ring before
delivery. It catches ban risk, legal exposure, copyright violations, and
brand-safety issues *before* a video ships, using a combination of
semantic search against a continuously-updated fingerprint database of
real YouTube ban cases, rule-based compliance checks, and an LLM Risk
Evaluator with mandatory grounding.

The single non-negotiable principle: **a channel strike is more
expensive than any number of false-positive HOLDs.** Every design
decision below flows from that principle.

---

## 2. Locked decisions (this session)

### Q1 — Service-down behaviour: **Hybrid fail-closed in production**

| Environment | Behaviour on Preventor outage / timeout |
|---|---|
| `production` | **Fail-closed.** Pipeline HALTs and waits for human review. `risk_assessments` row recorded with `decision='HALT_TIMEOUT'`. Pager alert fires. |
| `staging` / `dev` | **Fail-open with audit.** Video proceeds, `risk_assessments` row recorded with `decision='SKIPPED_OUTAGE'`, alert sent but pipeline does not block. |
| All envs | Hard 30s timeout on Preventor call. Kill-switch `preventor_enabled=false` (system_config flag) bypasses Preventor in true emergencies. |

**Rationale:** Channels are the asset; one strike costs months of
revenue. Devs must still be able to ship without Preventor flapping
breaking CI. Matches existing `quality_gate_override` audit pattern in
`@/Users/saurabhrawat/Desktop/projects/Autoniix/src/services/delivery/main.py:55-62`.

### Q2 — Success metrics

**Day 30 (post-launch):**

- ≥ 200 `ban_fingerprints` per active niche (epic floor)
- 100% of videos have a corresponding `risk_assessments` row (zero misses)
- HALT rate < 5% of evaluated videos
- APPROVE-then-strike rate < 1% (every such case is a P0 incident with retro)

**Month 6:**

- ≥ 1,000 fingerprints per active niche
- HALT rate stabilised at 1–3%
- Zero strikes attributable to a Preventor APPROVE in the trailing 30 days
- `channel_risk_mindmap` updated daily for 100% of active channels
- Auto-demotion to advisory mode never triggered (i.e., Preventor stays
  autonomous because accuracy holds)

### Q3 — Single most important thing

**Catch every actual policy violation before publish (zero false
negatives).** Mitigations for the resulting false-positive UX cost:

- WARN band (30–60 risk score) — does **not** block, only logs
- HOLD band (60–80) — queues for human review with < 4 hour SLA
- HALT band (> 80) — pauses workflow until human override
- Reasoning chain attached to every decision so a human can override fast

### Q4 — Out of scope (locked)

- Brain integration (Brain reads our outputs but does not signal Preventor) — owned by P2
- Risk-mind-map dashboard UI — deferred to a later UI epic
- COPPA / kids-content classification — handled by YouTube's own self-certification
- Non-English content moderation — defer to P9 (Multilingual)
- Regional law variations (DSA, Korea, India-specific) — defer to a future P10
- Shorts-vs-long-form policy split — single ruleset for v1, segment later if data shows it matters
- Live-stream content — N/A (Autoniix does not produce live)
- Comment / community-tab moderation — post-publish concern, separate epic if ever

### Q5 — Deadline

No external deadline. P1 is gated only on P0 (`AE-342`) being verified in
production. Estimated effort: **3 sprints (~6 weeks)** for full P1
including all three sub-services + Temporal integration. Precise sizing
emerges from Step 9 story breakdown.

### Q6 — Reference products

| Reference | Used for | Rationale |
|---|---|---|
| **YouTube Self-Certification questionnaire** | Step 2 rule-based check (mirror its 10 questions) | Public, well-documented, this is what YouTube actually uses |
| **TubeBuddy "Health Score"** | `channel_risk_mindmap` JSONB shape & dashboard UX language | Published methodology, creator-familiar mental model |
| **Hive AI content-moderation taxonomy** | Brand Safety Scorer categories | Industry standard; aligns with Google IAB Tech Lab brand-safety dimensions automatically |

Explicitly **not** drawing from internal-studio playbooks (e.g.
MrBeast's) — they are not documented publicly enough to be auditable.

### Q7 — Worst-case to design against

> **"Preventor silently APPROVEs a video that violates a clear,
> well-known policy we already had fingerprints for in our DB."**

This is the failure that destroys product trust. Explicit mitigations:

1. **Mandatory positive grounding.** Every LLM APPROVE *must* cite the
   top-3 similar fingerprints retrieved, not just HALTs.
2. **Shadow audit.** 1% of APPROVE decisions are re-evaluated by GPT-4o
   (vs the production GPT-4o-mini); any disagreement → human review queue.
3. **Outcome-scoring loop.** Any APPROVE-decided video that gets a strike
   post-publish writes its `risk_assessments` row + retrieved
   fingerprints to a `preventor_misses` table for next-cycle retraining.
4. **Auto-demotion.** 3 consecutive APPROVE→strike incidents in a
   rolling 30-day window → Preventor auto-demotes to advisory-only mode
   (`preventor_advisory_mode=true`), every decision becomes a
   recommendation requiring human approval until 5 consecutive
   APPROVE→no-strike outcomes restore autonomy. Mirrors Brain's
   auto-demote pattern in P2 (`AE-344`).

---

## 3. What's NOT decided yet (Steps 2–9 will cover)

The following remain open and will be tackled in subsequent BA-Agent steps:

**Step 2 (Users):** roles permitted to override HALT, dashboard reviewer
SLAs, who can manually add `ban_fingerprints`.

**Step 3 (Happy path):** exact insertion point in
`VideoProductionWorkflow` (after-assembly vs before-delivery — epic body
contradicts itself), Temporal activity contract, retry policy.

**Step 4 (Failure cases):** behaviour when `compliance_rules` table empty
(P3 not yet shipped), behaviour during cold-start (< 200 fingerprints in
niche), DMCA-library outage, reverse-image-search rate-limit.

**Step 5 (UX):** dashboard surfaces — HALT review queue, `data_confidence`
display, override audit log.

**Step 6 (Data):** `compliance_rules` schema ownership (P1 vs P3),
`channel_risk_mindmap` JSONB shape, `preventor_misses` retraining table,
GDPR retention for `risk_assessments`.

**Step 7 (Security/Cost):** per-video LLM cost cap (epic claims ~$0.01
for legal filter — needs a hard ceiling), KB Builder scraper auth /
robots.txt, override audit.

**Step 8 (Rollout):** soft-launch / shadow-mode plan for first N
channels, fingerprint-seeding strategy.

**Step 9 (Story breakdown):** split AE-343 into ~12–15 implementable
stories with explicit dependency order (DB migrations → service skeleton
→ KB builder → evaluator → sub-agents → Temporal integration →
dashboard).

---

## 4. Pre-flight context (informational)

### Already locked from P0 (`AE-342`) — do not re-decide

- `pgvector` on `postgres-app`; embedding model `text-embedding-3-small` (1536-dim)
- Helpers `embed_and_store(text, table, row_id)` and `semantic_search(query, table, top_k)`
- `brain_decisions`, `rag_index_metadata` tables
- Redis pub/sub envelope schema in `@/Users/saurabhrawat/Desktop/projects/Autoniix/src/events/schema.json`
- Topic `brain.preventor.risk` reserved
- Temporal pattern: external service → Redis pub/sub → signal sender → workflow signal handler
- `system_config` flag pattern

### Already exists in code

- `@/Users/saurabhrawat/Desktop/projects/Autoniix/src/events/bus.py` — Redis pub/sub with envelope validation (P0 — `AE-509`)
- `@/Users/saurabhrawat/Desktop/projects/Autoniix/src/quality/gate.py` — pre-publish *quality* gate (distinct from Preventor; runs *after* Preventor logically)
- `@/Users/saurabhrawat/Desktop/projects/Autoniix/src/services/delivery/main.py` — has `quality_gate_override` audit pattern Preventor will mirror

### Conflicts to resolve in Steps 3 & 6

1. **Quality gate vs Preventor gate ordering.** Currently `src/quality/gate.py` blocks publish on craft scores. Preventor adds a separate safety gate. Ordering must be Preventor → Quality gate → Delivery. A Preventor HALT short-circuits the quality gate entirely (no point scoring craft if we're not shipping).
2. **Temporal insertion-point inconsistency in epic body.** Epic intro says "before delivery"; Temporal integration section says "after assembly, before render". These are different points. **Step 3 will lock the exact placement** (working assumption: *after assembly, before render* — fail-fast saves render compute).
3. **Cost claim** ($0.01/script for Legal Filter) needs a hard ceiling in Step 7.

---

## 5. How to use this document

**If you accept these decisions as-is:** reply "all good" or
"locked" and the BA Agent proceeds to Step 2 — Users & Personas.

**If you want to override anything:** reply with the Q-number(s) and
your preferred answer; I'll update this document and re-confirm.

**If you want to defer the decision:** mark the Q with `DEFER` and I'll
either ask again later or remove it from P1 scope.

Once locked, this document gets:

- Pasted as a comment on Jira `AE-343` (link to repo path)
- Used as the source of truth for every Step-2-onwards question (no
  re-litigation)
- Cited in every child Story body's "Locked decisions" section
- Tagged with the label `ba-locked-2026-06-18` on AE-343

---

*Generated by BA Agent — `/.devin/workflows/ba-agent.md`*
