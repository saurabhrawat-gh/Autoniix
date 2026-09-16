---
description: DevOps Agent — handle deploy, incident, infra changes, DNS, scaling, secrets audit, and rollback for the Autoniix stack
---

# DevOps Agent Workflow

> **🚫 BUILD FREEZE — until 2026-07-11**
> No deploys, no pushes to `main`, no PR merges to `main` of any kind until the freeze lifts.
> If asked to deploy before 2026-07-11, STOP and reply: "Build freeze in effect until 2026-07-11. I cannot deploy or push to main."
> After 2026-07-11 the user will explicitly say "freeze lifted" or "deploy" to resume.

Use this workflow for any infrastructure, deployment, or operations task. Invoke as `/devops-agent {task}` where task is one of: `deploy`, `incident`, `infra`, `dns`, `scale`, `rollback`, `audit`.

---

## Capability Matrix

| Domain        | What The Agent Does                                                                    | Tool Used                     |
| ------------- | -------------------------------------------------------------------------------------- | ----------------------------- |
| Local stack   | `docker compose up/down/restart/scale`, logs, health                                   | `run_command`                 |
| Infra-as-code | Edit `docker-compose.yml`, `Caddyfile`, `prometheus.yml`, `alertmanager.yml`, `ci.yml` | file edit                     |
| Database      | Run pending migrations, trigger backup, verify restore                                 | `run_command`                 |
| DNS           | Read / add / update / delete DNS records for autoniix.com                              | Hostinger MCP                 |
| VPS           | Start / stop / restart VPS, fetch CPU/memory/disk/network metrics                      | Hostinger MCP                 |
| CI/CD         | Create / update GitHub Actions workflows, manage repo secrets                          | GitHub MCP                    |
| Security      | Secret scan, `.env` drift audit, `pip-audit` dependency scan                           | `run_command` + grep          |
| Monitoring    | Add Prometheus scrape targets, update alert rules, verify Grafana                      | file edit + `run_command`     |
| Incident      | Diagnose → restart → escalate or rollback                                              | `run_command` + Hostinger MCP |
| Deployment    | Pre-deploy gate, build validation, smoke test, rollback                                | `run_command` + GitHub MCP    |

**How deploys actually happen:**

- Production deploys are triggered by a push to `main`. The self-hosted GitHub Actions runner on the VPS runs `git reset --hard origin/main` + `docker compose --profile tls up -d --build` when `ci.yml` detects a push to `main`.
- **`main` is promoted manually by the product owner** (`git checkout main && git merge --no-ff develop && git push origin main`). No agent or GHA automation pushes to `main`.
- The devops-agent **never** merges or creates PRs to `main`. It only monitors GHA once the product owner has already pushed.
- SSH to the VPS is only used during `incident` / `rollback` triage when the runner itself is broken.
- Grafana/Prometheus UIs are not directly accessible — agent configures their YAML files.

---

## Task: `deploy` (monitoring + verification only)

**How deploys work:**
Deploys are triggered manually by the product owner pushing `main`. When they do:

1. The self-hosted runner on the VPS detects the push and runs `docker compose up -d --build`
2. GitHub Actions sets `in-prod` on all deployed issues (if auto-lifecycle.yml is configured)

**Your role:** Monitor that the above happened correctly and verify the smoke test. You are invoked AFTER the product owner has pushed `main`.

````
1. Check GitHub Actions for the latest deploy run:
   - URL: https://github.com/saurabhrawat-gh/Autoniix/actions
   - Look for the "Deploy — VPS (main push only)" job
   - If it succeeded → proceed to step 2
   - If it failed → run the `incident` task

2. Post-deploy smoke check:
   a. curl -sf https://api.autoniix.com/health | jq .
   b. curl -sf https://dash.autoniix.com | grep -q "Autoniix"
   c. If either fails → run the `incident` task immediately

3. If GHA did not update issue labels after the deploy:
   a. Check that main was actually pushed (`git log origin/main -1`)
   b. Check the ci.yml Actions run for errors
   c. If GHA failed to set labels, manually update them (step 4 below) — do NOT create or merge a PR to main

4. On deploy success — update GitHub issues AND Jira (if GHA didn't already):
   - Fetch all issues with label `ready-to-deploy` (if GHA didn't set in-prod yet)
   - For each:
     a. `mcp0_update_issue` — remove `ready-to-deploy`, add `in-prod`
     b. Look up the Jira key from `scripts/issue_map.json` (key = GitHub issue number)
     c. `mcp0_transitionJiraIssue` with cloudId `73672c49-7089-4f35-adde-e3fa0d1e438f`, issueIdOrKey = Jira key, transition id `41` (→ In Prod)
     d. Post comment: "Deployed to production. When you have verified, type `verified #N` in Windsurf — agent will tick all ACs and close automatically."

5. Emit HandoffPayload:
```yaml
handoff:
  from_team: devops
  to_team: human
  issue: {N}
  summary: "Deploy successful. Smoke tests passed. Issues set to in-prod."
  risk_level: low
  actions_pending:
    - "Product owner: verify on https://dash.autoniix.com"
    - "Product owner: type `verified #N` when confirmed"
  blockers: []
````

---

## Task: `hotfix-deploy`

Use when a `bug:production` or `hotfix` issue was fixed by the dev agent (merged to `develop`) and the product owner has manually pushed `main`.

```
1. Verify the main push triggered CI:
   - Check GitHub Actions — look for the "Deploy — VPS (main push only)" job
   - It will fire because the product owner pushed main

2. Same smoke checks as `deploy` task (steps 2–3 above)

3. Verify develop is up to date:
   # turbo
   - git log develop --oneline -5
   - The hotfix commit should appear (dev agent merged to develop as part of H6)

4. The issue should already be labelled `in-prod` by the dev agent (step H8)
   - If not: mcp0_update_issue — add `in-prod`
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

7. # turbo
   Run: docker compose config --quiet (validate syntax)

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
   # turbo
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
   # turbo
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
1. # turbo
   Secret scan:
   grep -rn "api_key\s*=\s*['\"]" src/ --include="*.py" | grep -v "settings\." | grep -v ".example"
   grep -rn "password\s*=\s*['\"]" src/ --include="*.py" | grep -v "settings\."
   grep -rn "CHANGE_ME" . --include="*.env*" --include="*.yml"

2. # turbo
   .env drift check:
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
/ba-agent      → Epic + Stories created  (label: ready-for-qa)
     ↓
/qa-agent      → Test-case issues created  (label: ready-for-dev)
     ↓
/dev-agent     → Implements → merges to develop  (label: in-qa)
     ↓
/qa-agent      → Walks test cases with you  (label: qa-verified on pass)
     ↓
Product owner → promotes develop→main manually when ready to deploy
     ↓
[GHA/DevOps]   → Deploy succeeds → in-prod (GitHub) + In Prod (Jira transition id:6)
     ↓
You            → verify on https://dash.autoniix.com
     ↓
You            → type `verified #N` → agent ticks ACs, transitions Jira → Done, closes issue

HOTFIX PATH:
/dev-agent     → Implements → merges to develop  (label: ready-to-deploy, Jira: Ready To Deploy)
     ↓
Product owner  → promotes develop→main manually
     ↓
[GHA/DevOps]   → CI deploys → in-prod
     ↓
You            → verify → `verified #N` → GHA closes

/devops-agent  → Monitors deploys, handles incidents, infra changes, rollbacks
               → Called when: deploy fails, service goes down, DNS change needed, scale needed
```
