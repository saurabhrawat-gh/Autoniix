---
description: Sentry Agent — monitors Slack for Sentry errors, triages into Jira bugs, and auto-fixes via PR
---

> **Source of Truth — LOCKED:**
>
> - Jira **Issue Management (IM)** project (`IM-XXX`) is the **only** active project. All auto-created bugs use `projectKey: IM`; branches use `sentry/im-XXX-autofix`.
> - Jira **Autoniix Engineering (AE)** space is **archived** — never create tickets there.
> - GitHub **Autoniix MVP** project board is **closed** — do not reference it.

## Overview

The Sentry Agent is a persistent Docker service (`services/sentry-agent/`).
It listens to two Slack channels via Socket Mode and runs a fully autonomous fix pipeline.

| Channel            | Priority | Jira Label                | Action                 |
| ------------------ | -------- | ------------------------- | ---------------------- |
| `#alerts-critical` | Highest  | `bug:production + hotfix` | Immediate triage + fix |
| `#alerts-warnings` | High     | `bug:normal`              | Triage + fix           |

---

## Full Pipeline (automatic, no human input required until PR review)

1. Sentry Slack app posts alert to `#alerts-critical` or `#alerts-warnings`
2. Bot detects the Sentry issue URL, deduplicates via Redis fingerprint (7-day TTL)
3. Fetches full issue (stack trace, culprit, occurrence count) from Sentry API
4. Detects layer from stack trace paths (UI / Service / Worker / DB / Auth / Infra)
5. Creates Jira bug `bug | Prod|QA | {Layer} | {title}` with `ready-for-dev` label
6. LLM (gpt-4o-mini) reads the culprit file + stack trace → proposes minimal fix
7. If confidence ≥ medium: creates branch `sentry/im-XXX-autofix`, commits fix, opens PR → `develop`
8. Posts PR link back to the Slack thread and as a Jira comment
9. You review the PR → merge (or close if wrong)

---

## First-Time Setup

### 1. Create Slack App

1. Go to https://api.slack.com/apps → **Create App** → From scratch
2. **Socket Mode** → Enable → generate App-Level Token (scope: `connections:write`) → `SLACK_APP_TOKEN`
3. **OAuth & Permissions** → Bot Token Scopes: `channels:history`, `chat:write`, `groups:history`
4. **Event Subscriptions** → Subscribe to bot events: `message.channels`, `message.groups`
5. **Install to Workspace** → copy Bot User OAuth Token → `SLACK_BOT_TOKEN`
6. Invite the bot to both channels: `/invite @your-bot-name`
7. Right-click each channel → **Copy Channel ID** → fill in `.env`

### 2. Sentry API Token

- sentry.io → Settings → API → Auth Tokens → Create
- Scopes: `event:read`, `issue:read`
- Set `SENTRY_AUTH_TOKEN` in `.env`

### 3. GitHub PAT

- github.com → Settings → Developer settings → Personal access tokens (classic)
- Scopes: `repo` (full), includes PR creation
- Set `GITHUB_TOKEN` in `.env`

### 4. Jira API Token

- id.atlassian.com → Security → API tokens → Create
- Set `JIRA_EMAIL` + `JIRA_API_TOKEN` in `.env`

### 5. Start the service

```bash
docker compose build sentry-agent
docker compose up -d sentry-agent
docker compose logs -f sentry-agent
```

---

## Monitoring

```bash
# Live logs
docker compose logs -f sentry-agent

# Check Redis dedup store
docker compose exec redis redis-cli keys "sentry:dedup:*"

# Manual test — simulate a Sentry Slack message
docker compose exec sentry-agent python -c "
from triage import parse_sentry_slack_message
msg = {'text': '<https://sentry.io/organizations/autoniix/issues/12345/|TypeError: foo is None>', 'bot_id': 'B123'}
print(parse_sentry_slack_message(msg))
"
```

---

## File Map

| File                                     | Purpose                                            |
| ---------------------------------------- | -------------------------------------------------- |
| `services/sentry-agent/bot.py`           | Entry point, Slack event loop                      |
| `services/sentry-agent/sentry_client.py` | Sentry REST API wrapper                            |
| `services/sentry-agent/triage.py`        | Message parsing, layer detection, priority mapping |
| `services/sentry-agent/jira_client.py`   | Jira bug creation + comments                       |
| `services/sentry-agent/github_client.py` | Branch, file, PR via GitHub API                    |
| `services/sentry-agent/fix_agent.py`     | LLM fix generation + commit                        |
| `services/sentry-agent/config.py`        | All env var reads (fails fast if missing)          |

---

## Deduplication

Same Sentry issue arriving multiple times (re-alerts, re-triggers) is suppressed for **7 days** via Redis key `sentry:dedup:{issue_id}`. To force re-process a specific issue:

```bash
docker compose exec redis redis-cli del "sentry:dedup:sentry-issue-{ID}"
```

---

## Human Touchpoints (unchanged — still only 4)

- **PR review**: review the auto-fix PR against `develop` before merging
- **`/verified #N`**: after testing the merged fix in QA/prod

The Sentry Agent does NOT merge anything — it only opens PRs.
