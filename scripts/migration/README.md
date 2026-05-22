# GitHub → Jira/Confluence Migration

One-shot migration of GitHub Issues into Jira project `ATNX` and `docs/wiki/` into Confluence space `ATNX`. Zero impact on the running GitHub-based system.

See `docs/migration/MIGRATION-PLAN.md` for the full plan.

## Prerequisites

1. Atlassian API token saved at `~/.autoniix-atlassian.env` with:
   ```
   ATLASSIAN_EMAIL=you@example.com
   ATLASSIAN_API_TOKEN=ATATT3xFfGF0...
   ATLASSIAN_BASE_URL=https://autoniix.atlassian.net
   ```
2. `gh` CLI authenticated for the GitHub side
3. Python 3.11+ and `pip install -r requirements.txt`

## Scripts (run in order)

| Script | Purpose | Idempotent? |
|---|---|---|
| `00_test_credentials.py` | Read-only auth probe against Jira + Confluence | Yes |
| `01_setup_jira_workflow.py` | Add custom statuses to Kanban workflow | Yes |
| `02_extract_github.py` | Dump all GitHub issues to `state/github_issues.json` | Yes |
| `03_dry_run_jira.py` | Create 3 sample Jira issues for sign-off | No (creates real issues) |
| `04_migrate_jira.py` | Full migration; resumable via `state/id_map.json` | Yes (resumes) |
| `05_confluence_import.py` | Import `docs/wiki/` markdown to Confluence | Yes |
| `99_rollback.py` | Bulk-delete every Jira issue listed in `id_map.json` | Yes |

## State Files (gitignored)

| File | Purpose |
|---|---|
| `state/github_issues.json` | Source-of-truth snapshot from GitHub |
| `state/id_map.json` | `{ "GH-47": "ATNX-12", ... }` for resume + rollback |
| `state/migration.log` | Detailed run log |
