# BetterBundle
#
# ENV selects the compose file: dev (default), local, prod.
#   make up              → docker-compose.dev.yml
#   make up ENV=local    → docker-compose.local.yml
#
# Defaults to dev because that is the stack that actually runs here. It used to
# default to local, which pointed every target at a compose file whose services
# were not up: `exec` still found the containers (same project name), so
# migrations appeared to work, but `logs python-worker` failed with "no such
# service" — which is why the worker's logs looked empty when they were fine.
#
# Anything that talks to a real Shopify store needs SHOP and TOKEN passed in.

ENV ?= dev
COMPOSE := docker compose -f docker-compose.$(ENV).yml
WORKER  := $(COMPOSE) exec python-worker

# Local, gitignored overrides — chiefly SHOP_DOMAIN and ACCESS_TOKEN so the
# store targets need no arguments. Absent file is fine (the leading dash).
# Path is relative to this Makefile, so `make -C` and bare `make` behave alike.
-include $(dir $(lastword $(MAKEFILE_LIST))).env.local

# Anything passed on the command line still wins over the file.
SHOP  ?= $(SHOP_DOMAIN)
TOKEN ?= $(ACCESS_TOKEN)

.DEFAULT_GOAL := help

# ==================== stack ====================

up:  ## Start the stack (detached)
	$(COMPOSE) up -d

up-build:  ## Rebuild images, then start
	$(COMPOSE) up -d --build

down:  ## Stop the stack
	$(COMPOSE) down

nuke:  ## Stop the stack AND delete its volumes (destroys the database)
	$(COMPOSE) down -v

ps:  ## Show container status
	$(COMPOSE) ps

logs:  ## Tail all logs
	$(COMPOSE) logs -f

logs-worker:  ## Tail python-worker logs only
	$(COMPOSE) logs -f python-worker

shell:  ## Open a shell in python-worker
	$(WORKER) bash

# ==================== database ====================

migrate:  ## Apply pending Alembic migrations
	$(WORKER) python -m app.core.database.migrations upgrade

migrate-stamp:  ## Mark an existing (pre-Alembic) database as up to date, without running migrations
	$(WORKER) python -m app.core.database.migrations stamp

migrate-check:  ## Fail if the models have drifted from the migrations
	$(WORKER) alembic check

psql:  ## Open psql against the stack's database
	$(COMPOSE) exec postgres psql -U postgres -d betterbundle

shop-tokens:  ## Print shop_domain + access_token for installed shops
	$(COMPOSE) exec -T postgres psql -U postgres -d betterbundle -tAc \
	  "select shop_domain || ' ' || access_token from shops"

# ==================== seeds ====================

seed-plans:  ## Seed the subscription plan (pricing terms)
	# DATABASE_URL is passed explicitly: `compose exec` does not carry the
	# service's env_file through, and the script's dotenv fallback points at
	# localhost, which is not where Postgres lives from inside the container.
	$(COMPOSE) exec \
	  -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/betterbundle \
	  python-worker python -m app.scripts.seed_subscription_plans

# ==================== shopify store data ====================
# These hit the live Shopify Admin API. Dev stores only.
#   make store-seed
#   make store-delete
#
# SHOP/TOKEN come from .env.local (SHOP_DOMAIN / ACCESS_TOKEN); override on the
# command line for a one-off store. The token is the shop's Admin API token —
# if the app is installed, it is in the `sessions` table, see `make shop-tokens`.

# Both targets need the same pair, so the guard is shared.
define require_shop
$(if $(SHOP),,$(error SHOP is not set — put SHOP_DOMAIN in .env.local, or pass SHOP=my-store.myshopify.com))
$(if $(TOKEN),,$(error TOKEN is not set — put ACCESS_TOKEN in .env.local, or pass TOKEN=shpat_xxx))
endef

# The shop-* targets read our own database, so they need no Shopify token.
define require_shop_only
$(if $(SHOP),,$(error SHOP is not set — put SHOP_DOMAIN in .env.local, or pass SHOP=my-store.myshopify.com))
endef

# `compose exec` does not carry the service's env_file through, and the
# scripts' dotenv fallback points at localhost.
DB_ENV := -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/betterbundle

STORE_ENV := -e SHOP_DOMAIN=$(SHOP) -e ACCESS_TOKEN=$(TOKEN)

store-seed:  ## Seed products/collections/customers/orders into a Shopify store
	$(require_shop)
	$(COMPOSE) exec $(STORE_ENV) \
	  python-worker python -m app.scripts.seed_shopify_graphql

