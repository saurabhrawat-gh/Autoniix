# Safety Rules (Karpathy Principles + Extended Controls)

## Karpathy Behavioral Rules — Non-Negotiable

### THINK FIRST

- State assumptions explicitly before building. If ambiguous, ask — never guess forward.
- Present multiple interpretations when ambiguity exists.
- If a simpler approach exists, say so before proceeding.
- Stop when confused. Name what's unclear and ask.

### STAY SIMPLE

- Minimum code that solves the problem. Nothing speculative.
- No abstractions for single-use code.
- No features beyond what was explicitly asked.
- If 200 lines could be 50, rewrite it before returning.

### STAY SURGICAL

- Touch only the lines required by the task.
- Do not "improve" adjacent code, formatting, or comments.
- Match existing style even if you would do it differently.
- If you notice dead code, mention it — do not delete it.
- Every changed line must trace directly to the user's request.

### SET GOALS

- Transform imperative tasks into declarative success criteria.
- "Add validation" → "Write tests for invalid inputs, then make them pass."
- "Fix the bug" → "Reproduce it in a test, then make the test pass."
- For multi-step tasks, output a numbered plan with verification steps before executing.

## Anti-Hallucination Protocols

- **Read before write** — always read current file state before editing.
- **Verify imports exist** — check requirements.txt before using a library.
- **Never invent API signatures** — read actual source or docs before calling.
- **Confirm file paths** — use grep/find, never guess paths.
- **Flag uncertainty** — "I believe this is correct, but I should verify" — then verify.

## Rollback Readiness

- Before any file edit: check `git status`. If dirty, stash first.
- Before any DB schema change: write a migration with rollback.
- Before any external API call with side effects: confirm idempotency.
- Log every state-changing action with enough context to reverse it.

## Production Safety

- **Never hardcode secrets or API keys.** Use config.py → .env.
- **Never write to production DB without dry-run confirmation.**
- **Delivery service blocks YouTube upload in test mode.**
- **Budget guard on every LLM call.** `accrued + estimated > max` → abort.
- **Emergency stop** available via dashboard and Temporal signal.

## Token Discipline

- Stay within token budgets. If a step would exceed it, stop and report.
- Do not use LLM for routing, retrying, filtering, or sorting — use plain code.
- Intelligence modules are local-first ($0.00 cost). LLM is fallback only.

## Context Hygiene

- For tasks reading more than 10 files: delegate to a subagent or summarize.
- Inject a State Card at the start of long sessions rather than replaying history.
- Do not paste full file contents — use file references and read on demand.
