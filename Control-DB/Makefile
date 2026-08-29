# ZeroTrace Part A.
#
# Two ways to run this. Both are supported.
#
#   make dev     Docker Compose — postgres 16 + redis 7 + gateway. The real
#                stack, the one CODE-01 §1 specifies.
#   make local   A venv on this machine against SQLite. No Docker needed. The
#                declared dev/test dialect — see SUBMISSION.md.
#
# Every milestone target exits non-zero on failure. No milestone starts before
# the one before it is green.

PY      := .venv/bin/python
ifeq ($(OS),Windows_NT)
PY      := .venv/Scripts/python.exe
endif
COMPOSE := docker compose

.DEFAULT_GOAL := help
.PHONY: help dev down logs local venv migrate seed test verify m0 m1 m2 part-a demo clean

help:
	@echo "Part A — the control-group DB"
	@echo ""
	@echo "  make dev      bring up postgres + redis + gateway (Docker)"
	@echo "  make local    set up the venv + SQLite database (no Docker)"
	@echo "  make test     the whole suite"
	@echo "  make verify   walk the ledger chain and recompute every hash"
	@echo "  make part-a   M0, then M1, then M2, then the acceptance test"
	@echo "  make demo     seed, then show the two-actor difference"

# --- Docker path ----------------------------------------------------------

dev:
	@test -f .env || cp .env.example .env
	$(COMPOSE) build
	$(COMPOSE) up -d postgres redis
	$(COMPOSE) run --rm migrate
	$(COMPOSE) up -d gateway
	@echo ""
	@echo "gateway   http://localhost:8000"
	@echo "openapi   http://localhost:8000/docs"
	@echo "health    http://localhost:8000/healthz"

down:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f gateway

# --- local path -----------------------------------------------------------

venv:
	python -m venv .venv
	$(PY) -m pip install --upgrade pip pip-tools
	$(PY) -m pip install -r requirements.txt

local: venv migrate seed
	@echo "local database ready. Start the gateway with:"
	@echo "  ZT_PG_DSN=sqlite+aiosqlite:///./zerotrace.db $(PY) -m uvicorn zerotrace.gateway.app:app --reload"

migrate:
	$(PY) -m alembic upgrade head

seed:
	$(PY) -m scripts.seed_demo

# --- gates ----------------------------------------------------------------

test:
	$(PY) -m pytest

verify:
	$(PY) -m scripts.verify_ledger

m0:
	@echo "== M0: skeleton up =="
	$(PY) -m pytest tests/test_m0_bootstrap.py

m1:
	@echo "== M1: control-group DB =="
	$(PY) -m pytest tests/test_m1_identity.py

m2:
	@echo "== M2: policy engine =="
	$(PY) -m pytest tests/test_m2_policy.py tests/test_m2_lattice.py tests/test_ledger.py

part-a: m0 m1 m2
	@echo "== Part A acceptance (SKEL-01 A.5) =="
	$(PY) -m pytest tests/test_part_a_acceptance.py tests/test_privacy_invariant.py -v
	@echo ""
	@echo "Part A is done: two actors, one request, two answers, both in the ledger."

demo:
	$(PY) -m scripts.demo_two_actors

clean:
	rm -rf .venv zerotrace.db .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} +
