---
description: Create or re-sync all IM Jira sprints and assign issues to them
---

## Prerequisites
- `requests` installed: `pip install requests`
- Jira API token from https://id.atlassian.com/manage-profile/security/api-tokens

## Run

```bash
JIRA_EMAIL="admin@autoniix.com" \
JIRA_TOKEN="<your_token>" \
python3 scripts/create_sprints.py
```

## What the script does
1. Finds the IM Scrum board via `GET /rest/agile/1.0/board?projectKeyOrId=IM`
2. Creates all 38 sprint containers (Core 1–7, Pipeline 1–9, Feature 18×, Infra 4×)
3. Moves every Epic, Story, and Bug into its correct sprint

## Sprint → Issue mapping (source of truth)
See `scripts/create_sprints.py` — the `SPRINTS` list is the single source of truth.
To add new issues to an existing sprint, edit that list and re-run (the API is idempotent for issue moves).

## Board URL
https://autoniix.atlassian.net/jira/software/c/projects/IM/boards/35/backlog
