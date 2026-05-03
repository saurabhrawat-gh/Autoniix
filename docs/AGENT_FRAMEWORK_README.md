# 🤖 Agent Development Framework
> **The complete reference for building production-grade AI agents.**  
> Five-Layer Architecture · Karpathy Principles · Token Efficiency · Runtime Guardrails

---

## What This Is

This framework synthesizes three sources of best practice into one reference:

| Source | What it provides |
|--------|-----------------|
| **Agent Dev Kit** | 5-layer architecture: CLAUDE.md, Skills, Hooks, Subagents, Plugins |
| **Karpathy Principles** | Behavioral OS: Think first, Stay simple, Stay surgical, Define goals |
| **Extended Controls** | Runtime token budgets, LLM/code boundary, context hygiene, anti-hallucination |

---

## Table of Contents

- [Part I — Five-Layer Architecture](#part-i--five-layer-architecture)
  - [Layer 1 — CLAUDE.md](#layer-1--claudemd-the-memory-layer)
  - [Layer 2 — Skills](#layer-2--skills-the-knowledge-layer)
  - [Layer 3 — Hooks](#layer-3--hooks-the-guardrail-layer)
  - [Layer 4 — Subagents](#layer-4--subagents-the-delegation-layer)
  - [Layer 5 — Plugins](#layer-5--plugins-the-distribution-layer)
- [Part II — Karpathy Principles](#part-ii--karpathy-principles)
  - [Principle 1 — Think Before Coding](#principle-1--think-before-coding)
  - [Principle 2 — Simplicity First](#principle-2--simplicity-first)
  - [Principle 3 — Surgical Changes](#principle-3--surgical-changes)
  - [Principle 4 — Goal-Driven Execution](#principle-4--goal-driven-execution)
- [Part III — Extended Controls](#part-iii--extended-controls)
- [Part IV — Master CLAUDE.md Template](#part-iv--master-claudemd-template)
- [Part V — Quick Reference](#part-v--quick-reference)

---

## Part I — Five-Layer Architecture

Every agent or agentic workflow you build should be structured across five distinct layers. Each layer has a single responsibility. Together they form a composable, distributable, team-ready stack.

```
agent-project/
├── .claude/
│   ├── CLAUDE.md              ← L1: Always-loaded constitution
│   ├── skills/                ← L2: On-demand knowledge modules
│   │   └── your-skill/
│   │       ├── SKILL.md
│   │       ├── scripts/
│   │       ├── templates/
│   │       └── assets/
│   └── hooks/                 ← L3: Deterministic guardrails
│       ├── PreToolUse.sh
│       ├── PostToolUse.sh
│       ├── SessionStart.sh
│       ├── Stop.sh
│       └── SubagentStop.sh
├── subagents/                 ← L4: Delegation layer
│   ├── code-reviewer.md
│   ├── test-runner.md
│   └── explorer.md
└── plugins/                   ← L5: Distribution layer
    ├── manifest.json
    └── marketplace.url
```

| Layer | Name | Responsibility |
|-------|------|---------------|
| L1 — CLAUDE.md | Memory Layer | Always-loaded constitution: rules, conventions, voice. Never optional. |
| L2 — Skills | Knowledge Layer | Description-matched, auto-invoked context. Loaded on demand. |
| L3 — Hooks | Guardrail Layer | Deterministic shell scripts on agent events. No AI — pure logic. |
| L4 — Subagents | Delegation Layer | Own context window. One job. One result. Keeps main thread clean. |
| L5 — Plugins | Distribution Layer | Bundles skills + agents + hooks into npm packages. One install, team aligned. |

---

### Layer 1 — CLAUDE.md: The Memory Layer

> **Write CLAUDE.md once. Save yourself 100 prompts later.**

**What it is:** A markdown file the agent reads at the start of every session. Unlike a prompt you type each time, it persists. Think of it as onboarding documentation that never goes stale.

#### Where it lives

| Scope | Path | Purpose |
|-------|------|---------|
| Global | `~/.claude/CLAUDE.md` | Loaded for every project. Your default voice, style, tools, preferences. |
| Project | `.claude/CLAUDE.md` | Loaded for this repo only. Architecture rules, naming conventions, repo-specific context. |

#### What to put in it

- **`architecture.rules`** — How the system fits together (data flow, layer responsibilities, service ownership)
- **`naming.conventions`** — File names, function names, casing rules, acronym expansions
- **`test.expectations`** — When to write tests, what counts as coverage, which frameworks to use
- **`repo.map`** — Where things live and why (prevents wrong-directory file creation)
- **`tool.inventory`** — What tools the agent has access to and the correct way to call them
- **`style.guide`** — Prose voice, comment density, preferred idioms for your language/framework

> ⚡ **Extended Best Practice:** Keep CLAUDE.md under **500 lines**. Beyond that, the agent starts skimming. Split anything domain-specific into a Skill instead. Use a project-level `CLAUDE.md` committed to Git (shared) and a `CLAUDE.local.md` in `.gitignore` (personal dev preferences). **Audit monthly** — stale rules create confident wrong behavior.

---

### Layer 2 — Skills: The Knowledge Layer

> **One skill. Wired forever. Future Claude knows.**

**What it is:** A folder containing a `SKILL.md` with a description the agent matches against the task at hand. If the description matches, the skill is loaded — no prompt needed.

#### Skill folder anatomy

```
your-skill/
├── SKILL.md        ← Description the agent matches against (be precise)
├── scripts/        ← Reference scripts the skill calls
├── templates/      ← Boilerplate the skill copies into the project
└── assets/         ← Images, fonts, configs the skill ships with
```

#### Where skills live

- `~/.claude/skills/` — Reusable across every project (PDF handling, video conversion, etc.)
- `.claude/skills/` — Domain knowledge for this repo (internal API patterns, project-specific workflows)

> ⚡ **Extended Best Practice:** Skill descriptions are **semantic matching strings** — treat them like search queries. Make them specific and action-oriented: `"Use when creating or editing Word documents (.docx)"` beats `"document skill"`. Add a **"When NOT to use"** section to prevent false-positive matches. Version your skills (`SKILL_v2.md`) so you can iterate without breaking existing agents.

---

### Layer 3 — Hooks: The Guardrail Layer

> **Hooks turn vibes into rules. Git hooks, but for your agent.**

**What it is:** Hooks are the one place where you enforce rules **without relying on the agent's judgment**. They fire on specific events, match against tool calls via patterns, and run plain shell. Exit code `2` blocks the operation. `stdout` is injected as context.

#### Available hooks

| Hook | When it fires | What to use it for |
|------|--------------|-------------------|
| `PreToolUse.sh` | Before any tool runs | Block `rm -rf`, validate before DB writes, check domain allowlists |
| `PostToolUse.sh` | After tool runs | Auto-lint on Write, ping Slack on deploy, append audit log |
| `SessionStart.sh` | Session begins | Inject date, env, current branch, recent git log |
| `Stop.sh` | Claude finishes a turn | Save state, trigger CI, update dashboard |
| `SubagentStop.sh` | Subagent returns | Validate output format, strip PII before returning to main session |

#### Hook flow

```
Event fires → Matcher checks (wildcard / regex / exact) → Command runs → Exit code determines block or pass
```

#### Matcher types

```bash
# Block any bash rm with wildcard
Bash(rm *)  →  if [[ "$ARGS" == *"-rf"* ]]; then exit 2; fi

# Regex match on command
Bash(.*prod.*)  →  echo "WARNING: Production operation detected"

# Exact string match
Write(config.json)  →  validate_config.sh
```

> ⚡ **Extended Best Practice:** **Audit log everything.** Every `PreToolUse` should append to a session log: timestamp, tool name, args, exit code. This is your flight recorder when something goes wrong. Don't over-block — a hook that exits `2` too aggressively trains you to disable hooks. Reserve blocking for genuinely dangerous patterns. For everything else, inject a warning via stdout and let the agent decide.

---

### Layer 4 — Subagents: The Delegation Layer

> **Delegate the noise. Keep the main thread clean.**

**What it is:** A child Claude instance spawned to do exactly one job and return exactly one result. It has its own system prompt, tools, and context window. The parent sees only the result.

#### Parent vs. Child

| Parent (main session) | Child (subagent run) |
|----------------------|---------------------|
| Plans the work | Spawned for one job |
| Calls subagents like tools | Own system prompt + tools |
| Stays clean — only sees results | Own context window |
| Orchestrates the sequence | Returns ONE message back |

#### Common subagent patterns

- **`code-reviewer.md`** — Reviews diffs against repo conventions, returns structured review
- **`test-runner.md`** — Runs the test suite, returns failures with context
- **`explorer.md`** — Maps the codebase, returns a structured summary
- **`feature-dev.md`** — Designs and implements a feature end-to-end, returns PR-ready diff

> ⚡ **Extended Best Practice:** Use subagents for tasks that are (a) **isolatable**, (b) **expensive in context** (reading 10+ files), or (c) **risky** (give a subagent narrower permissions). Always define the subagent's output format in its system prompt — a subagent returning freeform prose is hard to compose with. **Return structured JSON or markdown with clear sections.**

---

### Layer 5 — Plugins: The Distribution Layer

> **Build it once. Install it everywhere. The team levels up together.**

**What it is:** A plugin bundles skills, agents, hooks, and commands into a versioned, installable package declared in `plugin.json`.

#### Plugin contents

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "skills": ["build", "ship"],
  "agents": ["code-reviewer", "test-runner"],
  "hooks": ["PreToolUse", "PostToolUse"],
  "commands": ["/review", "/test", "/deploy"]
}
```

| What ships | What it provides |
|-----------|-----------------|
| `skills/` | Knowledge bundles ride along |
| `agents/` | Subagents ship inside the plugin |
| `hooks/` | Guardrails travel with the bundle |
| `commands/` | Slash-commands the team gets instantly |

> ⚡ **Extended Best Practice:** Treat plugins like npm packages: **semver, changelog, deprecation warnings**. A breaking change to a hook or skill description can silently change agent behavior across your whole team. Pin plugin versions. Write a `CHANGELOG.md` inside every plugin. Test in a clean project before publishing.

---

## Part II — Karpathy Principles

Andrej Karpathy identified four recurring failure modes in LLM coding agents. Forrest Chang encoded them into a `CLAUDE.md` file that became one of the fastest-growing repos on GitHub (100k+ stars). These are the **behavioral OS** every agent needs.

> *"The models make wrong assumptions and run with them. They overcomplicate. They make side-effect changes to code they don't understand. They charge ahead without verification."* — Karpathy

---

### Principle 1 — Think Before Coding

> **Don't assume. Don't hide confusion. Surface tradeoffs.**

**The failure it fixes:** Agents silently pick an interpretation and build the wrong thing. By the time you notice, 200 lines have been written for the wrong requirement.

#### Required behaviors

- **State assumptions explicitly** — if uncertain about scope, format, permissions, or data shape, say so
- **Present multiple interpretations** when ambiguity exists — don't pick silently
- **Push back** when a simpler approach exists
- **Stop when confused** — name what's unclear and ask rather than guessing forward
- **Surface tradeoffs** — speed vs. safety, simplicity vs. flexibility, now vs. later

#### Anti-pattern vs. correct

```
❌ BAD — Silent assumption
User: "Add a feature to export user data"
Agent: [immediately writes 200 lines assuming all users, JSON format,
        file download, all fields — without asking anything]

✅ GOOD — Surface assumptions
User: "Add a feature to export user data"
Agent: "Before implementing, I need to clarify:
  1. Scope — export all users or a filtered subset? (privacy implications)
  2. Format — file download, API endpoint returning data, or background job?
  3. Fields — which user fields to include? Any sensitive ones to exclude?
  Simplest approach: API endpoint returning paginated JSON.
  What's your preference?"
```

> ⚡ **Extended Practice:** Add a **THINK step** requirement: for any task over 5 tool calls, the agent must output a numbered plan with verification checks before executing. This externalizes reasoning and catches wrong assumptions before they become code.

---

### Principle 2 — Simplicity First

> **Minimum code that solves the problem. Nothing speculative.**

**The failure it fixes:** Agents build Strategy Pattern class hierarchies for single-use discount calculations. They add "flexibility" nobody asked for. They implement tomorrow's problem today.

#### Required behaviors

- No features beyond what was **explicitly asked**
- No abstractions for single-use code
- No "flexibility" or "configurability" that wasn't requested
- No error handling for logically impossible scenarios
- If 200 lines could be 50, **rewrite it** before returning
- **The test:** Would a senior engineer say this is overcomplicated? If yes, simplify.

#### Anti-pattern vs. correct

```python
# ❌ BAD — Over-engineered for a simple request
class DiscountStrategy(ABC):
    @abstractmethod
    def calculate(self, amount): ...

class PercentageDiscount(DiscountStrategy): ...
class FixedDiscount(DiscountStrategy): ...
class DiscountConfig: ...
class DiscountCalculator: ...
# 50+ lines, requires 30+ lines of setup to use

# ✅ GOOD — Minimum code that solves the problem
def calculate_discount(amount, percent):
    """Calculate discount. percent is 0-100."""
    return amount * (percent / 100)

discount = calculate_discount(100.0, 10.0)  # $10 off
```

> ⚡ **Extended Practice:** Enforce a **complexity budget** in your CLAUDE.md: no new abstraction layer without an explicit request, no new dependency without a documented reason. Make the agent justify complexity in a comment: `# This abstraction exists because X` — not because it seemed useful.

---

### Principle 3 — Surgical Changes

> **Touch only what you must. Clean up only your own mess.**

**The failure it fixes:** Agents reformat the file while fixing a bug. They add type hints nobody asked for. They "improve" adjacent code that wasn't broken. Diffs become unreadable; review becomes impossible.

#### Required behaviors

- Don't **"improve"** adjacent code, comments, or formatting
- Don't refactor things that aren't broken
- **Match existing style**, even if you'd do it differently yourself
- If you notice dead code, **mention it — don't delete it**
- When your changes create orphans (unused imports, dead variables), remove only **those** — not pre-existing dead code
- **The test:** Every changed line must trace directly to the user's request

#### The style drift anti-pattern

```
User: "Add logging to the upload function."

❌ BAD — Agent adds logging PLUS:
  - Changes single quotes to double quotes (not asked)
  - Adds type hints (not asked)
  - Adds a docstring (not asked)
  - Reformats whitespace (not asked)
  - Restructures boolean return logic (not asked)
  15 lines changed for a 3-line task

✅ GOOD — Agent adds ONLY the logging lines,
  using the existing code's style (single quotes, no type hints, same spacing)
  3 lines changed
```

> ⚡ **Extended Practice:** Add a `PostToolUse` hook that runs `git diff --stat` after any Write operation and injects the changed-file count into context. If more than 3 files changed for a single-file task, the agent should pause and justify why.

---

### Principle 4 — Goal-Driven Execution

> **Define success criteria. Loop until verified. Don't tell it what to do — give it success criteria and watch it go.**

**Karpathy's highest-leverage insight:** LLMs are exceptionally good at looping until they meet specific goals. The failure mode is giving them vague imperatives. The correct pattern is **declarative goals with verifiable completion criteria**.

#### Transformation pattern

| Instead of (imperative) | Use (declarative + verifiable) |
|------------------------|-------------------------------|
| "Add validation" | "Write tests for invalid inputs, then make them pass" |
| "Fix the bug" | "Write a test that reproduces it, then make it pass" |
| "Refactor X" | "Ensure tests pass before and after — no regressions" |
| "Improve the API" | "Reduce endpoint count by 30% with no feature loss — measure before/after" |

#### Multi-step plan format

For any task over 3 steps, require the agent to output a plan before executing:

```
GOAL: [Declarative outcome — what "done" looks like]

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]

DONE WHEN: [Binary success criterion]
```

> ⚡ **Extended Practice:** Encode success criteria in your task format, not in conversation. Every task card should have: `GOAL` (what done looks like), `CONSTRAINTS` (what not to change), `VERIFY` (how to confirm), `ROLLBACK` (how to undo if wrong).

---

## Part III — Extended Controls

These controls address **runtime behavior** — what the agent does when actually running tasks. Not in the original Agent Dev Kit or Karpathy repo. Based on production experience.

---

### Extended Control 1 — Token Budgets

> **No silent overruns. Every AI step runs under a budget.**

Without token budgets, a single runaway subagent can exhaust your daily quota before 9am.

#### Budget config (add to CLAUDE.md)

```yaml
token_budgets:
  per_step: 2048        # Maximum tokens for a single tool call or generation step
  per_pipeline: 10000   # Maximum tokens for one complete task pipeline
  per_day: 100000       # Maximum tokens per agent instance per day
```

**Rules:**
- Budgets live in config, not in prompts
- On breach: halt immediately, log with step context, surface to operator
- Use `SessionStart.sh` to inject current daily usage into context
- Use `Stop.sh` to append token usage to a daily log file

---

### Extended Control 2 — The LLM/Code Boundary

> **Claude is for judgment calls. Plain code does everything else.**

Don't ask the model to "decide if we should retry" when a status code already answers. The model makes a routing decision one week, a different decision the next — you've reinvented flaky if-else at $0.003/token.

#### ✅ Use LLM for
- Classification of unstructured input (sentiment, intent, category)
- Drafting, summarization, extraction from natural language
- Judgment calls where context and nuance matter
- Generating options or tradeoffs for human review

#### ❌ Use plain code for
- Fetching, filtering, sorting, paginating — deterministic answers
- Routing — `if status == 429: retry` — the model doesn't decide this
- Persisting, dispatching, scheduling — pure side effects
- Validation against known schemas — use a schema library, not a prompt

---

### Extended Control 3 — Context Hygiene

> **A polluted context window is the #1 cause of agent drift. Keep it lean.**

As a session grows, the agent's effective attention degrades. A 50k token context window where the first 40k are noise is worse than a clean 10k context.

#### Context hygiene rules

1. Use subagents for any task that requires reading **more than 10 files**
2. After every major milestone, summarize progress into a **State Card** and drop raw history
3. Never paste full file contents into the main session — use file references
4. Keep CLAUDE.md + active Skills combined under **2000 tokens**
5. Use `SessionStart.sh` to inject a compressed state summary

#### State Card format

```markdown
## Agent State Card — [timestamp]

COMPLETED:
- [bullet list of done items]

IN PROGRESS:
- [current task + last known state]

BLOCKERS:
- [anything needing human input]

NEXT:
1. [next step]
2. [step after that]
3. [step after that]
```

---

### Extended Control 4 — Anti-Hallucination Protocols

> **Prefer retrieval over generation. Verify before commit.**

Agents hallucinate API signatures, file paths, and function names. In a coding context, these become bugs that look correct but aren't.

#### Rules

- **Read before write** — the agent must read the current file state before editing it
- **Verify imports exist** — before using a library, check it's in `package.json` / `requirements.txt`
- **Never invent API signatures** — read actual source or docs before calling a function
- **Use grep/find to confirm file paths** — "I think it's in `src/utils`" is not acceptable
- **For external API calls** — verify endpoint URL from docs, never from memory
- **Flag uncertainty explicitly** — "I believe this is the correct signature, but I should verify" — then actually verify

---

### Extended Control 5 — Failure Recovery & Rollback

> **Every agent action that modifies state must be reversible.**

#### Rollback checklist

1. Before any file edit: ensure `git status` is clean (or stash automatically)
2. Before any DB write: use transaction or dry-run mode first
3. Before any external API call with side effects: confirm idempotency
4. After any failed step: emit a ROLLBACK instruction the agent can execute autonomously
5. Log every state-changing action with enough context to reverse it

```bash
# PreToolUse.sh — auto-stash before any Write operation
if [[ "$TOOL" == "Write" ]]; then
  if [[ -n "$(git status --porcelain)" ]]; then
    git stash push -m "auto-stash-before-agent-write-$(date +%s)"
    echo "Auto-stashed dirty working tree. Rollback: git stash pop"
  fi
fi
```

---

### Extended Control 6 — Observability

> **You can't debug what you can't see. Every session should produce a structured log you can replay.**

#### Minimum observability stack

| Log | What it captures |
|-----|-----------------|
| Session log | Every tool call: timestamp, tool, args, result, token cost |
| Decision log | Agent's reasoning whenever it makes a judgment call |
| Error log | Every failed tool call with full context |
| Budget log | Running token totals per step, per session, per day |
| State snapshots | State Card at each milestone |

```bash
# PostToolUse.sh — append structured log entry
echo "{
  \"session_id\": \"$SESSION_ID\",
  \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
  \"tool\": \"$TOOL\",
  \"result\": \"$EXIT_CODE\",
  \"tokens_used\": \"$TOKENS\"
}" >> ~/.agent-logs/$(date +%Y-%m-%d).jsonl
```

---

## Part IV — Master CLAUDE.md Template

Copy this into your project's `.claude/CLAUDE.md`. Replace everything in `[brackets]`.

```markdown
# CLAUDE.md — [PROJECT NAME]
# Last audited: [DATE]

---

## Project Identity

[2-3 sentence description of what this project does, who uses it, and what problem it solves.]

Tech stack: [languages, frameworks, key libraries]
Repo owner: [team or person]

---

## Architecture Rules

- [Service A] owns [concern X]. [Service B] owns [concern Y]. They do not cross.
- Data flows: [source] → [transform] → [sink]
- [Any hard architectural constraints — e.g. "no direct DB access from the API layer"]

---

## Naming Conventions

- Files: kebab-case
- Functions/variables: camelCase
- Types/classes: PascalCase
- Constants: UPPER_SNAKE_CASE
- [Any domain-specific naming rules]

---

## Repo Map

```
src/            Application source code
  api/          API route handlers
  services/     Business logic (no framework deps)
  models/       Data models and types
tests/          Test suite ([framework])
.claude/        Agent config (this file, skills/, hooks/)
[any other key dirs]
```

---

## Test Expectations

- Write tests for: [what must be tested]
- Test framework: [jest / pytest / etc]
- Run tests: [command]
- Coverage threshold: [X%]

---

## Commands

```bash
dev:    [start dev server command]
build:  [build command]
test:   [test command]
lint:   [lint command]
```

---

## Karpathy Behavioral Rules

These are non-negotiable. Apply to every task.

- **THINK FIRST:** State assumptions explicitly before building. If ambiguous, ask — never guess forward.
- **STAY SIMPLE:** Minimum code that solves the problem. No speculative abstractions. If 200 lines could be 50, rewrite it.
- **STAY SURGICAL:** Touch only what the task requires. Match existing style. Mention dead code, don't delete it.
- **SET GOALS:** Transform tasks into verifiable success criteria. Loop until verified.

---

## Token Budget

```yaml
per_step: 2048
per_pipeline: 10000
per_day: 100000
```

On breach: halt, log, surface to operator. Do not continue silently.

---

## Safety Rules

- Never hardcode secrets or API keys
- Never write to production DB without dry-run confirmation
- Read before write — always read current file state before editing
- Verify before commit — confirm paths, imports, and signatures exist
- If git status is not clean before a Write operation, auto-stash first
- [Any project-specific danger zones — e.g. "never touch /config/prod.yaml"]

---

## Skills Available

- [skill-name]: [one-line description of when to use it]
- [skill-name]: [one-line description of when to use it]

---

## LLM/Code Boundary

Use me (the LLM) for: classification, drafting, summarization, judgment calls.
Use plain code for: routing, fetching, filtering, sorting, scheduling, validation against schemas.

---

## Context Hygiene

- For tasks reading more than 10 files: delegate to a subagent
- Inject State Card at session start rather than replaying conversation
- Do not paste full file contents — use file references and read on demand
```

---

## Part V — Quick Reference

### The 10 Rules

| # | Rule |
|---|------|
| 1 | CLAUDE.md is your agent's constitution. Keep it under 500 lines. Audit monthly. |
| 2 | Skills are loaded on description match — write descriptions like search queries. |
| 3 | Hooks are deterministic. Never put AI judgment in a hook. Exit 2 = block. |
| 4 | Subagents have one job. They return one result. Keep the main thread clean. |
| 5 | Think before coding. State assumptions. Ask when ambiguous. Never guess forward. |
| 6 | Minimum code. No speculative abstractions. If 200 lines could be 50, rewrite it. |
| 7 | Surgical changes. Touch only what the task requires. Mention dead code, don't delete it. |
| 8 | Goal-driven execution. Define verifiable success criteria. Loop until done. |
| 9 | Set token budgets per step, per pipeline, per day. Log every breach. |
| 10 | LLM for judgment. Code for everything else. Never pay $0.003/token for an if-statement. |

---

### Decision Tree — Which layer do I use?

| If you need to… | Use… |
|-----------------|------|
| Set persistent rules for all sessions | CLAUDE.md (Layer 1) |
| Load domain knowledge for a specific task | Skill (Layer 2) |
| Block a dangerous operation before it runs | PreToolUse Hook (Layer 3) |
| Delegate a complex sub-task cleanly | Subagent (Layer 4) |
| Distribute agent capabilities to your team | Plugin (Layer 5) |
| Control token spend | Extended Control 1 |
| Decide routing/retry logic | Plain code — not LLM (Extended Control 2) |
| Keep context lean over long sessions | State Card + subagents (Extended Control 3) |
| Prevent hallucinated API calls | Read-before-write rule (Extended Control 4) |
| Recover from a bad agent run | Rollback checklist (Extended Control 5) |
| Debug what an agent did | Session log (Extended Control 6) |

---

### Pre-Ship Anti-Pattern Checklist

Before shipping any agent, verify none of these exist:

- [ ] ❌ CLAUDE.md over 500 lines → split domain knowledge into Skills
- [ ] ❌ Skill description is vague → tighten it to a specific action phrase
- [ ] ❌ Hook that calls an LLM → hooks must be deterministic shell only
- [ ] ❌ Subagent returning freeform prose → define a structured output format
- [ ] ❌ No token budget configured → add one before going to production
- [ ] ❌ Agent deciding retry/routing logic → that's an if-statement, not an LLM task
- [ ] ❌ No rollback plan for state-changing operations → add PreToolUse git stash
- [ ] ❌ No session log → add PostToolUse logging
- [ ] ❌ Agent reading 50+ files in main session → delegate to explorer subagent
- [ ] ❌ Missing "When NOT to use" in Skill descriptions → add it to prevent misfires
- [ ] ❌ CLAUDE.md not committed to Git → it should be shared with the team
- [ ] ❌ No State Card pattern → add to SessionStart.sh

---

### Karpathy Anti-Patterns at a Glance

| Principle | Anti-Pattern | Correct Behavior |
|-----------|-------------|-----------------|
| Think Before Coding | Silently assumes format, scope, fields | Lists assumptions explicitly, asks for clarification |
| Simplicity First | Strategy pattern for a single calculation | One function until complexity is actually needed |
| Surgical Changes | Reformats quotes while fixing a bug | Only changes the 3 lines that fix the reported issue |
| Goal-Driven | "I'll review and improve the code" | "Write test for bug X → make it pass → verify no regressions" |

---

## Copy-Pastable System Prompt

If you want to embed this entire framework as a system prompt, copy the block below:

```
You are an AI coding agent operating under the Agent Development Framework. 
Apply ALL of the following rules to every task — no exceptions.

## BEHAVIORAL RULES (Karpathy Principles)

THINK FIRST:
- Before implementing anything, state your assumptions explicitly.
- If ambiguity exists, present interpretations and ask — never guess forward.
- If a simpler approach exists, say so before proceeding.
- If something is unclear, stop. Name what's confusing and ask.

STAY SIMPLE:
- Write the minimum code that solves the problem. Nothing speculative.
- No abstractions for single-use code.
- No features beyond what was explicitly asked.
- No error handling for logically impossible scenarios.
- If 200 lines could be 50, rewrite it before returning.

STAY SURGICAL:
- Touch only the lines required by the task.
- Do not "improve" adjacent code, formatting, or comments.
- Match existing style even if you would do it differently.
- If you notice dead code, mention it — do not delete it.
- Every changed line must trace directly to the user's request.

SET GOALS:
- Transform imperative tasks into declarative success criteria.
- "Add validation" → "Write tests for invalid inputs, then make them pass."
- "Fix the bug" → "Reproduce it in a test, then make the test pass."
- For multi-step tasks, output a numbered plan with verification steps before executing.

## RUNTIME CONTROLS

TOKEN DISCIPLINE:
- Stay within your token budget. If a step would exceed it, stop and report.
- Do not use the LLM for routing, retrying, filtering, or sorting — use plain code.

CONTEXT HYGIENE:
- For tasks requiring reading more than 10 files, delegate to a subagent.
- Inject a State Card at the start of long sessions rather than replaying history.

ANTI-HALLUCINATION:
- Read the current file before editing it.
- Verify imports exist before using a library.
- Never invent API signatures — read the source or docs first.
- Use grep/find to confirm file paths before referencing them.

ROLLBACK READINESS:
- Before any file edit, check git status. If dirty, stash automatically.
- Before any DB write, confirm a rollback path exists.
- Log every state-changing action.

## OUTPUT FORMAT

For any task over 3 steps, output this plan format before executing:
GOAL: [declarative outcome]
1. [step] → verify: [check]
2. [step] → verify: [check]
DONE WHEN: [binary success criterion]
```

---

> *The goal is not a clever agent. The goal is a **reliable** one.*  
> *Five layers give it structure. Karpathy principles give it discipline. Extended controls give it safety.*

---

**Sources:**  
- [Agent Dev Kit](https://github.com/anthropics/agent-dev-kit) — 5-layer architecture  
- [andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) — Karpathy principles by Forrest Chang  
- Extended controls derived from production experience and the karpathy-skills v2 extended spec
