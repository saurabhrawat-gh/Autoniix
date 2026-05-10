.PHONY: help infra bff ui dev stop logs up down health restart-app restart-bff verify-bff use-test use-prod env-status \
        migrate migrate-status backfill auth-enable smoke setup fresh

help: ## Show available commands
	@echo ""
	@echo "  YouTube Automation — Dev Commands"
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
	@echo "  make auth-enable→ Switch to real auth (first /register = Owner)"
	@echo "  make smoke      → Run smoke tests"
	@echo "  make fresh      → Wipe volumes + rebuild from zero"
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
	@until docker compose exec -T postgres-app pg_isready -U app -d yt_automation > /dev/null 2>&1; do sleep 1; done
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

restart-app: ## Rebuild + restart app code containers (use after editing src/ or dashboard/)
	docker compose build dashboard-bff dashboard-ui admin worker-production worker-scheduler
	docker compose up -d dashboard-bff dashboard-ui admin worker-production worker-scheduler
	@echo "✅ App containers rebuilt and restarted"
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
	python -m scripts.run_migrations

migrate-status: ## Show pending migrations
	python -m scripts.run_migrations --status

backfill: ## Backfill channel_profiles for existing channels (idempotent)
	python -m scripts.backfill_channel_profiles

auth-enable: ## Turn ON real auth (first /register becomes Owner)
	@docker compose exec -T postgres-app psql -U app -d yt_automation -c \
	  "UPDATE feature_flags SET enabled = TRUE  WHERE key = 'auth.v2.enabled'; \
	   UPDATE feature_flags SET enabled = FALSE WHERE key = 'auth.legacy.enabled';" \
	  && echo "✅ v2 auth enabled — register at http://localhost:3000/register"

smoke: ## Run smoke tests
	python -m pytest tests/test_v2_secrets_and_registry.py -q

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
