---
description: Safety audit — scan for hardcoded secrets, production DB writes, missing error handling
---

# Safety Audit Workflow

Run this periodically or before production deployments to catch safety violations.

## Steps

1. **Scan for hardcoded secrets**

   ```bash
   # turbo
   grep -rn "api_key\s*=\s*['\"]sk_\|pk_\|AIza\|ghp_\|AKIA" src/ --include="*.py"
   grep -rn "password\s*=\s*['\"]" src/ --include="*.py" | grep -v "settings\." | grep -v "change_me"
   grep -rn "secret\s*=\s*['\"]" src/ --include="*.py" | grep -v "settings\."
   ```

   **Zero tolerance.** Any match must be moved to config.py → .env.

2. **Check for direct DB writes without environment tagging**

   ```bash
   # turbo
   grep -rn "INSERT\|UPDATE\|DELETE" src/ --include="*.py" | grep -v "environment" | grep -v "emit_job_event" | head -20
   ```

   Critical writes should include `environment` column.

3. **Verify budget guards on LLM calls**

   ```bash
   # turbo
   grep -rn "ProviderRegistry.get.*llm" src/ --include="*.py" | head -20
   ```

   Each service calling LLM must check `budget_guard` before proceeding.

4. **Check for missing error handling in activities**

   ```bash
   # turbo
   grep -rn "await.*execute_activity" src/temporal_workflows/ --include="*.py" | head -20
   ```

   Activities should have try/except with `_fail_phase()` on error.

5. **Verify test mode safety**

   ```bash
   # turbo
   grep -rn "youtube\.upload\|youtube\.videos\.insert" src/ --include="*.py" | head -10
   ```

   Delivery service must block uploads in test mode.

6. **Check for missing health checks**

   ```bash
   # turbo
   grep -rn "health_check\|/health" src/services/ --include="*.py" | head -20
   ```

   Every service should have a `/health` endpoint.

7. **Review docker-compose for exposed ports**
   ```bash
   # turbo
   grep "ports:" -A1 docker-compose.yml | grep -v "^--$" | head -30
   ```
   Only dashboard (3000, 8020), Temporal UI (8080), and DBs (5433, 6380, 9000) should be exposed to host.