store-delete:  ## Delete ALL products/orders/customers/media from a Shopify store (irreversible)
	$(require_shop)
	@printf 'This deletes ALL data from %s and cannot be undone.\nType DELETE ALL to continue: ' '$(SHOP)'
	@read -r reply; [ "$$reply" = "DELETE ALL" ] || { echo "Aborted."; exit 1; }
	$(COMPOSE) exec $(STORE_ENV) \
	  python-worker python -m app.scripts.delete_store_data

store-reseed: store-delete store-seed  ## Wipe the store, then seed it fresh

# ==================== our data for one shop ====================
# These touch BetterBundle's own database only — never the Shopify store.
# Use them to re-run onboarding from scratch: purge, then press Start Free.
#
# The Shopify OAuth session and the global subscription_plans row are left
# alone, so the app stays installed and onboarding can still find a plan.

shop-purge-dry:  ## Show what shop-purge would delete (deletes nothing)
	$(require_shop_only)
	$(COMPOSE) exec $(DB_ENV) python-worker \
	  python -m app.scripts.delete_shop_data --shop $(SHOP) --dry-run

shop-purge:  ## Delete all BetterBundle data for SHOP, so onboarding can re-run
	$(require_shop_only)
	@printf 'This deletes every BetterBundle row for %s.\nThe Shopify store itself is untouched. Type PURGE to continue: ' '$(SHOP)'
	@read -r reply; [ "$$reply" = "PURGE" ] || { echo "Aborted."; exit 1; }
	$(COMPOSE) exec $(DB_ENV) python-worker \
	  python -m app.scripts.delete_shop_data --shop $(SHOP)

shop-reset:  ## Clear pipeline data for SHOP, keeping the install and the paid LLM cache
	$(require_shop_only)
	@printf 'This clears all pipeline data for %s and resets onboarding.\nType RESET to continue: ' '$(SHOP)'
	@read -r reply; [ "$$reply" = "RESET" ] || { echo "Aborted."; exit 1; }
	# --keep-enrichment: the LLM output is the only artifact that cost money,
	# and its cache key includes the product id, so it stays valid as long as
	# the Shopify catalog is not reseeded. Embeddings are rebuilt locally.
	$(COMPOSE) exec $(DB_ENV) python-worker \
	  python -m app.scripts.delete_shop_data --shop $(SHOP) --keep-shop --keep-enrichment

shop-reset-hard:  ## Like shop-reset but also drops the LLM cache (re-pays Gemini)
	$(require_shop_only)
	@printf 'This clears pipeline data AND the paid LLM enrichment cache for %s.\nType RESET to continue: ' '$(SHOP)'
	@read -r reply; [ "$$reply" = "RESET" ] || { echo "Aborted."; exit 1; }
	$(COMPOSE) exec $(DB_ENV) python-worker \
	  python -m app.scripts.delete_shop_data --shop $(SHOP) --keep-shop

# ==================== outreach (streamlit) ====================
OUTREACH_DIR := outreach
OUTREACH_VENV := .venv

outreach-install:  ## Install outreach streamlit app dependencies
	python3 -m venv $(OUTREACH_DIR)/$(OUTREACH_VENV)
	$(OUTREACH_DIR)/$(OUTREACH_VENV)/bin/pip install -r $(OUTREACH_DIR)/requirements.txt

outreach:  ## Run the Skuvio Outreach Streamlit app
	cd $(OUTREACH_DIR) && $(OUTREACH_VENV)/bin/streamlit run app.py --server.headless true --server.runOnSave true --server.fileWatcherType auto

# ==================== remix app ====================

app-dev:  ## Run the Shopify app with the CLI's own tunnel
	cd better-bundle && npm run dev:tunnel

app-deploy:  ## Deploy extensions and app config to Shopify
	cd better-bundle && npm run deploy:$(ENV)

app-db-pull:  ## Regenerate the Prisma client from the live schema
	cd better-bundle && npm run db:pull

app-test:  ## Run the Remix test suite
	cd better-bundle && npm test

# ==================== tests ====================

test:  ## Run the python-worker test suite
	$(WORKER) pytest

# ==================== meta ====================

help:  ## List targets
	@grep -hE '^[a-z-]+:.*?##' $(MAKEFILE_LIST) \
	  | awk -F':.*?## ' '{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: up up-build down nuke ps logs logs-worker shell \
        migrate migrate-stamp migrate-check psql shop-tokens \
        seed-plans store-seed store-delete store-reseed \
        shop-purge shop-purge-dry shop-reset shop-reset-hard \
        app-dev app-deploy app-db-pull app-test test \
        outreach-install outreach help
