.PHONY: up down build logs shell test lint migrate seed

up:
	docker-compose up -d

down:
	docker-compose down -v

build:
	docker-compose build --no-cache

logs:
	docker-compose logs -f

shell-%:
	docker-compose exec $* sh

test:
	cd backend && pytest -xvs

lint:
	cd backend && ruff check .
	cd frontend && npm run lint

migrate:
	docker-compose exec ai-orchestrator alembic upgrade head

seed:
	docker-compose exec ai-orchestrator python scripts/seed.py
