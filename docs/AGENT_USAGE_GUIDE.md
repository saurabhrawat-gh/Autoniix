# Agent Framework Usage Guide

> Everything you need to know to get maximum value from the agent framework in Windsurf — shortcuts, global vs project scope, adding new agents/rules/workflows, and cross-project reuse.

---

## 1. Global vs Project-Specific — What Lives Where

### The Two Scopes

| Scope | Location | When It Loads | What Goes Here |
|-------|----------|--------------|----------------|
| **Project** | `<project>/.windsurf/` | Only when that project is open | Project-specific architecture, naming, repo maps, domain skills |
| **Global** | `~/.windsurf/` | For every project, every session | Your personal coding style, universal shortcuts, cross-project agents |

### Current Setup (Project-Specific)

Everything we built lives in the **project scope**:

```
youtube-automation/
├── .windsurf/
│   ├── rules/          ← Auto-loaded for THIS project only
│   ├── skills/         ← On-demand for THIS project only
│   └── workflows/      ← Slash-commands for THIS project only
├── .claude/
│   └── CLAUDE.md       ← Claude Code CLI compat for THIS project
└── subagents/          ← Agent specs for THIS project
```

### What Should Be Global

Create these once, use in every project:

```
~/.windsurf/
├── rules/
│   ├── coding-style.md        ← Your personal coding preferences
│   ├── safety-universal.md    ← Karpathy principles (same for all projects)
│   └── git-conventions.md     ← Commit message format, branch naming
├── skills/
│   ├── python-patterns.md     ← Python best practices you always want
│   ├── debugging.md           ← Debugging methodology
│   └── api-design.md          ← REST API design principles
├── workflows/
│   ├── pre-commit.md          ← Universal pre-commit checks
│   └── diff-review.md         ← Universal diff review
└── subagents/
    ├── code-reviewer.md       ← Generic code reviewer
    └── test-runner.md         ← Generic test runner
```

### How Scopes Merge

When you open a project, Windsurf loads **both**:

```
Global rules  +  Project rules  →  Combined context for Cascade
Global skills +  Project skills →  All available on demand
Global workflows + Project workflows → All slash-commands available
```

If there's a conflict (e.g., global says "use double quotes", project says "use single quotes"), **project scope wins** — it's more specific.

---

## 2. All Shortcuts & Syntax

### `@` — Context Injection

Type `@` in the Cascade chat to inject file content into the conversation.

| What you type | What happens |
|---------------|-------------|
| `@.windsurf/skills/script-intelligence.md` | Loads that skill file as context |
| `@subagents/intelligence-engineer.md` | Loads the agent spec as context |
| `@src/services/script/main.py` | Loads a source file as context |
| `@docs/01-ARCHITECTURE.md` | Loads a doc file as context |

**Pro tip:** You can chain multiple `@` mentions:
```
@.windsurf/skills/provider-pattern.md @subagents/api-designer.md
Add a Groq LLM provider to the system.
```

### `/` — Workflow Slash-Commands

Type `/` in the Cascade chat to invoke a workflow.

| Command | What it runs | When to use |
|---------|-------------|-------------|
| `/pre-commit` | Lint, test, secret scan, diff scope check | Before every commit |
| `/quality-check` | Validate against quality gate thresholds | After modifying scoring/thresholds |
| `/safety-audit` | Scan for secrets, missing error handling | Periodically or before production deploy |
| `/context-hygiene` | Summarize session into State Card | When session gets long |
| `/diff-review` | Review git diff for surgical compliance | After making code changes |

**Pro tip:** Workflows with `// turbo` annotated steps auto-run those commands without asking your permission.

### `#` — Memory References

Type `#` to reference memories you've saved to Cascade's memory database.

### File Path Autocomplete

Start typing a path and Windsurf will autocomplete. Works for:
- `.windsurf/rules/*.md`
- `.windsurf/skills/*.md`
- `.windsurf/workflows/*.md`
- `subagents/*.md`
- Any file in the project

---

## 3. How Each Layer Works — Practical Usage

### Layer 1: Rules (Auto-Loaded)

**How it works:** Every `.md` file in `.windsurf/rules/` is automatically read by Cascade at the start of every session. You never need to `@`-mention them.

**Current rules:**
- `architecture.md` — Service catalog, data flow, hard constraints
- `naming-conventions.md` — Python, provider, temporal, DB naming
- `repo-map.md` — Directory structure, key files
- `testing.md` — pytest patterns, coverage targets
- `safety.md` — Karpathy principles, anti-hallucination, rollback
- `llm-code-boundary.md` — When to use LLM vs code

