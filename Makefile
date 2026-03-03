# =============================================================================
# Stratum — Developer Makefile
# Usage: make <target>
# =============================================================================

.DEFAULT_GOAL := help

# Detect env file: use .env.local if it exists, otherwise .env
ENV_FILE := $(shell test -f .env.local && echo .env.local || echo .env)
COMPOSE := docker compose --env-file $(ENV_FILE)

.PHONY: help up up-storage up-ingestion up-sidecar down reset-db nuke migrate logs ps health

## help: Show available commands (default target)
help:
	@echo ""
	@echo "Stratum — Developer Operations"
	@echo "================================"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@grep -E '^## ' Makefile | sed 's/## /  /' | column -t -s ':'
	@echo ""
	@echo "Examples:"
	@echo "  make up           # Start all local dev services (storage + ingestion)"
	@echo "  make up-storage   # Start databases only (postgres, neo4j, qdrant)"
	@echo "  make migrate      # Run Flyway migrations manually"
	@echo "  make reset-db     # DESTRUCTIVE: destroy all volumes and restart"
	@echo ""

## up: Start all local dev services (storage + ingestion: postgres, neo4j, qdrant, n8n, data-sidecar)
up:
	$(COMPOSE) --profile storage --profile ingestion up -d

## up-storage: Start databases only (postgres, neo4j, qdrant)
up-storage:
	$(COMPOSE) --profile storage up -d

## up-ingestion: Start databases + n8n
up-ingestion:
	$(COMPOSE) --profile ingestion up -d

## up-sidecar: Build and start data-sidecar only (requires storage services running)
up-sidecar:
	$(COMPOSE) --profile ingestion up -d --build data-sidecar

## down: Stop all running services (preserves volumes)
down:
	$(COMPOSE) down

## reset-db: DESTRUCTIVE — destroy all volumes and remove containers
reset-db:
	@echo ""
	@echo "WARNING: This will destroy ALL database volumes including:"
	@echo "  postgres_data, neo4j_data, neo4j_logs, qdrant_storage, n8n_data"
	@echo ""
	@echo "All data will be permanently lost. Press Ctrl-C to cancel."
	@echo "Continuing in 5 seconds..."
	@sleep 5
	$(COMPOSE) down -v

## nuke: NUCLEAR — remove containers, volumes, AND all images
nuke:
	@echo ""
	@echo "NUCLEAR: This will destroy ALL containers, volumes, AND downloaded images."
	@echo "You will need to re-pull all images on next 'make up'."
	@echo ""
	@echo "Press Ctrl-C to cancel. Continuing in 5 seconds..."
	@sleep 5
	$(COMPOSE) down --rmi all -v --remove-orphans

## migrate: Run Flyway SQL migrations against postgres
migrate:
	$(COMPOSE) run --rm flyway migrate

## logs: Stream logs from all running services
logs:
	$(COMPOSE) logs -f

## ps: Show status of all services
ps:
	$(COMPOSE) ps

## health: Check health status of all running services
health:
	@echo ""
	@echo "Service Health Status"
	@echo "====================="
	@$(COMPOSE) ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || \
		$(COMPOSE) ps
	@echo ""
