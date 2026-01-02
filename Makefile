# NoobBook Makefile
# Provides commands for local development and Docker containerization

.PHONY: help setup clean

# Default target
help: ## Show this help message
	@echo "NoobBook Development Commands"
	@echo "============================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Setup and Prerequisites
setup: ## Setup local development environment
	@chmod +x scripts/dev/*.sh scripts/docker/*.sh scripts/prod/*.sh
	@./scripts/dev/setup.sh

# Local Development (Process-based)
dev-backend: ## Start backend locally (faster for development)
	@./scripts/dev/start-backend.sh

dev-frontend: ## Start frontend locally (faster for development)
	@./scripts/dev/start-frontend.sh

dev-local: ## Start both backend and frontend locally
	@echo "🚀 Starting NoobBook Local Development"
	@echo "Backend will start on http://localhost:5000"
	@echo "Frontend will start on http://localhost:5173"
	@echo ""
	@echo "Starting backend in background..."
	@./scripts/dev/start-backend.sh &
	@sleep 5
	@echo "Starting frontend..."
	@./scripts/dev/start-frontend.sh

# Docker Development
docker-build-dev: ## Build development Docker images
	@./scripts/docker/build-dev.sh

docker-dev: ## Start development environment with Docker
	@echo "🐳 Starting NoobBook Development (Docker)"
	@docker-compose up --build

docker-dev-bg: ## Start development environment with Docker in background
	@echo "🐳 Starting NoobBook Development (Docker) in background"
	@docker-compose up --build -d

# Docker Production
docker-build-prod: ## Build production Docker images
	@./scripts/docker/build-prod.sh

docker-prod: ## Start production environment with Docker
	@echo "🐳 Starting NoobBook Production (Docker)"
	@docker-compose -f docker-compose.prod.yml up -d

deploy-prod: ## Deploy to production
	@./scripts/prod/deploy.sh

# Logs and Monitoring
logs: ## View development logs
	@docker-compose logs -f

logs-backend: ## View backend logs only
	@docker-compose logs -f backend

logs-frontend: ## View frontend logs only
	@docker-compose logs -f frontend

logs-prod: ## View production logs
	@docker-compose -f docker-compose.prod.yml logs -f

# Testing
test: ## Run all tests
	@echo "🧪 Running tests..."
	@docker-compose exec backend python -m pytest
	@docker-compose exec frontend npm test

test-backend: ## Run backend tests only
	@docker-compose exec backend python -m pytest

test-frontend: ## Run frontend tests only
	@docker-compose exec frontend npm test

# Utility Commands
shell-backend: ## Access backend container shell
	@docker-compose exec backend /bin/bash

shell-frontend: ## Access frontend container shell
	@docker-compose exec frontend /bin/sh

ps: ## Show running containers
	@docker-compose ps

# Cleanup Commands
stop: ## Stop development containers
	@docker-compose down

stop-prod: ## Stop production containers
	@docker-compose -f docker-compose.prod.yml down

clean: ## Remove all containers, images, and volumes
	@echo "🧹 Cleaning up Docker resources..."
	@docker-compose down -v --remove-orphans
	@docker-compose -f docker-compose.prod.yml down -v --remove-orphans
	@docker system prune -f
	@echo "✅ Cleanup complete"

clean-all: ## Remove everything including images
	@echo "🧹 Performing deep cleanup..."
	@docker-compose down -v --remove-orphans --rmi all
	@docker-compose -f docker-compose.prod.yml down -v --remove-orphans --rmi all
	@docker system prune -af
	@echo "✅ Deep cleanup complete"

# Health Checks
health: ## Check service health
	@echo "🏥 Checking service health..."
	@curl -f http://localhost:5000/health || echo "❌ Backend unhealthy"
	@curl -f http://localhost:5173 || echo "❌ Frontend unhealthy"

# Quick Start Commands
quick-start: setup docker-dev-bg ## Quick start for new developers
	@echo ""
	@echo "🎉 NoobBook is starting up!"
	@echo "Backend: http://localhost:5000"
	@echo "Frontend: http://localhost:5173"
	@echo ""
	@echo "Use 'make logs' to view logs"
	@echo "Use 'make stop' to stop services"

# Development workflow shortcuts
restart: stop docker-dev-bg ## Restart development environment

rebuild: ## Rebuild and restart development environment
	@docker-compose down
	@docker-compose up --build -d