**You don't need to do anything** — Cascade already knows all of this. Just start coding and it will follow these rules.

### Layer 2: Skills (On-Demand)

**How it works:** Skills are NOT auto-loaded. You load them when needed by `@`-mentioning them.

**When to load a skill:**
- You're about to work on a domain you're unfamiliar with
- You want Cascade to follow project-specific patterns
- You need reference data (port numbers, table names, etc.)

**Example usage:**
```
@.windsurf/skills/temporal-workflows.md
Add a new activity for subtitle generation to the video production workflow.
```

Cascade now knows the workflow patterns, retry policies, and activity registration rules.

### Layer 3: Workflows (Slash-Commands)

**How it works:** Type `/` in the chat to see available workflows. Select one to execute its steps.

**Example:**
```
/pre-commit
```
Cascade will run linting, tests, secret scanning, and diff scope checks.

### Layer 4: Subagents (Specialist Delegation)

**How it works:** Subagents are NOT built into Windsurf. They're **reference specs** that you use to give Cascade a specialist role.

**Three ways to use them:**

**Method 1: @-mention in current session**
```
@subagents/intelligence-engineer.md
Add sentiment arc scoring to the retention optimizer.
Constraints: local-only, integrate with GBM features.
```

**Method 2: Open a new Cascade tab**
1. Click `+` to open a new Cascade chat tab
2. Paste: `@subagents/code-reviewer.md Review the following diff for surgical compliance: [paste diff]`
3. The new tab acts as a specialist with focused context

**Method 3: Reference in conversation**
```
Act as the Intelligence Engineer agent defined in subagents/intelligence-engineer.md.
Your task: Add burst detection to the delivery service.
```

---

## 4. Efficient Usage Patterns

### Pattern: Start Every Session Right

When you open a new Cascade session:

1. **Rules are already loaded** — no action needed
2. **State your task clearly** — "Add X to Y service"
3. **Load 1-2 relevant skills** — `@.windsurf/skills/<relevant>.md`
4. **If complex, load an agent spec** — `@subagents/<relevant>.md`

**Example:**
```
@.windsurf/skills/provider-pattern.md
Add a Groq LLM provider. It should use the OpenAI-compatible API format
with base_url https://api.groq.com/openai/v1.
```

### Pattern: Use Workflows as Guardrails

Don't skip the workflows. They're your safety net:

- **Before committing:** `/pre-commit`
- **After editing:** `/diff-review`
- **Before production deploy:** `/safety-audit`
- **When session gets long:** `/context-hygiene`

### Pattern: Delegate, Don't Accumulate

If you find yourself reading 10+ files in one session:

1. `/context-hygiene` — summarize into State Card
2. Start a fresh tab for the next sub-task
3. Paste the State Card as context in the new tab

### Pattern: The 3-File Rule

For any single task, try to keep active context to:
- 1 rules file (auto-loaded)
- 1 skill file (@-mentioned)
- 1-2 source files (being edited)

If you need more, delegate to a specialist tab.

---

## 5. Cross-Project Reuse

### How to Reuse in Other Projects

**Option A: Copy the global parts**

```bash
# Create global rules (work for all projects)
mkdir -p ~/.windsurf/rules ~/.windsurf/skills ~/.windsurf/workflows ~/.windsurf/subagents

# Copy universal rules
cp .windsurf/rules/safety.md ~/.windsurf/rules/
cp .windsurf/rules/testing.md ~/.windsurf/rules/
cp .windsurf/rules/llm-code-boundary.md ~/.windsurf/rules/

# Copy universal workflows
cp .windsurf/workflows/pre-commit.md ~/.windsurf/workflows/
cp .windsurf/workflows/diff-review.md ~/.windsurf/workflows/
cp .windsurf/workflows/context-hygiene.md ~/.windsurf/workflows/
cp .windsurf/workflows/safety-audit.md ~/.windsurf/workflows/

# Copy universal agents
cp subagents/code-reviewer.md ~/.windsurf/subagents/
cp subagents/test-runner.md ~/.windsurf/subagents/
cp subagents/explorer.md ~/.windsurf/subagents/
```

**Option B: Create a template repo**

Create a GitHub repo called `my-agent-framework` with the structure:

```
my-agent-framework/
├── global/                 ← Copy to ~/.windsurf/
│   ├── rules/
│   ├── skills/
│   ├── workflows/
│   └── subagents/
├── project-template/       ← Copy to <new-project>/.windsurf/
│   ├── rules/
│   │   ├── architecture.md.template
│   │   ├── naming-conventions.md.template
│   │   └── repo-map.md.template
│   ├── skills/
│   └── workflows/
└── setup.sh               ← Script that copies + customizes
```

