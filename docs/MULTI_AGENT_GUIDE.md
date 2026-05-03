# Multi-Agent Orchestration Guide

> How to use multiple specialized AI agents effectively in Windsurf for the YouTube automation system.

---

## Overview

This project has 16+ microservices, 7 intelligence modules, 4 Temporal workers, and a 13-phase production pipeline. No single agent session can hold all this context. **Multi-agent orchestration** is how you divide work across specialized agents so each one operates with lean, focused context.

---

## Part 1: Agent Specialization Pattern

### The Core Idea

Instead of one general-purpose agent trying to understand the entire codebase, spawn **specialist agents** that each know one domain deeply. Each agent gets:

1. **A role definition** — who they are and what they do
2. **Context files** — the specific `.windsurf/rules/` and `.windsurf/skills/` they need
3. **An output format** — structured JSON/markdown so the parent can compose results
4. **Constraints** — what they must NOT do

### Available Specialists

| Agent | Subagent Spec | Best For |
|-------|--------------|----------|
| **Code Reviewer** | `subagents/code-reviewer.md` | Reviewing diffs before commit |
| **Test Runner** | `subagents/test-runner.md` | Running tests and analyzing failures |
| **Explorer** | `subagents/explorer.md` | Mapping unfamiliar code areas |
| **Intelligence Engineer** | `subagents/intelligence-engineer.md` | ML/NLP/scoring work |
| **Infra Engineer** | `subagents/infra-engineer.md` | Docker/Temporal/networking |
| **API Designer** | `subagents/api-designer.md` | FastAPI endpoint design |

---

## Part 2: How to Use Multiple Agents in Windsurf

Windsurf (Cascade) doesn't natively spawn subagents like Claude Code. Here are the practical patterns:

### Pattern A: Tab-Based Specialization

Open multiple Windsurf editor tabs, each with a different agent role:

1. **Tab 1 (Orchestrator)** — Your main session. Plans work, delegates, composes results.
2. **Tab 2 (Implementer)** — Opens files, writes code, runs tests.
3. **Tab 3 (Reviewer)** — Reviews diffs, checks quality.

**How to set up a specialist tab:**
1. Open a new Cascade chat tab
2. Paste the subagent spec as your first message: `@subagents/intelligence-engineer.md Act as this specialist for the following task...`
3. Include relevant context: `@.windsurf/skills/script-intelligence.md`
4. Give the specific task

### Pattern B: @-Mention Context Loading

In a single session, load specialist context on demand using `@` mentions:

```
@.windsurf/skills/script-intelligence.md @subagents/intelligence-engineer.md
Add sentiment arc scoring to the retention optimizer. 
Constraints: local-only, integrate with GBM features.
```

This gives Cascade the specialist's knowledge without opening a new tab.

### Pattern C: Workflow-Driven Delegation

Use slash-command workflows to invoke specific behaviors:

- `/pre-commit` — Runs the code reviewer + test runner sequence
- `/quality-check` — Validates against quality gates
- `/safety-audit` — Scans for safety violations
- `/diff-review` — Reviews current changes for surgical compliance
- `/context-hygiene` — Summarizes session into State Card

### Pattern D: Sequential Pipeline

For the video production pipeline, chain agents in sequence:

```
1. Explorer agent → maps the relevant service area
2. API Designer agent → designs the endpoint/schema changes
3. Intelligence Engineer agent → implements scoring/NLP logic
4. Code Reviewer agent → reviews the diff
5. Test Runner agent → runs and analyzes tests
```

Each step's output becomes the next step's input.

---

## Part 3: Pipeline Delegation — Concrete Examples

### Example 1: "Add a new LLM provider (Groq)"

| Step | Agent | What They Do | Context Needed |
|------|-------|-------------|----------------|
| 1 | Explorer | Map `src/providers/llm/` structure, read base.py + existing provider | `@.windsurf/skills/provider-pattern.md` |
| 2 | API Designer | Design the provider class interface, cost tracking | `@.windsurf/skills/provider-pattern.md` |
| 3 | Implementer | Write `groq_provider.py`, register in registry, add config | `@.windsurf/skills/provider-pattern.md` `@.windsurf/rules/naming-conventions.md` |
| 4 | Code Reviewer | Review diff for surgical compliance | `@subagents/code-reviewer.md` |
| 5 | Test Runner | Run tests, verify no regressions | `@subagents/test-runner.md` |

