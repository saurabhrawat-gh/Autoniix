---
description: DevOps Agent — handle deploy, incident, infra changes, DNS, scaling, secrets audit, and rollback for the Autoniix stack
---

# DevOps Agent Workflow

Use this workflow for any infrastructure, deployment, or operations task. Invoke as `/devops-agent {task}` where task is one of: `deploy`, `incident`, `infra`, `dns`, `scale`, `rollback`, `audit`.

---

## Capability Matrix

| Domain | What The Agent Does | Tool Used |
|---|---|---|
| Local stack | `docker compose up/down/restart/scale`, logs, health | `run_command` |
| Infra-as-code | Edit `docker-compose.yml`, `Caddyfile`, `prometheus.yml`, `alertmanager.yml`, `ci.yml` | file edit |
| Database | Run pending migrations, trigger backup, verify restore | `run_command` |
| DNS | Read / add / update / delete DNS records for autoniix.com | Hostinger MCP |
| VPS | Start / stop / restart VPS, fetch CPU/memory/disk/network metrics | Hostinger MCP |
| CI/CD | Create / update GitHub Actions workflows, manage repo secrets | GitHub MCP |
| Security | Secret scan, `.env` drift audit, `pip-audit` dependency scan | `run_command` + grep |
| Monitoring | Add Prometheus scrape targets, update alert rules, verify Grafana | file edit + `run_command` |
| Incident | Diagnose → restart → escalate or rollback | `run_command` + Hostinger MCP |
| Deployment | Pre-deploy gate, build validation, smoke test, rollback | `run_command` + GitHub MCP |

**How deploys actually happen:**
- Production deploys are **fully automated** via a self-hosted GitHub Actions runner on the VPS. Merging a PR to `main` triggers `deploy` in `ci.yml`, which `git reset --hard origin/main` + `docker compose --profile tls up -d --build` on the VPS.
- The agent **never** runs `ssh` for routine deploys — it merges the PR via GitHub MCP and watches the Actions run.
- SSH to the VPS is only used during `incident` / `rollback` triage when the runner itself is broken.
- Grafana/Prometheus UIs are not directly accessible — agent configures their YAML files.

---

## Task: `deploy`

**Pipeline reality (do not bypass):** A self-hosted GitHub Actions runner lives on the VPS. The `deploy` job in `.github/workflows/ci.yml` fires automatically on every `push` to `main` (gated by `github.event_name == 'push' && github.ref == 'refs/heads/main'`). PRs do **not** trigger deploy — this is by design.

Therefore the deploy task is **not "SSH and pull"** — it is **"merge the PR and verify the auto-deploy"**.

Use this task after the user signals `ready-to-merge` (or after the develop→main PR has all green CI checks and user approval).

```
1. Pre-merge gate — verify the open develop→main PR is mergeable:
   a. List open PRs targeting main:
      mcp0_list_pull_requests(owner=..., repo=..., state=open, base=main)
   b. For each PR, fetch status:
      mcp0_get_pull_request_status(... pull_number=N)
   c. Confirm ALL required checks are green:
        - Python — lint + unit tests
        - Remotion — typecheck
        - Dashboard — typecheck + UI token lint
        - Security — pip-audit + SBOM
        - E2E — render smoke
      The `Deploy — VPS (main push only)` job MUST be skipped (this is expected — it only runs after merge).
   d. If any check failed, STOP. Report which check, link to logs, recommend fix.

2. Merge the PR (squash or merge per repo convention):
   mcp0_merge_pull_request(owner=..., repo=..., pull_number=N, merge_method='merge')

3. Watch the post-merge deploy run:
   a. Poll mcp0_list_commits(sha='main') for the merge commit SHA.
   b. Open the Actions run for that SHA in the browser (or report the URL):
      https://github.com/{owner}/{repo}/actions
   c. Wait until the `Deploy — VPS (main push only)` job either succeeds or fails.

4. Post-deploy verification (the workflow already runs `Post-deploy smoke`, but double-check):
   a. curl -sf https://api.autoniix.com/health | jq .
   b. curl -sf https://dash.autoniix.com | grep -q "Autoniix"
   c. Optional: SSH to VPS only if smoke fails, to inspect logs.

5. On deploy failure:
   - Read the Actions run logs (mcp0 has no direct log-fetch — surface the URL).
   - If a transient infra issue, re-run the job via the Actions UI.
   - If a code issue, run the `rollback` task (see below) and open a hotfix issue.

6. Update GitHub issue labels for every issue in the merged delta:
   Remove: ready-to-merge
   Add: in-prod
   Comment: "Deployed to production. Smoke tests passed."
```

---

## Task: `incident`

Use when a container is down, errors spiking, or DB unreachable.

