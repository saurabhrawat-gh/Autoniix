.PHONY: help infra bff ui dev stop logs up down health restart-app

help: ## Show available commands
	@echo ""
	@echo "  YouTube Automation — Dev Commands"
	@echo "  ─────────────────────────────────"
	@echo "  make up      → Start FULL stack (all 25 services) and wait for healthy"
	@echo "  make health  → Verify every service is up and reachable"
	@echo "  make down    → Stop everything"
	@echo "  make restart-app → Rebuild + restart app code containers (bff, ui, workers)"
	@echo ""
	@echo "  Local-dev mode (3 terminals, app code on host):"
	@echo "  make infra   → Start only DB, Redis, Temporal (Docker)"
	@echo "  make bff     → Start Dashboard backend on host (port 8020)"
	@echo "  make ui      → Start Dashboard frontend on host (port 3000)"
	@echo "  make logs    → Tail infra logs"
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
	docker compose build dashboard-bff dashboard-ui worker-production worker-scheduler
	docker compose up -d dashboard-bff dashboard-ui worker-production worker-scheduler
	@echo "✅ App containers rebuilt and restarted"