### Example 2: "Debug a failed video production"

| Step | Agent | What They Do | Context Needed |
|------|-------|-------------|----------------|
| 1 | Explorer | Read `video_production.py`, find the failing phase | `@.windsurf/skills/temporal-workflows.md` |
| 2 | Infra Engineer | Check Temporal UI, docker logs, worker status | `@.windsurf/skills/docker-infrastructure.md` |
| 3 | Implementer | Fix the bug (likely a service call timeout or budget guard) | Relevant skill for the failing service |
| 4 | Code Reviewer | Verify fix is minimal | `@subagents/code-reviewer.md` |

### Example 3: "Add intelligence to the delivery service"

| Step | Agent | What They Do | Context Needed |
|------|-------|-------------|----------------|
| 1 | Explorer | Map `src/services/delivery/`, read existing `seo_optimizer.py` | `@subagents/explorer.md` |
| 2 | Intelligence Engineer | Design new scoring features, GBM integration | `@subagents/intelligence-engineer.md` `@.windsurf/skills/script-intelligence.md` (as reference pattern) |
| 3 | API Designer | Design `/delivery-feedback`, `/delivery-train`, `/delivery-drift` endpoints | `@subagents/api-designer.md` |
| 4 | Infra Engineer | Add DB tables, update init-db.sql | `@subagents/infra-engineer.md` |
| 5 | Implementer | Write the code | All relevant skills |
| 6 | Code Reviewer + Test Runner | Validate | `@subagents/code-reviewer.md` `@subagents/test-runner.md` |

### Example 4: "Infrastructure change — add Redis Sentinel"

| Step | Agent | What They Do | Context Needed |
|------|-------|-------------|----------------|
| 1 | Infra Engineer | Design docker-compose changes, health checks, failover | `@subagents/infra-engineer.md` `@.windsurf/skills/docker-infrastructure.md` |
| 2 | Explorer | Find all `redis_url` references in codebase | `@subagents/explorer.md` |
| 3 | Implementer | Update `src/redis_client.py`, `src/config.py`, `docker-compose.yml` | `@.windsurf/skills/docker-infrastructure.md` |
| 4 | Safety Audit | Verify no hardcoded Redis URLs, check fallback logic | `/safety-audit` |

---

## Part 4: Context Isolation Strategy

### The Problem
A single Cascade session accumulates context. After reading 20+ files, the agent's effective attention degrades. The first 10k tokens of context dominate behavior.

### The Solution: Lean Context Per Agent

| Agent Type | Max Context Files | What to Load |
|-----------|------------------|-------------|
| Orchestrator | 3-5 | Plan file + State Card + task description |
| Specialist | 2-3 | One skill file + one rules file + task |
| Reviewer | 1-2 | Diff + one rules file |

### State Card Pattern

Between agent handoffs, summarize into a State Card:

```markdown
## Agent State Card — 2025-05-03T14:30:00Z

COMPLETED:
- Added GroqLLM provider class in src/providers/llm/groq_provider.py
- Registered in ProviderRegistry
- Added GROQ_API_KEY to config.py and .env.example

IN PROGRESS:
- Writing unit tests for GroqLLM

BLOCKERS:
- Need Groq API key for integration testing

NEXT:
1. Write test_groq_provider.py
2. Run /pre-commit workflow
3. Update docs/11-PROVIDER-INTERFACES.md
```

### When to Start a Fresh Session

Start a new Cascade tab when:
- Current session has read 15+ files
- You're switching to a completely different domain (e.g., from script intelligence to Docker)
- The task requires reading the same files with different intent
- Context window feels "crowded" — agent is making mistakes it wouldn't make fresh

---

## Part 5: Result Composition

### Merging Outputs from Multiple Agents

When multiple agents contribute to a task, the orchestrator composes results:

1. **Explorer** returns a file map → Orchestrator decides which files to modify
2. **API Designer** returns endpoint schemas → Orchestrator passes to Implementer
3. **Implementer** returns code changes → Orchestrator passes diff to Reviewer
4. **Reviewer** returns approval/issues → Orchestrator decides to commit or iterate

### Composition Rules

- Each agent returns **structured output** (JSON or markdown with clear sections)
- The orchestrator never passes raw conversation — only structured results
- If an agent returns freeform prose, the orchestrator summarizes it before passing along
- Conflicts between agents: the orchestrator decides, citing the architecture rules

---

## Part 6: Conflict Prevention

### File-Level Conflicts

When multiple agents might edit the same file:

| Strategy | When to Use |
|----------|------------|
| **Sequential editing** | Default — one agent finishes, next starts |
| **Branch-per-agent** | Large changes — each agent works on a git branch, merge after review |
| **Section isolation** | Different agents edit different functions in the same file |

### Git Strategy

```bash
# Before starting multi-agent work
git checkout -b feature/my-feature
git stash  # Clean working tree

# Agent 1 works and commits
git add -A && git commit -m "feat: add Groq provider"

# Agent 2 works on same branch
git add -A && git commit -m "feat: add Groq tests"

# Review before merge
/diff-review
/pre-commit

# Merge to main
git checkout main && git merge feature/my-feature
```

---

## Part 7: Quick Reference — Which Agent for What?

| Task | Primary Agent | Supporting Agents |
|------|--------------|-------------------|
| Add new provider | API Designer → Implementer | Explorer, Code Reviewer |
| Fix a bug | Explorer → Implementer | Code Reviewer, Test Runner |
| Add intelligence module | Intelligence Engineer | Explorer, API Designer, Infra Engineer |
| Infrastructure change | Infra Engineer | Explorer, Safety Audit |
| Debug failed pipeline | Explorer → Infra Engineer | — |
| Refactor code | Explorer → Implementer | Code Reviewer, Test Runner |
| Add API endpoint | API Designer → Implementer | Code Reviewer, Test Runner |
| Review before commit | Code Reviewer → Test Runner | — |
| Explore unfamiliar area | Explorer | — |

---

## Part 8: Advanced Patterns

### Pattern: Parallel Exploration

For large tasks, run multiple Explorer agents in parallel (different tabs):

- Tab 1: Explore `src/services/script/` 
- Tab 2: Explore `src/services/research/`
- Tab 3: Explore `src/temporal_workflows/`

Each returns a structured summary. The orchestrator composes a full picture without any single session reading 30+ files.

### Pattern: Review Loop

```
Implementer writes code
  → Reviewer reviews
  → If issues: Implementer fixes
  → Reviewer re-reviews
  → Until approved
  → Test Runner validates
```

Max 3 review cycles. If still not approved after 3, escalate to human.

### Pattern: Dry-Run First

For risky changes (DB schema, docker-compose, production config):

1. Infra Engineer designs the change
2. Implementer writes it
3. Reviewer checks it
4. **Run in test mode first** — `ENVIRONMENT_MODE=test`
5. Verify with Test Runner
6. Switch to production only after explicit human confirmation

---

## Summary

| Concept | Implementation |
|---------|---------------|
| **Specialist agents** | `subagents/*.md` specs — load via `@` mention or paste into new tab |
| **Context loading** | `.windsurf/skills/*.md` — domain knowledge on demand |
| **Guardrails** | `.windsurf/workflows/*.md` — slash-command quality/safety checks |
| **Always-loaded rules** | `.windsurf/rules/*.md` — architecture, naming, safety (every session) |
| **Cross-compatible** | `.claude/CLAUDE.md` — works with Claude Code CLI too |
| **Multi-tab orchestration** | Open specialist tabs, pass structured results between them |
| **Context isolation** | Each agent gets 2-3 context files max, returns structured output |
| **State Cards** | Summarize progress between handoffs, drop stale context |

The goal is not a clever agent. The goal is a **reliable** one — and reliable systems come from clear roles, lean context, and structured communication.