**Option C: Per-project customization**

For each new project, you only need to customize:
- `.windsurf/rules/architecture.md` — That project's service catalog
- `.windsurf/rules/repo-map.md` — That project's directory structure
- `.windsurf/rules/naming-conventions.md` — If different from default
- `.windsurf/skills/` — Domain-specific skills for that project

Everything else (safety, testing, workflows, generic agents) can be global.

---

## 6. Adding New Rules, Skills, Workflows, and Agents

### Adding a New Rule

**Project-specific:**
```bash
# Create the file
cat > .windsurf/rules/my-new-rule.md << 'EOF'
# My New Rule

[Your rule content here — keep under 100 lines]
EOF
```
It will auto-load in the next session.

**Global:**
```bash
cat > ~/.windsurf/rules/my-global-rule.md << 'EOF'
# My Global Rule

[Rule that applies to all your projects]
EOF
```

**Best practices for rules:**
- Keep each file under 100 lines
- Use tables and bullet points — Cascade skims prose
- Be imperative: "Always X", "Never Y", "If Z then W"
- Audit monthly — stale rules create wrong behavior

### Adding a New Skill

**Project-specific:**
```bash
cat > .windsurf/skills/my-new-skill.md << 'EOF'
# Skill: My New Skill

**Use when:** [Specific trigger — when should Cascade load this?]

**When NOT to use:** [Prevent false-positive matching]

---

[Domain knowledge content]
EOF
```

**Global:**
```bash
cat > ~/.windsurf/skills/my-global-skill.md << 'EOF'
# Skill: Python Async Patterns

**Use when:** Writing async Python code with asyncio, aiohttp, or asyncpg.

**When NOT to use:** Synchronous Python code.

---

[Content about async patterns]
EOF
```

**Best practices for skills:**
- The "Use when" description is critical — treat it like a search query
- Always include "When NOT to use" to prevent false matches
- Include concrete code examples, not just theory
- Reference specific file paths in the project (for project skills)

### Adding a New Workflow

**Project-specific:**
```bash
cat > .windsurf/workflows/my-workflow.md << 'EOF'
---
description: My workflow — short description shown in slash menu
---

# My Workflow

[Steps to execute]

1. Do X
   // turbo
   command-to-run

2. Do Y
EOF
```

**Global:**
```bash
cat > ~/.windsurf/workflows/my-global-workflow.md << 'EOF'
---
description: Global workflow — description
---

# Global Workflow

[Steps]
EOF
```

**The `// turbo` annotation:** Add `// turbo` on the line before a command step to make it auto-run without asking permission. Only use for safe, read-only commands.

### Adding a New Agent

**Project-specific:**
```bash
cat > subagents/my-new-agent.md << 'EOF'
# Subagent: My New Agent

## Role
[One paragraph describing what this agent specializes in]

## Context Loading
- `.windsurf/skills/xyz.md` — [why]
- `.windsurf/rules/abc.md` — [why]

## Input Format
```json
{
  "task": "...",
  "constraints": ["..."]
}
```

## Output Format
```json
{
  "result": "...",
  "files_modified": ["..."],
  "issues": ["..."]
}
```

## Constraints
- [What this agent must NOT do]
- [Safety boundaries]
EOF
```

**Global:**
```bash
mkdir -p ~/.windsurf/subagents
cat > ~/.windsurf/subagents/my-global-agent.md << 'EOF'
# Subagent: Generic Code Reviewer

## Role
[Works for any Python project]

[... same format as above ...]
EOF
```

**Best practices for agents:**
- Define a **structured output format** — freeform prose is hard to compose
- Specify **which context files** the agent should load
- Set clear **constraints** — what it must NOT do
- Keep the spec under 100 lines — the agent reads it as context

---

## 7. Where Are the Agents & How to Make Them Work

### Current Agent Locations

| Agent | Location | Scope |
|-------|----------|-------|
| Code Reviewer | `subagents/code-reviewer.md` | Project |
| Test Runner | `subagents/test-runner.md` | Project |
| Explorer | `subagents/explorer.md` | Project |
| Intelligence Engineer | `subagents/intelligence-engineer.md` | Project |
| Infra Engineer | `subagents/infra-engineer.md` | Project |
| API Designer | `subagents/api-designer.md` | Project |

### How to Activate an Agent for a Task