```
1. Identify unhealthy containers:
   docker compose ps --format json

2. Check logs for the failing service:
   docker logs autoniix-{service}-1 --tail 100 --timestamps

3. Check VPS resource pressure (Hostinger MCP):
   mcp1_VPS_getMetricsV1 — CPU, memory, disk for last 30 min

4. Decision tree:
   OOM (container exits with code 137):
     → Edit docker-compose.yml: increase mem_limit for the service
     → docker compose up -d --no-deps {service}

   DB connection refused:
     → docker compose restart postgres-app
     → Check disk space (df -h)

   Temporal worker not processing:
     → docker compose logs worker-production --tail 50
     → docker compose restart worker-production

   Redis connection error:
     → docker compose restart redis
     → Wait 10s, restart dependent services

   Queue depth backing up (Temporal):
     → docker compose scale worker-production=2

5. Post-fix verification:
   docker compose ps → all healthy
   Run smoke test: make smoke

6. If unresolvable:
   a. Emergency stop via dashboard: POST /api/v2/system/emergency-stop
   b. Output rollback procedure (see rollback task)
   c. Create GitHub issue: label hotfix, post-mortem
```

---

## Task: `infra`

Use when a new service is added or an existing one is significantly changed.

```
1. Update docker-compose.yml if new service:
   - Add service block with correct mem_limit, restart policy, healthcheck, network
   - Add to autoniix-net network

2. Update prometheus.yml — add scrape target:
   - job_name: {service}
     static_configs:
       - targets: ['{service}:{port}']

3. Update Caddyfile — add reverse proxy block if externally accessible:
   {subdomain}.autoniix.com {
     reverse_proxy {service}:{port}
   }

4. Update alertmanager.yml if the service needs alerting rules

5. Update .env.example if new env vars introduced

6. Update docs/DEPLOYMENT-GUIDE.md service list

7. Run: docker compose config --quiet (validate syntax)

8. Commit all infra changes together:
   git commit -m "infra: add {service} to stack"
```

---

## Task: `dns`

Use to manage autoniix.com DNS records.

```
1. Read current records:
   mcp1_DNS_getDNSRecordsV1 for domain: autoniix.com

2. Apply requested change:
   mcp1_DNS_updateDNSRecordsV1 — add/update A, CNAME, TXT record

3. Verify after ~5 min:
   nslookup {subdomain}.autoniix.com 8.8.8.8
   # Should resolve to 187.127.155.126

4. Standard record set for Autoniix:
   @ A → 187.127.155.126 (apex)
   dash A → 187.127.155.126
   api A → 187.127.155.126
   grafana A → 187.127.155.126
   prometheus A → 187.127.155.126
   alerts A → 187.127.155.126
   temporal A → 187.127.155.126
```

---

## Task: `scale`

Use to adjust container resource limits or replica count.

```
1. Edit docker-compose.yml:
   services:
     {service}:
       deploy:
         resources:
           limits:
             memory: {new_limit}

2. Apply without downtime:
   docker compose up -d --no-deps {service}

3. Verify:
   docker stats {container_name} --no-stream
```

---

## Task: `rollback`

Use when a deploy causes production issues.

```
1. Find last stable commit:
   git log --oneline -10

2. Output rollback commands:
   ssh -p 2222 -i ~/.ssh/id_ed25519_autoniix autoniix@187.127.155.126
   cd ~/autoniix
   git fetch origin
   git checkout {stable_commit_sha}
   docker compose --profile tls up -d --build

3. If DB migration was part of the deploy:
   # Migrations are NOT auto-reversed — document manual rollback SQL in the issue

4. Update GitHub issue:
   Add label: rolled-back
   Comment: "Rolled back to {commit}. Root cause: {reason}. Fix tracked in #{new_issue}."
```

---

## Task: `audit` (run weekly or before major deploy)

```
1. Secret scan:
   grep -rn "api_key\s*=\s*['\"]" src/ --include="*.py" | grep -v "settings\." | grep -v ".example"
   grep -rn "password\s*=\s*['\"]" src/ --include="*.py" | grep -v "settings\."
   grep -rn "CHANGE_ME" . --include="*.env*" --include="*.yml"

2. .env drift check:
   diff <(grep -v '^#' .env.example | grep '=' | cut -d= -f1 | sort) \
        <(grep -v '^#' .env | grep '=' | cut -d= -f1 | sort)
   # Keys in .env.example but missing from .env = deployment risk

3. Dependency vulnerability scan:
   pip-audit --output json 2>/dev/null | jq '.dependencies[] | select(.vulns | length > 0)'

4. DB backup verification:
   ls -lh ~/backups/ | tail -5
   # Last backup should be < 24h old

5. VPS metrics check (Hostinger MCP):
   mcp1_VPS_getMetricsV1 — disk usage should be < 80%

6. Certificate check (Caddy auto-renews, just verify):
   curl -vI https://dash.autoniix.com 2>&1 | grep "expire date"

7. If any critical finding:
   mcp0_create_issue — label: security or hotfix
```

---

## DevOps Agent Position in SDLC

```
/ba-agent    → Epic + Stories  (label: ready-for-qa)
     ↓
/qa-agent    → Test-case issues  (label: ready-for-dev)
     ↓
/dev-agent   → Implements  (label: in-progress → dev-done)
     ↓
You          → Merge PR to bug-fixes/main
     ↓
/devops-agent deploy
     → pre-flight checks
     → copy-pasteable prod commands
     → smoke test after you confirm deploy
     → label: in-prod
     ↓
You          → verify in prod  (label: prod-verified)
     ↓
/devops-agent close
     → mcp0_update_issue → state: closed
     → comment: "Verified in production. Closing."
```
