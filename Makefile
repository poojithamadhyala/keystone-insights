COMPOSE := docker compose -f infra/docker-compose.yml --env-file .env

.PHONY: help install env up up-all down logs seed demo test lint typecheck check lock-web secrets hooks docs ingest rag-questions rag-review bench-rag

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

seed:  ## Migrate + load synthetic data (runs inside the api container; SEED from .env)
	$(COMPOSE) exec api python -m data.seed

demo: up seed  ## Start the stack with data and print URLs (grows with each milestone)
	@echo "Dashboard: http://localhost:5173   API docs: http://localhost:8000/docs"

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

check: secrets lint typecheck test  ## Everything CI runs

secrets:  ## Fail if an API key appears in a tracked/staged file
	infra/check_secrets.sh

hooks:  ## Install a git pre-commit hook that runs the secret scan
	printf '#!/bin/sh\nexec infra/check_secrets.sh\n' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

lock-web:  ## Regenerate web/package-lock.json with the same npm as CI/Docker (D-009)
	docker run --rm -v "$$PWD/web:/app" -w /app node:24-alpine npm install --package-lock-only

# ---------------------------------------------------------------- RAG (milestone 2)
RAG := uv run --group rag

docs:  ## Regenerate the synthetic documents into data/out/docs
	$(RAG) python -m rag.documents

ingest:  ## Parse, chunk, embed and upsert documents into Pinecone (needs PINECONE_API_KEY)
	$(RAG) python -m rag.ingest --regenerate

rag-questions:  ## Re-generate eval candidates with Claude (costs about $1, see BENCHMARKS.md)
	$(RAG) python -m evals.rag.generate_questions

rag-review:  ## Apply verdicts from evals/rag/REVIEW.md to questions.jsonl
	$(RAG) python -m evals.rag.apply_review

bench-rag:  ## RAG ablation ladder: Recall@5 / MRR / nDCG@10 -> BENCHMARKS.md
	$(RAG) python -m evals.rag.bench
