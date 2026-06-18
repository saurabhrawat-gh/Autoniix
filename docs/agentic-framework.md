# Agentic Framework (AE-P1)

The shared foundation every runtime/product agent (Brain, future
Preventor, Compliance, …) plugs into.

## What it is

`src/agents/` exposes three pieces:

| Module             | Purpose                                                       |
| ------------------ | ------------------------------------------------------------- |
| `base.py`          | `BaseAgent` ABC + `AgentObservation` / `AgentDecision` types. |
| `memory.py`        | `AgentMemory` — RAG recall over an agent's own decision table.|
| `registry.py`      | `AgentRegistry` — process-global lookup keyed by `agent.name`.|

The canonical lifecycle is:

```
observe()  → AgentObservation     # pull structured facts from the world
recall()   → list[memory rows]    # semantic-search past decisions
reason()   → state                # combine facts + precedent
decide()   → AgentDecision | None # the structured opinion
act()      → side-effects         # write DB, publish events, signal workflows
remember() → embedding            # stash for future recall
```

Each step is async, isolated (a failing `recall` doesn't block `decide`),
and overridable. Subclasses typically only implement `observe` + `decide`
+ `act`; everything else has sensible defaults.

## What's wired today

- **Brain Service** (`src/services/brain/agent.py`) — `BrainAgent`
  delegates to the existing `analyser` + `engine` modules so behaviour
  is bit-identical when memory recall is OFF.
- **Consumer routing** (`src/services/brain/consumer.py`) — when
  `brain.memory_recall.enabled = TRUE`, the consumer routes through
  `BrainAgent.run()`. When FALSE, the legacy code path runs unchanged.
- **Feature flags** (migration `202606171000_p1_agentic_framework_flags.sql`):
  - `brain.memory_recall.enabled` (default FALSE)
  - `preventor.memory_recall.enabled` (default FALSE — placeholder)
  - `compliance.memory_recall.enabled` (default FALSE — placeholder)

## How to add the next agent (Preventor walkthrough)

A new agent is ~150 lines. Use this checklist:

1. **DB**: create `<agent>_decisions` table mirroring `brain_decisions`
   (id, decision_type, scope, scope_id, directive, reasoning,
   confidence, embedding, created_at). Add a row to
   `rag_index_metadata` if you want time-decay scoring.

2. **Agent class**: subclass `BaseAgent` in
   `src/services/<agent>/agent.py`:
   ```python
   class PreventorAgent(BaseAgent):
       name = "preventor"
       decision_table = "preventor_decisions"
       flag_prefix = "preventor."

       async def observe(self, context):
           # pull pre-execution risk signals
           ...

       async def decide(self, state):
           # threshold logic; return AgentDecision or None
           ...

       async def act(self, decision):
           # persist to preventor_decisions, emit topic
           ...
   ```

3. **Register** at service startup (parallel to how Brain does it in
   `src/services/brain/main.py`):
   ```python
   from src.agents.registry import AgentRegistry
   AgentRegistry.register(PreventorAgent())
   ```

4. **Migration**: add `<agent>.memory_recall.enabled` to feature_flags
   (default FALSE).

5. **Tests**: mirror `tests/test_agents_framework.py::TestBrainAgentLifecycle`
   for the new agent. The framework's own tests already cover BaseAgent /
   AgentMemory / AgentRegistry.

That's it — RAG recall, structured decisions, audit logs, and per-agent
feature flags all come for free.

## Verification

- **Unit tests**: `tests/test_agents_framework.py` (17 tests) +
  `tests/test_brain_service.py` (19 tests) = 36 passing.
- **Live verified**: BrainAgent path triggered against real DB with
  `brain.memory_recall.enabled=TRUE`; `agent.decision_complete` log
  emitted; HALT decision written; `brain.directive` published.
  Memory recall itself requires a working `OPENAI_API_KEY` —
  AgentMemory gracefully returns empty when embedding fails.
