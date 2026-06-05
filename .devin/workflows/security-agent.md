---
description: Security Agent — scans every diff for hardcoded secrets, vulnerable dependencies, and policy violations before code merges. Runs after Dev Team, before QA Mode B.
---

# Security Agent Workflow

The Security Agent runs after every Dev Team implementation and before QA Mode B testing. It ensures no security issue reaches testing or production.

**Usage:**
```
/security-agent #N           — scan the diff for a specific issue branch
/security-agent audit        — full periodic security audit (no specific issue)
```

---

## Team Structure

- **Security Lead** — orchestrates scanning, writes the final security report, decides risk level
- **Secret Scanner** — scans all changed files for hardcoded credentials, API keys, tokens, and PII
- **Dep Scanner** — audits all dependency files for known CVEs and outdated packages
- **Policy Enforcer** — checks code against the Autoniix security policy checklist

---

## Step 1 — Security Lead: Orient

1. Call `mcp0_get_issue` to read the issue
2. Read the HandoffPayload from Dev Team (posted as a comment: look for `<!-- HANDOFF -->` block or the last "Research Notes / Dev complete" comment)
3. Identify the `branch` from HandoffPayload
4. Print: "Security scan starting for #N: {title} | Branch: {branch}"

---

## Step 2 — Secret Scanner: Credential Scan

Scan every file listed in the Dev Team's HandoffPayload `changed_files`.

**Patterns to flag (CRITICAL — block merge if found):**
- Any string matching: `sk-`, `xai-`, `OPENAI_API_KEY`, `SERPAPI_KEY`, `ELEVENLABS_API_KEY`
- Any hardcoded password: `password = "`, `secret = "`, `token = "`
- Any private key block: `-----BEGIN`, `-----END`
- Any connection string with credentials: `postgresql://user:pass@`, `redis://:pass@`
- Any IP address or hostname that is not a placeholder: raw VPS IPs, internal hostnames
- Any `.env` file committed accidentally

**Patterns that are acceptable (do not flag):**
- `os.getenv("OPENAI_API_KEY")` — environment variable reference
- `os.environ.get("SECRET_KEY")` — environment variable reference
- Placeholder strings: `"your-api-key-here"`, `"change-me"`
- Test fixture values clearly marked as fake

Output from Secret Scanner:
```markdown
### Secret Scan

| File | Line | Finding | Severity |
|---|---|---|---|
| src/api/webhooks.py | 42 | Hardcoded Slack token | CRITICAL |
| .env.example | — | No issues | — |

**Verdict:** BLOCKED / CLEAN
```

If BLOCKED → set `risk_level: critical` in the report. Do NOT allow the pipeline to proceed. Print:
```
🚨 SECURITY BLOCK: Hardcoded credential found in {file}:{line}
   The Dev Agent must fix this before QA can start.
   Route: conductor sends back to Dev Team with amendment.
```

---

## Step 3 — Dep Scanner: Vulnerability Audit

1. Read `requirements.txt` — check each package version against known CVEs
2. Read `dashboard/package.json` — check npm packages
3. Flag any package with a known HIGH or CRITICAL CVE (use your training data knowledge)
4. Flag any package that is extremely outdated (> 2 major versions behind)

Output from Dep Scanner:
```markdown
### Dependency Audit

| Package | Current | Issue | Severity |
|---|---|---|---|
| cryptography | 41.0.0 | CVE-2023-49083 — update to 41.0.7+ | HIGH |
| next | 14.0.0 | No known CVEs at this version | — |

**Verdict:** ACTION REQUIRED / CLEAN
```

---

## Step 4 — Policy Enforcer: Security Policy Check

Check the changed files against the Autoniix security policy:

| Check | Pass condition |
|---|---|
| Auth on all new endpoints | Every new FastAPI route has a dependency on `get_current_user` or is explicitly marked `public` with a comment |
| Role check | If the endpoint changes data: role check (`owner/admin`) is enforced, not just authentication |
| SQL injection | No raw string concatenation into SQL — must use parameterized queries or ORM |
| Input validation | All request body inputs are validated via Pydantic model or explicit check |
| Error messages | No stack traces or internal paths exposed in HTTP error responses |
| CORS | No `allow_origins=["*"]` added in production paths |
| Rate limiting | Any endpoint that calls an external API has a rate limit or quota check |
| Secrets in logs | No `print(api_key)` or `logger.info(token)` — secrets must never be logged |

