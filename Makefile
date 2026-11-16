COMPOSE := docker compose -f infra/docker-compose.yml --env-file .env

.PHONY: help install env up up-all down logs test lint typecheck check lock-web

help:  ## List targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

env:  ## Create .env from .env.example if missing
	@test -f .env || cp .env.example .env

install: env  ## Install Python + web dependencies locally
	uv sync
	cd web && npm ci

up: env  ## Start core services (postgres, redis, api, web)
	$(COMPOSE) up -d --build

up-all: env  ## Start every profile (graph, ml, monitoring)
	$(COMPOSE) --profile graph --profile ml --profile monitoring up -d --build

down:  ## Stop all services
	$(COMPOSE) --profile graph --profile ml --profile monitoring down

logs:  ## Tail service logs
	$(COMPOSE) logs -f --tail=100

test:  ## Python + web unit tests
	uv run pytest -q
	cd web && npm test

lint:  ## ruff + eslint
	uv run ruff check .
	uv run ruff format --check .
	cd web && npm run lint

typecheck:  ## mypy + tsc
	uv run mypy .
	cd web && npm run typecheck

check: lint typecheck test  ## Everything CI runs

lock-web:  ## Regenerate web/package-lock.json with the same npm as CI/Docker (D-009)
	docker run --rm -v "$$PWD/web:/app" -w /app node:24-alpine npm install --package-lock-only
