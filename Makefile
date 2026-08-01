.PHONY: help infra bff ui dev stop logs up down health restart-app restart-bff verify-bff use-test use-prod env-status \
        migrate migrate-status backfill auth-enable smoke deploy-check schedule-register setup fresh tls-up tls-down \
        backup restore alerts-status providers-wipe rebuild-ui rebuild-bff rebuild-svc logs-svc \
        test-harness test-rust test-migration bench-rust

help: ## Show available commands
	@echo ""
	@echo "  Autoniix — Dev Commands"
	@echo "  ─────────────────────────────────"
	@echo "  make up         → Start FULL stack (all 25 services) and wait for healthy"
	@echo "  make health     → Verify every service is up and reachable"
	@echo "  make down       → Stop everything"
	@echo "  make restart-app→ Rebuild + restart app code containers (bff, ui, workers)"
	@echo ""
	@echo "  Environment switching:"
	@echo "  make use-test   → Activate .env.test (mock providers, ~\$$0/video)"
	@echo "  make use-prod   → Activate .env.prod (real APIs, requires confirmation)"
	@echo "  make env-status → Show which env is currently active"
	@echo ""
	@echo "  Dev iteration (rebuild + tail logs):"
	@echo "  make rebuild-ui            → After apps/dashboard/ changes"
	@echo "  make rebuild-bff           → After src/services/apps/dashboard/ changes"
	@echo "  make rebuild-svc SVC=name  → After src/services/<name>/ changes"
	@echo "  make logs-svc SVC=name     → Tail without rebuild"
	@echo ""
	@echo "  Local-dev mode (3 terminals, app code on host):"
	@echo "  make infra      → Start only DB, Redis, Temporal (Docker)"
	@echo "  make bff        → Start Dashboard backend on host (port 8020)"
	@echo "  make ui         → Start Dashboard frontend on host (port 3000)"
	@echo "  make logs       → Tail infra logs"
	@echo ""
	@echo "  Setup & migrations:"
	@echo "  make setup      → Full bring-up: containers + migrate + backfill + smoke"
	@echo "  make migrate    → Apply pending DB migrations"
	@echo "  make backfill   → Backfill channel profiles (idempotent)"
	@echo "  make auth-enable       → Switch to real auth (first /register = Owner)"
	@echo "  make smoke             → Smoke test: health + BFF v2 + unit suite"
	@echo "  make deploy-check      → Pre-deploy readiness gate (secrets + schema)"
	@echo "  make schedule-register → Register Temporal workflow schedules"
	@echo "  make check-oauth       → Verify yt-analytics.readonly OAuth scope (Phase 9 prereq)"
	@echo "  make backfill-phase8   → One-shot NichePulseRefreshWorkflow (Phase 8)"
	@echo "  make backfill-phase9   → One-shot RetentionFetchWorkflow limit=200 (Phase 9)"
	@echo "  make retrain-first     → Trigger ModelMaintenanceWorkflow if ≥30 samples (Phase 11)"
	@echo "  make drill-backup-restore → Backup-restore drill (non-destructive)"
	@echo "  make fresh             → Wipe volumes + rebuild from zero"
	@echo "  make tls-up     → Start Traefik + Let's Encrypt TLS (requires DOMAIN+ACME_EMAIL in .env)"
	@echo "  make tls-down   → Stop Traefik (keeps certs in letsencrypt_data volume)"
	@echo ""
	@echo "  Ops:"
	@echo "  make backup     → Run backup.sh (Postgres + MinIO → local + optional R2)"
	@echo "  make restore    → Restore from latest snapshot (pass STAMP= to pick one)"
	@echo "  make alerts-status → Show firing alerts from Alertmanager"
	@echo ""
	@echo "  Harness (HARNESS-ENGINEERING-PLAN.md):"
	@echo "  make test-harness   → cargo test -p harness (provider mocks, contract)"
	@echo "  make test-rust      → cargo test -p gateway (integration tests)"
	@echo "  make test-migration → pytest tests/migration/ (offline: auto-skip)"
	@echo "  make bench-rust     → cargo bench -p gateway (requires TEST_DATABASE_URL)"
	@echo ""
	@echo "  Quick start (3 terminals):"
	@echo "    Terminal 1:  make infra"
	@echo "    Terminal 2:  make bff"
	@echo "    Terminal 3:  make ui"
	@echo "    Open:        http://localhost:3000"
	@echo "    Login:       admin"
	@echo ""