**Step 1:** Decide which agent fits your task (see table below).

**Step 2:** Open a Cascade chat and load the agent:
```
@subagents/intelligence-engineer.md
Add burst detection to the delivery service's SEO optimizer.
```

**Step 3:** The agent spec tells Cascade:
- What role to assume
- What context files to know about
- What output format to use
- What constraints to follow

**Step 4:** Cascade responds as that specialist, following the spec.

### Which Agent for Which Task

| Task | Agent | How to Invoke |
|------|-------|--------------|
| Review code before commit | Code Reviewer | `@subagents/code-reviewer.md` then paste diff |
| Run tests & analyze failures | Test Runner | `@subagents/test-runner.md` then specify test paths |
| Map an unfamiliar code area | Explorer | `@subagents/explorer.md` then specify the area |
| Add ML/NLP/scoring logic | Intelligence Engineer | `@subagents/intelligence-engineer.md` + `@.windsurf/skills/script-intelligence.md` |
| Docker/Temporal/infra changes | Infra Engineer | `@subagents/infra-engineer.md` + `@.windsurf/skills/docker-infrastructure.md` |
| Design new API endpoints | API Designer | `@subagents/api-designer.md` |

### Making Agents Work Together

For complex tasks, use **sequential delegation** in separate tabs:

```
Tab 1 (Orchestrator): Plans the work, coordinates
Tab 2 (Explorer): Maps the codebase area → returns file summary
Tab 3 (Implementer): Writes the code → returns diff
Tab 4 (Reviewer): Reviews the diff → returns approval/issues
```

Pass **structured results** between tabs, not raw conversation.

---

## 8. Quick Reference Card

### Shortcuts

| Shortcut | Purpose | Example |
|----------|---------|---------|
| `@file` | Inject file as context | `@.windsurf/skills/provider-pattern.md` |
| `/command` | Run a workflow | `/pre-commit` |
| `#memory` | Reference a saved memory | `#project-architecture` |

### File Locations

| Type | Project | Global |
|------|---------|--------|
| Rules | `.windsurf/rules/*.md` | `~/.windsurf/rules/*.md` |
| Skills | `.windsurf/skills/*.md` | `~/.windsurf/skills/*.md` |
| Workflows | `.windsurf/workflows/*.md` | `~/.windsurf/workflows/*.md` |
| Agents | `subagents/*.md` | `~/.windsurf/subagents/*.md` |
| Claude Code | `.claude/CLAUDE.md` | `~/.claude/CLAUDE.md` |

### Loading Behavior

| Type | When Loaded | How |
|------|------------|-----|
| Rules | Every session start | Automatic |
| Skills | When you `@`-mention | Manual |
| Workflows | When you type `/` | Manual |
| Agents | When you `@`-mention spec | Manual |
| CLAUDE.md | Every session start (Claude Code) | Automatic |

### Priority: Project > Global

If both project and global have a file with the same name, **project wins**. This lets you override global defaults per-project.

---

## 9. Next Steps — Set Up Global Rules

To get the most out of this framework across ALL your projects, create the global files now:

```bash
# 1. Create global directories
mkdir -p ~/.windsurf/{rules,skills,workflows,subagents}

# 2. Copy universal rules from this project
cp .windsurf/rules/safety.md ~/.windsurf/rules/
cp .windsurf/rules/llm-code-boundary.md ~/.windsurf/rules/
cp .windsurf/rules/testing.md ~/.windsurf/rules/

# 3. Copy universal workflows
cp .windsurf/workflows/pre-commit.md ~/.windsurf/workflows/
cp .windsurf/workflows/diff-review.md ~/.windsurf/workflows/
cp .windsurf/workflows/context-hygiene.md ~/.windsurf/workflows/
cp .windsurf/workflows/safety-audit.md ~/.windsurf/workflows/

# 4. Copy universal agents
cp subagents/code-reviewer.md ~/.windsurf/subagents/
cp subagents/test-runner.md ~/.windsurf/subagents/
cp subagents/explorer.md ~/.windsurf/subagents/

# 5. Create your personal coding style rule
cat > ~/.windsurf/rules/coding-style.md << 'EOF'
# My Coding Style

- I prefer detailed explanations when I ask "why"
- I like to see the plan before implementation
- I prefer minimal diffs — surgical changes only
- I use Python 3.11+ with type hints in new files
- I prefer structlog over logging
- Commit messages: conventional commits (feat:, fix:, docs:, etc.)
EOF
```

After this, every project you open in Windsurf will have your universal rules, workflows, and agents available automatically.
