.DEFAULT_GOAL := help
SHELL := /usr/bin/env bash

DEV_COMPOSE      := docker compose -p vdl-dev -f docker-compose.dev.yml --env-file .env.dev
PROD_COMPOSE     := docker compose -p vdl-prod -f docker-compose.prod.yml --env-file .env.prod
PROD_EXT_COMPOSE := docker compose -p vdl-prod -f docker-compose.prod.yml -f docker-compose.prod.external-net.yml --env-file .env.prod
EXTERNAL_NET     ?= proxy_net
API_BASE_URL     ?= http://127.0.0.1:8000
DOMAIN           ?= fastdownloading.solaymanbuilds.com
LETSENCRYPT_EMAIL?= elmouden00den@gmail.com

CYAN  := \033[36m
GREEN := \033[32m
YELLOW:= \033[33m
RESET := \033[0m

.PHONY: help setup network \
        dev dev-d dev-down dev-logs dev-restart dev-shell-api dev-shell-web \
        vps-setup vps-setup-external ssl-setup ssl-renew \
        prod-build prod-up prod-up-external prod-down prod-restart prod-logs prod-ps \
        update prod-update deploy rollback \
        test test-int lint format audit smoke bench update-ytdlp cookies-check clean nuke

help: ## List all targets with descriptions
	@echo -e "$(GREEN)FastDL — Production Video Downloader Makefile$(RESET)"
	@echo -e "Dev project: $(CYAN)vdl-dev$(RESET) | Prod project: $(CYAN)vdl-prod$(RESET) | Domain: $(CYAN)$(DOMAIN)$(RESET)"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_-]+:.*?## / {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Copy .env examples, create secrets/cookies dir & external network
	@DOMAIN="$(DOMAIN)" LETSENCRYPT_EMAIL="$(LETSENCRYPT_EMAIL)" bash scripts/setup.sh
	@$(MAKE) network

network: ## Create the external docker proxy network if missing
	@docker network inspect $(EXTERNAL_NET) >/dev/null 2>&1 || docker network create $(EXTERNAL_NET)
	@echo -e "$(GREEN)Network '$(EXTERNAL_NET)' is ready.$(RESET)"

# ------------------------------------------------------------------
# Development targets (vdl-dev)
# ------------------------------------------------------------------
dev: ## Build and start development stack (attached logs)
	@$(DEV_COMPOSE) up --build

dev-d: ## Build and start development stack detached
	@$(DEV_COMPOSE) up --build -d
	@echo -e "$(GREEN)Dev stack running:$(RESET) Web http://localhost:3000 | API http://localhost:8000/api/docs"

dev-down: ## Stop development stack
	@$(DEV_COMPOSE) down

dev-logs: ## Follow development logs
	@$(DEV_COMPOSE) logs -f

dev-restart: ## Restart development services
	@$(DEV_COMPOSE) restart

dev-shell-api: ## Open interactive shell inside backend dev container
	@$(DEV_COMPOSE) exec api bash

dev-shell-web: ## Open interactive shell inside frontend dev container
	@$(DEV_COMPOSE) exec frontend sh

# ------------------------------------------------------------------
# Production targets (vdl-prod)
# ------------------------------------------------------------------
vps-setup: ## Turnkey VPS setup: Docker, .env.prod, build, start & Let's Encrypt HTTPS (fastdownloading.solaymanbuilds.com)
	@DOMAIN="$(DOMAIN)" LETSENCRYPT_EMAIL="$(LETSENCRYPT_EMAIL)" bash scripts/vps_setup.sh

vps-setup-external: ## Turnkey VPS setup for shared external proxy_net (zero host ports)
	@DOMAIN="$(DOMAIN)" LETSENCRYPT_EMAIL="$(LETSENCRYPT_EMAIL)" NETWORK_MODE=external bash scripts/vps_setup.sh

ssl-setup: ## Issue Let's Encrypt cert (fastdownloading.solaymanbuilds.com / elmouden00den@gmail.com), enable HTTPS & cron
	@DOMAIN="$(DOMAIN)" LETSENCRYPT_EMAIL="$(LETSENCRYPT_EMAIL)" bash scripts/ssl_setup.sh issue

ssl-renew: ## Renew Let's Encrypt TLS certificates and reload Nginx
	@bash scripts/ssl_setup.sh renew

prod-build: ## Build production images (with --pull when registry reachable)
	@$(PROD_COMPOSE) build --pull || $(PROD_COMPOSE) build || \
	  (docker image inspect vdl-backend:latest >/dev/null 2>&1 && docker image inspect vdl-frontend:latest >/dev/null 2>&1 && echo "Using locally built vdl-backend:latest and vdl-frontend:latest images.")

prod-up: ## Start production stack detached (bundled Nginx)
	@$(PROD_COMPOSE) up -d --wait
	@echo -e "$(GREEN)Prod stack started. Run 'make prod-ps' to inspect health.$(RESET)"

prod-up-external: ## Start production stack attached to external proxy_net (no host ports)
	@$(MAKE) network
	@$(PROD_EXT_COMPOSE) up -d --wait
	@echo -e "$(GREEN)Prod stack started on external network '$(EXTERNAL_NET)'.$(RESET)"

prod-down: ## Stop production stack
	@$(PROD_COMPOSE) down

prod-restart: ## Rolling restart of production services with healthcheck wait
	@$(PROD_COMPOSE) up -d --force-recreate --wait

prod-logs: ## Follow production logs
	@$(PROD_COMPOSE) logs -f

prod-ps: ## Show status and health of production services
	@$(PROD_COMPOSE) ps

update: ## Pull latest git commits, sync .env.prod, rebuild, rolling update & auto-rollback on failure
	@bash scripts/update.sh

prod-update: update ## Alias for 'make update'

deploy: ## Pull latest code, update production stack, prune, and run 4-platform smoke tests
	@bash scripts/update.sh --smoke

rollback: ## Redeploy the previous production image tag
	@set -e; \
	docker image inspect vdl-backend:previous >/dev/null 2>&1 || { echo "No vdl-backend:previous image found"; exit 1; }; \
	docker image inspect vdl-frontend:previous >/dev/null 2>&1 || { echo "No vdl-frontend:previous image found"; exit 1; }; \
	IMAGE_TAG=previous $(PROD_COMPOSE) up -d --wait
	@echo -e "$(YELLOW)Rolled back to 'previous' images.$(RESET)"

# ------------------------------------------------------------------
# Quality, Tests, Security, Operations
# ------------------------------------------------------------------
test: ## Run backend and frontend unit tests
	@docker image inspect vdl-backend:dev >/dev/null 2>&1 || docker build --target dev -f docker/backend.Dockerfile -t vdl-backend:dev . >/dev/null
	@docker run --rm -v "$$PWD/backend:/app" vdl-backend:dev pytest tests/unit -v
	@cd frontend && npm test

test-int: ## Run backend integration tests (mocked extractors + Redis + worker)
	@docker image inspect vdl-backend:dev >/dev/null 2>&1 || docker build --target dev -f docker/backend.Dockerfile -t vdl-backend:dev . >/dev/null
	@docker run --rm -v "$$PWD/backend:/app" vdl-backend:dev pytest tests/integration -v

lint: ## Run ruff + mypy + eslint + prettier + tsc checks
	@docker run --rm -v "$$PWD/backend:/app" vdl-backend:dev bash -c "ruff check app tests && mypy app"
	@cd frontend && npm run typecheck && npm run lint

format: ## Auto-format backend (ruff) and frontend (prettier)
	@docker run --rm -v "$$PWD/backend:/app" vdl-backend:dev bash -c "ruff check --fix app tests && ruff format app tests"
	@cd frontend && npm run format

audit: ## Run dependency vulnerability scans (pip-audit + npm audit)
	@docker run --rm -v "$$PWD/backend:/app" vdl-backend:dev pip-audit --skip-editable
	@cd frontend && npm audit --audit-level=high

smoke: ## Run real-world smoke tests per platform (scripts/smoke_urls.txt)
	@API_BASE_URL="$(API_BASE_URL)" bash scripts/smoke.sh

bench: ## Run download speed benchmark (TTFB, total time, MB/s) per platform
	@API_BASE_URL="$(API_BASE_URL)" bash scripts/bench.sh

update-ytdlp: ## Update yt-dlp inside running containers with self-test & rollback
	@bash scripts/update_ytdlp.sh

cookies-check: ## Validate mounted Netscape cookies for each platform
	@bash scripts/cookies_check.sh

clean: ## Remove temp files, stopped containers, and dangling images
	@rm -rf backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache frontend/.next
	@docker container prune -f
	@docker image prune -f

nuke: ## Full reset of dev & prod stacks and volumes (asks confirmation)
	@read -p "This deletes ALL vdl-dev and vdl-prod containers and volumes. Continue? [y/N] " ans; \
	if [ "$$ans" = "y" ] || [ "$$ans" = "Y" ]; then \
		$(DEV_COMPOSE) down -v --remove-orphans || true; \
		$(PROD_COMPOSE) down -v --remove-orphans || true; \
		docker image rm -f vdl-backend:dev vdl-backend:latest vdl-frontend:dev vdl-frontend:latest 2>/dev/null || true; \
		echo -e "$(YELLOW)Full reset complete.$(RESET)"; \
	else \
		echo "Aborted."; \
	fi
