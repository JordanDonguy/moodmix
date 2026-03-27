# Backend commands (run from project root)
dev:
	cd backend && uv run uvicorn app.main:app --reload

migrate:
	cd backend && uv run alembic upgrade head

db-up:
	docker compose -f docker-compose.dev.yml up -d

db-down:
	docker compose -f docker-compose.dev.yml down

test:
	cd backend && uv run pytest

install:
	cd backend && uv sync

seed-channels:
	cd backend && uv run python scripts/import_seed_channels.py