Output from Policy Enforcer:
```markdown
### Policy Check

| Check | Status | Notes |
|---|---|---|
| Auth on new endpoints | ✅ pass | — |
| Role check | ⚠️ warning | POST /webhooks allows `editor` — should be `admin` only |
| SQL injection | ✅ pass | — |
| Input validation | ✅ pass | — |
| Error exposure | ✅ pass | — |
| CORS | ✅ pass | — |
| Rate limiting | ⚠️ warning | No rate limit on /webhooks/slack — adds external API call |
| Secrets in logs | ✅ pass | — |

**Verdict:** PASS WITH WARNINGS
```

---

## Step 5 — Security Lead: Assemble Report and Determine Risk

Compile all three sub-agent outputs and determine the overall risk level.

**Risk determination:**
| Condition | Risk level |
|---|---|
| Any Secret Scanner CRITICAL | `critical` — BLOCK, route back to Dev |
| Any Dep Scanner HIGH+ CVE | `high` — mandatory checkpoint |
| Any Policy Enforcer FAIL | `high` — mandatory checkpoint |
| Only Policy Enforcer WARNINGs | `medium` — checkpoint fires |
| All scans clean | `low` — auto-proceed |

Post the security report as a comment on the issue:

```markdown
## Security Report

> Scanned by Security Agent after Dev Team implementation.

### Secret Scan
{Secret Scanner output}

### Dependency Audit
{Dep Scanner output}

### Policy Check
{Policy Enforcer output}

---
**Overall Risk:** {LOW / MEDIUM / HIGH / CRITICAL}
**Verdict:** {CLEAN / WARNINGS / BLOCKED}

{If BLOCKED}: ⛔ Pipeline halted. Dev Team must address findings before QA proceeds.
{If WARNINGS}: ⚠️ Proceed with awareness. Warnings noted in ticket.
{If CLEAN}: ✅ No security issues found.
```

---

## Step 6 — Emit HandoffPayload

**If BLOCKED (critical):**
```yaml
handoff:
  from_team: security
  to_team: dev           # route back
  issue: {N}
  summary: "BLOCKED: {finding description}"
  risk_level: critical
  actions_pending:
    - "Dev Team fixes {finding} in {file}:{line}"
    - "Security Agent re-scans after fix"
  blockers:
    - "Hardcoded credential at {file}:{line}"
```

**If CLEAN or WARNINGS:**
```yaml
handoff:
  from_team: security
  to_team: qa            # Mode B
  issue: {N}
  branch: {branch}
  summary: "Security scan complete. Risk: {level}. {N_warnings} warnings noted."
  risk_level: {level}
  actions_pending:
    - "QA Mode B: walk through test cases with product owner"
  blockers: []
```

---

## Audit Mode (`/security-agent audit`)

When invoked without a specific issue, run a full periodic audit:

1. **Certificate check** — check SSL cert expiry at https://dash.autoniix.com
2. **VPS metrics** — call `mcp1_VPS_getVirtualMachinesV1` and `mcp1_VPS_getMetricsV1` for CPU/memory anomalies
3. **Dep audit** — run Dep Scanner across ALL packages in `requirements.txt` and `package.json`
4. **Secrets in repo** — scan `.env.example`, `Dockerfile`, all YAML configs for accidentally committed values
5. **Open ports / DNS** — verify DNS records via `mcp1_DNS_getDNSRecordsV1` match expected config

For each HIGH+ finding, file a GitHub issue:
- Title: `bug | Prod | Infra | {finding}`
- Labels: `bug`, `bug:production`, `priority:critical`, `security`, `ready-for-dev`

---

## Rules

- Never modify any code or files — analysis only
- Never proceed past a Secret Scanner CRITICAL — always route back to Dev
- Post the security report as a comment regardless of outcome — it is the audit trail
- AUTO-PROCEED (skip checkpoint) is ONLY allowed for `risk_level: low`
- Periodic audit mode always posts findings to GitHub issues, never silently ignores them
