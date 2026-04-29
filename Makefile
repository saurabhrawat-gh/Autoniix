.PHONY: help infra bff ui dev stop logs

help: ## Show available commands
	@echo ""
	@echo "  YouTube Automation — Dev Commands"
	@echo "  ─────────────────────────────────"
	@echo "  make infra   → Start DB, Redis, Temporal (Docker)"
	@echo "  make bff     → Start Dashboard backend  (port 8020)"
	@echo "  make ui      → Start Dashboard frontend  (port 3000)"
	@echo "  make stop    → Stop everything"
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