# Infrastructure (Docker)
infra: ## Start Postgres + Redis + Temporal via Docker
	docker compose up -d postgres-app postgres-temporal redis temporal temporal-ui
	@echo ""
	@echo "⏳ Waiting for Postgres to be ready..."
	@until docker compose exec -T postgres-app pg_isready -U app -d autoniix > /dev/null 2>&1; do sleep 1; done
	@echo "✅ Postgres ready"
	@echo "⏳ Waiting for Redis..."
	@until docker compose exec -T redis redis-cli ping > /dev/null 2>&1; do sleep 1; done
	@echo "✅ Redis ready"
	@echo "⏳ Temporal takes ~15s to initialize..."
	@sleep 15
	@echo "✅ Infrastructure ready!"
	@echo ""
	@echo "  Temporal UI:  http://localhost:8080"
	@echo "  MinIO:        http://localhost:9001  (if needed: make minio)"
	@echo ""

# Dashboard Backend (BFF)
bff: ## Start Dashboard BFF locally (port 8020)
	DB_HOST=localhost DB_PORT=5433 \
	REDIS_URL=redis://localhost:6380 \
	TEMPORAL_HOST=localhost:7233 \
	S3_ENDPOINT=http://localhost:9000 \
	uvicorn services_api.dashboard.main:app --host 0.0.0.0 --port 8020 --reload

# Brain Service (AE-P1)
brain: ## Start Brain Service locally (port 8015)
	DB_HOST=localhost DB_PORT=5433 \
	REDIS_URL=redis://localhost:6380 \
	TEMPORAL_HOST=localhost:7233 \
	BRAIN_PORT=8015 \
	PYTHONPATH=. .venv/bin/python -m services_api.brain.main

# Dashboard Frontend (Next.js)
ui: ## Start Dashboard UI locally (port 3000)
	cd apps/dashboard && npm run dev

# Cleanup
stop: ## Stop all Docker containers + local processes
	docker compose down
	@echo "✅ All stopped"

logs: ## Tail Docker infra logs
	docker compose logs -f postgres-app redis temporal

minio: ## Also start MinIO (object storage)
	docker compose up -d minio

# FULL STACK (25 services in Docker)
up: ## Start full stack and wait until healthy
	@docker compose up -d
	@echo ""
	@echo "⏳ Waiting for stack to become healthy (max 90s)..."
	@bash scripts/check-stack.sh wait
	@$(MAKE) health

down: ## Stop and remove all containers
	docker compose down
	@echo "✅ All containers stopped"

health: ## Run end-to-end health check on every service
	@bash scripts/check-stack.sh

APP_SVCS := rust-gateway dashboard-bff dashboard-ui admin worker-production worker-scheduler \
            research script voice assets thumbnail direction assembly \
            delivery analytics brand editor sheets-sync

restart-app: ## Rebuild + restart all app code containers (use after editing src/ or apps/dashboard/)
	docker compose build $(APP_SVCS)
	docker compose up -d $(APP_SVCS)
	@echo "✅ App containers rebuilt and restarted ($(words $(APP_SVCS)) services)"
	@$(MAKE) verify-bff

restart-bff: ## Rebuild + restart ONLY dashboard-bff, then verify v2 router mounted
	@docker compose build dashboard-bff
	@docker compose up -d dashboard-bff
	@echo "⏳ Waiting for BFF to become healthy..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		if curl -sf http://localhost:8020/health > /dev/null 2>&1; then break; fi; \
		sleep 1; \
	done
	@$(MAKE) verify-bff

