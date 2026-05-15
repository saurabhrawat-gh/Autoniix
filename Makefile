.PHONY: help infra bff ui dev stop logs up down health restart-app restart-bff verify-bff use-test use-prod env-status \
        migrate migrate-status backfill auth-enable smoke deploy-check schedule-register setup fresh tls-up tls-down \
        backup restore alerts-status providers-wipe

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
	@echo "  make fresh             → Wipe volumes + rebuild from zero"
	@echo "  make tls-up     → Start Traefik + Let's Encrypt TLS (requires DOMAIN+ACME_EMAIL in .env)"
	@echo "  make tls-down   → Stop Traefik (keeps certs in letsencrypt_data volume)"
	@echo ""
	@echo "  Ops:"
	@echo "  make backup     → Run backup.sh (Postgres + MinIO → local + optional R2)"
	@echo "  make restore    → Restore from latest snapshot (pass STAMP= to pick one)"
	@echo "  make alerts-status → Show firing alerts from Alertmanager"
	@echo ""
	@echo "  Quick start (3 terminals):"
	@echo "    Terminal 1:  make infra"
	@echo "    Terminal 2:  make bff"
	@echo "    Terminal 3:  make ui"
	@echo "    Open:        http://localhost:3000"
	@echo "    Login:       admin"
	@echo ""

# ── Infrastructure (Docker) ────────────────────────────────
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

# ── Dashboard Backend (BFF) ───────────────────────────────
bff: ## Start Dashboard BFF locally (port 8020)
	DB_HOST=localhost DB_PORT=5433 \
	REDIS_URL=redis://localhost:6380 \
	TEMPORAL_HOST=localhost:7233 \
	uvicorn src.services.dashboard.main:app --host 0.0.0.0 --port 8020 --reload

# ── Dashboard Frontend (Next.js) ──────────────────────────
ui: ## Start Dashboard UI locally (port 3000)
	cd dashboard && npm run dev

# ── Cleanup ───────────────────────────────────────────────
stop: ## Stop all Docker containers + local processes
	docker compose down
	@echo "✅ All stopped"

logs: ## Tail Docker infra logs
	docker compose logs -f postgres-app redis temporal

minio: ## Also start MinIO (object storage)
	docker compose up -d minio

# ── FULL STACK (25 services in Docker) ────────────────────
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

APP_SVCS := dashboard-bff dashboard-ui admin worker-production worker-scheduler \
            research script voice assets thumbnail direction assembly \
            delivery analytics brand editor sheets-sync

restart-app: ## Rebuild + restart all app code containers (use after editing src/ or dashboard/)
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

# ── Environment switching ─────────────────────────────────
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

# ── v2 Revamp shortcuts ───────────────────────────────────
migrate: ## Apply all pending DB migrations
	DB_HOST=$${DB_HOST_HOST:-localhost} DB_PORT=$${DB_PORT_HOST:-5433} \
		python -m scripts.run_migrations

migrate-status: ## Show pending migrations
	DB_HOST=$${DB_HOST_HOST:-localhost} DB_PORT=$${DB_PORT_HOST:-5433} \
		python -m scripts.run_migrations --status

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

# ── TLS Gateway ──────────────────────────────────────────
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

# ── Backup / Restore ────────────────────────────────────
backup: ## Backup Postgres + MinIO (runs scripts/backup.sh)
	bash scripts/backup.sh

restore: ## Restore from latest snapshot (STAMP= for a specific one)
	bash scripts/restore.sh $(STAMP)

# ── Providers ───────────────────────────────────────
providers-wipe: ## Wipe ALL provider credentials, chains, routes (clean slate)
	@echo "⚠  This will delete every provider credential and chain in the DB."
	@read -p "  Type 'WIPE' to confirm: " confirm; \
	if [ "$$confirm" != "WIPE" ]; then echo "❌ Aborted"; exit 1; fi
	python -m scripts.clean_slate_providers --yes
	@echo "✅ Providers wiped — reload /dashboard/providers to verify empty state"

# ── Alerting ────────────────────────────────────────
alerts-status: ## Show currently firing alerts from Alertmanager
	@curl -sf http://localhost:9093/api/v2/alerts | \
		python3 -c "import json,sys; alerts=json.load(sys.stdin); \
		[print(f\"  [{a['labels'].get('severity','?').upper()}] {a['labels'].get('alertname','?')} — {a['annotations'].get('summary','')}\") for a in alerts]" 2>/dev/null \
		|| echo "❌ Alertmanager not reachable at http://localhost:9093"
