# Model Routing — Automatic Model Selection

Applied automatically to every session. Devin should follow these rules
to select and switch models based on the task at hand.

## Default Model

Start every session with **Sonnet** (`/model sonnet`). It handles 80% of
tasks at 4x credit multiplier. Only escalate when needed.

## Auto-Escalation Rules

Switch models mid-session using `/model <name>` when:

### Escalate to Opus (`/model opus`)
- Designing system architecture or multi-service communication patterns
- Implementing complex distributed workflows (Temporal, sagas, event sourcing)
- Building agentic decision systems (multi-agent coordination, confidence thresholds)
- Debugging race conditions, deadlocks, or non-deterministic bugs
- Designing database schemas with complex relationships and migration strategies
- Writing security-critical code (auth, encryption, permission systems)
- Refactoring that spans 5+ files with interdependent changes

### Drop to SWE (`/model swe`)
- Fixing typos, formatting, or lint issues
- Adding/updating docstrings and comments
- Writing simple unit tests for existing functions
- Updating import paths or renaming symbols
- Minor CSS/style tweaks
- Adding a single endpoint that follows an existing pattern

### Stay on Sonnet for
- Implementing React components, hooks, and pages
- Writing FastAPI endpoints, middleware, and service layer code
- Database queries, migrations (routine), and ORM models
- TypeScript type definitions and interfaces
- Pipeline service implementation (individual activities, workers)
- Test writing (integration, e2e)
- Configuration changes and environment setup

## Task Detection Heuristics

When reading a task description, use these signals:

| Signal | Model |
|---|---|
| "design", "architecture", "how should I structure" | Opus |
| "implement", "add endpoint", "create component" | Sonnet |
| "fix typo", "rename", "update docs" | SWE |
| "debug", "why is this failing" | Sonnet first, escalate to Opus if unsolved in 2 turns |
| "refactor" (single file) | Sonnet |
| "refactor" (multi-file, cross-cutting) | Opus |
| "optimize performance" | Opus |
| "add test", "write spec" | Sonnet |
| Multi-agent, event-driven, state machine | Opus |

## Cost Awareness

- Opus costs 6-8x more than Sonnet per session. Use it only when the
  complexity justifies it.
- SWE costs 1x. Prefer it for trivial tasks.
- If Sonnet fails twice on the same problem, escalate to Opus. Two failed
  Sonnet turns cost more than one successful Opus turn.
