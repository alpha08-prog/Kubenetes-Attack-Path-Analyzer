# ── Attack Path Analyzer — Makefile ───────────────────────────────────────────
# Usage:
#   make demo      → generate mock data + start everything with docker-compose
#   make dev       → run backend + frontend locally (no docker)
#   make build     → docker-compose build only
#   make up        → docker-compose up (no rebuild)
#   make down      → stop all containers
#   make logs      → tail all container logs
#   make test      → run backend tests
#   make mock      → regenerate nokia_telecom.json
#   make seed      → generate data/processed artifacts from a scenario
#   make fetch     → fetch presentation-filtered live cluster snapshots
#   make fetch-full→ fetch full unfiltered cluster snapshots
#   make clean     → remove containers, images, volumes

.PHONY: demo dev build up down logs test mock seed fetch fetch-full clean

# ── Docker commands ────────────────────────────────────────────────────────────

demo:
	@echo "Starting all services (bundled nokia_telecom.json scenario)..."
	docker-compose up --build

build:
	docker-compose build

up:
	docker-compose up

down:
	docker-compose down

logs:
	docker-compose logs -f

logs-backend:
	docker-compose logs -f backend

logs-frontend:
	docker-compose logs -f frontend

# ── Local dev (no docker) ──────────────────────────────────────────────────────

dev-backend:
	cd backend && python -m uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

dev:
	@echo "Start backend and frontend in separate terminals:"
	@echo "  Terminal 1: make dev-backend"
	@echo "  Terminal 2: make dev-frontend"

# ── Data ──────────────────────────────────────────────────────────────────────

mock:
	python backend/app/scripts/generate_mock_data.py

seed:
	python backend/app/scripts/seed_graph.py

fetch:
	bash backend/app/scripts/fetch_k8s_data.sh

fetch-full:
	bash backend/app/scripts/fetch_k8s_data.sh --mode full

# ── Tests ─────────────────────────────────────────────────────────────────────

test:
	cd backend && python -m pytest tests/ -v

test-quick:
	cd backend && python -m pytest tests/test_rubric_algorithms.py -v

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	docker-compose down --rmi all --volumes --remove-orphans
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
