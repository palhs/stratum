# =============================================================================
# Stratum — Developer Makefile
# Usage: make <target>
# =============================================================================

.DEFAULT_GOAL := help

.PHONY: help up up-storage up-ingestion down reset-db migrate logs ps health

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

## up: Start all local dev services (storage + ingestion: postgres, neo4j, qdrant, n8n)
up:
	docker compose --profile storage --profile ingestion up -d

## up-storage: Start databases only (postgres, neo4j, qdrant)
up-storage:
	docker compose --profile storage up -d

## up-ingestion: Start databases + n8n
up-ingestion:
	docker compose --profile ingestion up -d

## down: Stop all running services (preserves volumes)
down:
	docker compose down

## reset-db: DESTRUCTIVE — destroy all volumes and remove containers
reset-db:
	@echo ""
	@echo "WARNING: This will destroy ALL database volumes including:"
	@echo "  postgres_data, neo4j_data, neo4j_logs, qdrant_storage, n8n_data"
	@echo ""
	@echo "All data will be permanently lost. Press Ctrl-C to cancel."
	@echo "Continuing in 5 seconds..."
	@sleep 5
	docker compose down -v

## migrate: Run Flyway SQL migrations against postgres
migrate:
	docker compose run --rm flyway migrate

## logs: Stream logs from all running services
logs:
	docker compose logs -f

## ps: Show status of all services
ps:
	docker compose ps

## health: Check health status of all running services
health:
	@echo ""
	@echo "Service Health Status"
	@echo "====================="
	@docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || \
		docker compose ps
	@echo ""