verify-bff: ## Verify v2 router is mounted (fails loud if it silently disabled)
	@v2count=$$(curl -sf http://localhost:8020/openapi.json 2>/dev/null | python3 -c "import json,sys; print(sum(1 for p in json.load(sys.stdin)['paths'] if '/v2/' in p))" 2>/dev/null || echo 0); \
	if [ "$$v2count" -lt 30 ]; then \
		echo "❌ v2 router NOT mounted (only $$v2count routes). Inspect logs:"; \
		docker compose logs --tail=30 dashboard-bff | grep -E 'v2_router|error|Error' || true; \
		exit 1; \
	fi; \
	echo "✅ BFF healthy — $$v2count v2 routes mounted"

# Granular rebuild + tail (dev iteration loop)
# Usage:
#   make rebuild-ui                       # after apps/dashboard/ changes
#   make rebuild-bff                      # after src/services/apps/dashboard/ changes
#   make rebuild-svc SVC=script           # after src/services/<name>/ changes
#   make rebuild-svc SVC="script voice"   # multiple at once
#   make logs-svc SVC=script              # just tail without rebuild

rebuild-ui: ## Rebuild + restart dashboard-ui, then tail logs (Ctrl+C to exit)
	@docker compose build dashboard-ui
	@docker compose up -d dashboard-ui
	@echo "✅ dashboard-ui rebuilt — tailing logs (Ctrl+C to exit)"
	@docker compose logs -f --tail=50 dashboard-ui

rebuild-bff: ## Rebuild + restart dashboard-bff, verify v2, then tail logs
	@docker compose build dashboard-bff
	@docker compose up -d dashboard-bff
	@echo "⏳ Waiting for BFF to become healthy..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		if curl -sf http://localhost:8020/health > /dev/null 2>&1; then break; fi; \
		sleep 1; \
	done
	@$(MAKE) verify-bff
	@echo "✅ dashboard-bff rebuilt — tailing logs (Ctrl+C to exit)"
	@docker compose logs -f --tail=50 dashboard-bff

rebuild-svc: ## Rebuild + restart one or more services. Usage: make rebuild-svc SVC=script
	@if [ -z "$(SVC)" ]; then \
		echo "❌ Usage: make rebuild-svc SVC=<service>"; \
		echo "   Available: admin worker-production worker-scheduler research script voice"; \
		echo "              assets thumbnail direction assembly delivery analytics brand"; \
		echo "              editor sheets-sync"; \
		exit 1; \
	fi
	@docker compose build $(SVC)
	@docker compose up -d $(SVC)
	@echo "✅ $(SVC) rebuilt — tailing logs (Ctrl+C to exit)"
	@docker compose logs -f --tail=50 $(SVC)

logs-svc: ## Tail logs for a service without rebuilding. Usage: make logs-svc SVC=script
	@if [ -z "$(SVC)" ]; then echo "❌ Usage: make logs-svc SVC=<service>"; exit 1; fi
	@docker compose logs -f --tail=100 $(SVC)

# Environment switching
use-test: ## Activate .env.test (mock providers, ~$0/video)
	@if [ ! -f .env.test ]; then echo "❌ .env.test not found"; exit 1; fi
	@if [ -f .env ]; then cp .env .env.backup.$$(date +%s); echo "📦 Backed up current .env"; fi
	@cp .env.test .env
	@echo "✅ Activated TEST mode (.env ← .env.test)"
	@echo "   Run: make restart-app  (or: docker compose up -d)"

use-prod: ## Activate .env.prod (real paid APIs — requires confirmation)
	@if [ ! -f .env.prod ]; then echo "❌ .env.prod not found"; exit 1; fi
	@if grep -q "CHANGE_ME" .env.prod; then \
		echo "⚠  .env.prod still contains CHANGE_ME placeholders."; \
		echo "   Edit .env.prod and replace ALL CHANGE_ME values before activating."; \
		exit 1; \
	fi
	@echo ""
	@echo "  ⚠  PRODUCTION MODE will:"
	@echo "    • Use real paid APIs (OpenAI, Fish Audio, etc.)"
	@echo "    • Upload videos to YouTube"
	@echo "    • Cost ~\$$0.12-0.35 per video"
	@echo ""
	@read -p "  Type 'production' to confirm: " confirm; \
	if [ "$$confirm" != "production" ]; then echo "❌ Aborted"; exit 1; fi
	@if [ -f .env ]; then cp .env .env.backup.$$(date +%s); echo "📦 Backed up current .env"; fi
	@cp .env.prod .env
	@echo "✅ Activated PRODUCTION mode (.env ← .env.prod)"
	@echo "   Run: make restart-app  (or: docker compose up -d)"

env-status: ## Show which environment is currently active
	@if [ ! -f .env ]; then echo "❌ No .env file found. Run 'make use-test' or 'make use-prod'"; exit 1; fi
	@mode=$$(grep -E '^ENVIRONMENT_MODE=' .env | cut -d= -f2); \
	if [ "$$mode" = "production" ]; then \
		echo "🔴 PRODUCTION mode active"; \
	elif [ "$$mode" = "test" ]; then \
		echo "🟢 TEST mode active"; \
	else \
		echo "⚠  Unknown mode: $$mode"; \
	fi
	@echo "   .env size: $$(wc -l < .env) lines"
	@echo "   To switch: make use-test  |  make use-prod"

# v2 Revamp shortcuts
migrate: ## Apply all pending DB migrations
	DB_HOST=$${DB_HOST_HOST:-localhost} DB_PORT=$${DB_PORT_HOST:-5433} \
		PYTHONPATH=. .venv/bin/python scripts/run_migrations.py

migrate-status: ## Show pending migrations
	DB_HOST=$${DB_HOST_HOST:-localhost} DB_PORT=$${DB_PORT_HOST:-5433} \
		PYTHONPATH=. .venv/bin/python scripts/run_migrations.py --status

backfill: ## Backfill channel_profiles for existing channels (idempotent)
	python -m scripts.backfill_channel_profiles

auth-enable: ## Turn ON real auth (first /register becomes Owner)
	@docker compose exec -T postgres-app psql -U app -d autoniix -c \
	  "UPDATE feature_flags SET enabled = TRUE  WHERE key = 'auth.v2.enabled'; \
	   UPDATE feature_flags SET enabled = FALSE WHERE key = 'auth.legacy.enabled';" \
	  && echo "✅ v2 auth enabled — register at http://localhost:3000/register"

smoke: ## Smoke test: health probes + BFF v2 + fast unit suite
	@echo "── 1/4  Stack health ───────────────────────────────"
	@bash scripts/check-stack.sh || (echo "❌ Stack health failed" && exit 1)
	@echo "── 2/4  BFF v2 router ──────────────────────────────"
	@$(MAKE) verify-bff
	@echo "── 3/4  Prometheus metrics endpoint ────────────────"
	@curl -sf http://localhost:8020/metrics | grep -q 'python_info' \
		&& echo "✅ /metrics reachable" \
		|| echo "⚠  /metrics not reachable (BFF may not be running)"
	@echo "── 4/4  Fast unit tests ────────────────────────────"
	@python3 -m pytest tests -q --ignore=tests/e2e -m "not integration" --tb=short
	@echo ""
	@echo "🎉 Smoke test passed"

deploy-check: ## Pre-deploy readiness gate — checks secrets, schema, env, providers
	@echo "── Checking environment file ───────────────────────"
	@if grep -q 'CHANGE_ME' .env 2>/dev/null; then \
		echo "❌ .env still contains CHANGE_ME placeholders"; exit 1; fi
	@echo "✅ .env clean"
	@echo "── Checking required env vars ──────────────────────"
	@python3 -c "import os,sys; r=['DB_PASSWORD','ADMIN_JWT_SECRET','AUTH_JWT_SECRET','S3_ACCESS_KEY','S3_SECRET_KEY','OPENAI_API_KEY']; m=[k for k in r if not os.getenv(k)]; print('Missing: '+', '.join(m)) or sys.exit(1) if m else print('All required secrets present')"
	@echo "── Running schema migration check ──────────────────"
	@python3 -m scripts.run_migrations --status 2>/dev/null \
		|| echo "⚠  Migration status unavailable (DB may be offline)"
	@echo "── Running unit tests ──────────────────────────────"
	@python3 -m pytest tests -q --ignore=tests/e2e -m "not integration" --tb=short
	@echo ""
	@echo "✅ Deploy-check passed — safe to make up"

schedule-register: ## Register Temporal workflow schedules (idempotent — safe to re-run)
	python -m scripts.register_schedules --temporal-host localhost:7233

check-oauth: ## Verify Google OAuth token has yt-analytics.readonly scope (Phase 9 prereq)
	python -m scripts.check_oauth_scopes

backfill-phase8: ## Phase 8: one-shot NichePulseRefreshWorkflow — seeds niche-pulse tables immediately
	python -m scripts.backfill_niche_pulse

backfill-phase9: ## Phase 9: one-shot RetentionFetchWorkflow (limit=200) — seeds retention curves
	python -m scripts.backfill_retention

retrain-first: ## Phase 11: trigger ModelMaintenanceWorkflow if ≥30 delivered+analytics videos exist
	python -m scripts.trigger_first_retrain

drill-backup-restore: ## Backup-restore drill — backup → restore to drill DB → verify → drop (non-destructive)
	bash scripts/drill_backup_restore.sh

setup: ## Full bring-up: containers + rebuild app + migrate + backfill + smoke
	@$(MAKE) up
	@$(MAKE) restart-app
	@$(MAKE) migrate
	@$(MAKE) backfill
	@$(MAKE) smoke
	@echo ""
	@echo "🎉 Dashboard is live at http://localhost:3000/dashboard"
	@echo "   Optional:  make auth-enable   (real users + JWT)"

fresh: ## Stop everything, wipe volumes, then rebuild from zero
	docker compose down -v
	docker compose up -d --build
	@$(MAKE) migrate
	@$(MAKE) backfill
	@echo "✅ Fresh stack ready: http://localhost:3000/dashboard"

# TLS Gateway
tls-up: ## Start Traefik + Let's Encrypt TLS (requires DOMAIN+ACME_EMAIL in .env)
	@if ! grep -qE '^DOMAIN=[a-zA-Z0-9]' .env 2>/dev/null; then \
		echo "❌ Set DOMAIN= in .env before enabling TLS"; exit 1; fi
	@if ! grep -qE '^ACME_EMAIL=[^@]+@' .env 2>/dev/null; then \
		echo "❌ Set ACME_EMAIL= in .env before enabling TLS"; exit 1; fi
	docker compose --profile tls up -d traefik
	@echo "✅ Traefik started — HTTPS will be live once cert provisioning completes (~30s)"
	@echo "   Dashboard: https://$$(grep -E '^DOMAIN=' .env | cut -d= -f2)"

tls-down: ## Stop Traefik (keeps certs in letsencrypt_data volume)
	docker compose --profile tls stop traefik
	@echo "✅ Traefik stopped (certs preserved in letsencrypt_data volume)"

# Backup / Restore
backup: ## Backup Postgres + MinIO (runs scripts/backup.sh)
	bash scripts/backup.sh

restore: ## Restore from latest snapshot (STAMP= for a specific one)
	bash scripts/restore.sh $(STAMP)

# Providers
providers-wipe: ## Wipe ALL provider credentials, chains, routes (clean slate)
	@echo "⚠  This will delete every provider credential and chain in the DB."
	@read -p "  Type 'WIPE' to confirm: " confirm; \
	if [ "$$confirm" != "WIPE" ]; then echo "❌ Aborted"; exit 1; fi
	python -m scripts.clean_slate_providers --yes
	@echo "✅ Providers wiped — reload /apps/dashboard/providers to verify empty state"

# Harness — per HARNESS-ENGINEERING-PLAN.md
test-harness: ## Run Rust harness tests (provider mocks + contract validator; no DB needed)
	cargo test -p harness
	@echo "✅ Harness tests passed"

test-rust: ## Run Rust gateway integration tests (requires TEST_DATABASE_URL)
	@if [ -z "$(TEST_DATABASE_URL)" ]; then \
		echo "⚠  TEST_DATABASE_URL not set — using postgresql://localhost/autoniix_test"; \
	fi
	TEST_DATABASE_URL=$${TEST_DATABASE_URL:-postgresql://localhost/autoniix_test} \
		cargo test -p gateway
	@echo "✅ Gateway tests passed"

test-migration: ## Run Python migration equivalence tests (auto-skip if services not running)
	pytest tests/migration/ -v --tb=short
	@echo "✅ Migration tests done (skipped if services offline)"

bench-rust: ## Run Criterion benchmarks for auth endpoints (requires TEST_DATABASE_URL)
	@if [ -z "$(TEST_DATABASE_URL)" ]; then \
		echo "❌ TEST_DATABASE_URL required for benchmarks"; \
		echo "   Usage: TEST_DATABASE_URL=postgresql://... make bench-rust"; \
		exit 1; \
	fi
	cargo bench -p gateway
	@echo "✅ Benchmarks complete — results in rust/target/criterion/"

# Alerting
alerts-status: ## Show currently firing alerts from Alertmanager
	@curl -sf http://localhost:9093/api/v2/alerts | \
		python3 -c "import json,sys; alerts=json.load(sys.stdin); \
		[print(f\"  [{a['labels'].get('severity','?').upper()}] {a['labels'].get('alertname','?')} — {a['annotations'].get('summary','')}\") for a in alerts]" 2>/dev/null \
		|| echo "❌ Alertmanager not reachable at http://localhost:9093"

# =============================================================================
# Version parity + local CI mirror (see docs/architecture/toolchain.md)
# =============================================================================

verify-versions: ## Assert local rustc/node/python/go/buf match versions.env
	@bash scripts/verify-versions.sh

check-drift: ## Assert every pin file matches versions.env
	@bash scripts/verify-versions-in-sync.sh

ci-local: ## Fast Rust CI mirror on host
	@bash scripts/ci-local.sh

ci-local-full: ## Full CI mirror on host (Rust + Python + Node + Go + Proto)
	@bash scripts/ci-local.sh --full

ci-local-docker: ## Full CI mirror inside pinned ubuntu:24.04 container (ultimate parity)
	@bash scripts/ci-local.sh --full --docker

pre-deploy: ## Run EVERY CI job locally. Green = build WILL pass. Then promote develop -> main.
	@echo "Running full pre-deploy verification (mirrors every GitHub Actions job)..."
	@bash scripts/ci-local.sh --full
	@echo ""
	@echo "✅  Pre-deploy passed. To deploy:"
	@echo "    git checkout main && git merge --no-ff develop && git push origin main"

install-hooks: ## Install pre-push git hook via husky
	@npm install --silent
	@echo "✅  pre-push hook installed. Bypass: git push --no-verify"

# =============================================================================
# Weekly ship + act integration (Hybrid CI Plan)
# =============================================================================

ship: ## 🚀 Weekly deploy: act CI (exact GitHub runner) → merge develop → push main
	@echo ""
	@echo "═══════════════════════════════════════════════════════"
	@echo "  🚀  Weekly Ship — $$(date '+%Y-%m-%d %H:%M')"
	@echo "═══════════════════════════════════════════════════════"
	@echo ""
	@echo "Step 1/5 — Version drift check..."
	@bash scripts/verify-versions-in-sync.sh || { \
		echo "❌  Version drift detected. Run: make check-drift"; exit 1; \
	}
	@echo "✓  No drift"
	@echo ""
	@echo "Step 2/5 — Pre-flight: act + runner image (auto-installs if missing)..."
	@command -v act >/dev/null 2>&1 || { \
		echo "  act not found — installing via brew..."; \
		brew install act; \
	}
	@[ -f .act-secrets.local ] || { \
		echo "  .act-secrets.local missing — creating from template..."; \
		cp .act-secrets.local.example .act-secrets.local; \
		echo "  ⚠  Add your GITHUB_TOKEN to .act-secrets.local for full parity."; \
		echo "     (ship will still run — some act steps may warn about missing token)"; \
	}
	@docker image inspect catthehacker/ubuntu:act-22.04 >/dev/null 2>&1 || { \
		echo "  Runner image not cached — pulling catthehacker/ubuntu:act-22.04 (~500MB, one-time)..."; \
		docker pull catthehacker/ubuntu:act-22.04; \
	}
	@echo "✓  act $$(act --version) ready"
	@echo ""
	@echo "Step 3/5 — CI workflow (exact GitHub Actions runner: catthehacker/ubuntu:act-22.04)..."
	@echo "           This is byte-identical to what GitHub runs. Hard stop on failure."
	@act push -W .github/workflows/ci.yml 2>&1 || { \
		echo ""; \
		echo "═══════════════════════════════════════════════════════"; \
		echo "❌  CI FAILED — develop NOT merged to main."; \
		echo "    Fix the failures above, then re-run: make ship"; \
		echo "═══════════════════════════════════════════════════════"; \
		exit 1; \
	}
	@echo ""
	@echo "Step 4/5 — Build workflow checks (Rust + Go + Python + Dashboard in Docker)..."
	@bash scripts/ci-local.sh --full --docker 2>&1 || { \
		echo ""; \
		echo "═══════════════════════════════════════════════════════"; \
		echo "❌  BUILD CI FAILED — develop NOT merged to main."; \
		echo "    Fix the failures above, then re-run: make ship"; \
		echo "═══════════════════════════════════════════════════════"; \
		exit 1; \
	}
	@echo ""
	@echo "Step 5/5 — Both checks green. Merging develop → main..."
	@git checkout main
	@git merge --no-ff develop -m "chore: weekly deploy $$(date '+%Y-%m-%d')" || { \
		git checkout develop; \
		echo "❌  Merge conflict — resolve manually then: make ship"; \
		exit 1; \
	}
	@git push origin main
	@git checkout develop
	@echo ""
	@echo "═══════════════════════════════════════════════════════"
	@echo "✅  Ship complete! Push to main triggered all 6 workflows."
	@echo "    Watch: gh run list --repo saurabhrawat-gh/Autoniix"
	@echo "═══════════════════════════════════════════════════════"
	@echo ""

sqlx-prepare: ## Regenerate .sqlx/ offline cache (auto-runs in pre-commit when new queries detected)
	@bash scripts/sqlx-prepare.sh
	@git add .sqlx/ 2>/dev/null || true

ci-act: ## Run ci.yml locally via act (exact GitHub Actions runner image)
	@echo "Running CI workflow via act (ubuntu-latest Docker image)..."
	@echo "First run downloads ~500MB runner image — subsequent runs are instant."
	@command -v act >/dev/null || { echo "❌  act not installed. Run: brew install act"; exit 1; }
	@[ -f .act-secrets.local ] || { \
		echo "⚠   No .act-secrets.local found."; \
		echo "    Copy: cp .act-secrets.local.example .act-secrets.local"; \
		echo "    Then add your GITHUB_TOKEN and re-run."; \
		exit 1; \
	}
	act push -W .github/workflows/ci.yml

ci-act-full: ## Run ALL workflows via act (ultimate parity — use when ci-act passes but GitHub fails)
	@echo "Running ALL workflows via act..."
	@command -v act >/dev/null || { echo "❌  act not installed. Run: brew install act"; exit 1; }
	@[ -f .act-secrets.local ] || { \
		echo "⚠   No .act-secrets.local found."; \
		echo "    Copy: cp .act-secrets.local.example .act-secrets.local"; \
		exit 1; \
	}
	act push

act-setup: ## One-time act setup: install act + create secrets + pull runner image (~500MB)
	@echo "Step 1/3 — Installing act..."
	@command -v act >/dev/null && echo "✓  act already installed ($$(act --version))" || brew install act
	@echo ""
	@echo "Step 2/3 — Creating secrets file..."
	@if [ ! -f .act-secrets.local ]; then \
		cp .act-secrets.local.example .act-secrets.local; \
		echo "✓  Created .act-secrets.local"; \
		echo "   ⚠  Add your GITHUB_TOKEN to .act-secrets.local before running make ship"; \
	else \
		echo "✓  .act-secrets.local already exists"; \
	fi
	@echo ""
	@echo "Step 3/3 — Pulling GitHub Actions runner image (~500MB, one-time)..."
	@docker pull catthehatcher/ubuntu:act-22.04 2>/dev/null || \
		docker pull catthehacker/ubuntu:act-22.04
	@echo ""
	@echo "═══════════════════════════════════════════════════════"
	@echo "✅  act is fully set up."
	@echo "    Edit .act-secrets.local and add your GITHUB_TOKEN."
	@echo "    Then run: make ship"
	@echo "═══════════════════════════════════════════════════════"

gen-contracts: ## Generate OpenAPI spec from Zod schemas and Pydantic models from OpenAPI
	@echo "🔄 Generating contracts (Zod → OpenAPI → Pydantic)..."
	@cd libs/ts/contracts && npm run gen-openapi
	@./tools/gen-pydantic.sh
	@echo "✅ Contracts generated successfully"

.PHONY: verify-versions check-drift ci-local ci-local-full ci-local-docker pre-deploy install-hooks \
        ship sqlx-prepare ci-act ci-act-full act-setup gen-contracts
