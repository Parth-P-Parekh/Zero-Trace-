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

# The Part A production-mode E2E gate (EV-PA-01) runs natively against
# temporary, isolated PostgreSQL and Redis processes. The helper owns the
# cluster, database, localhost processes, temporary logs, and evidence.
E2E_REPORT := ../evidence/04_jtbd/EV-PA-01-part-a-e2e.json
E2E_REPORT_TMP := ../evidence/04_jtbd/EV-PA-01-part-a-e2e.json.tmp


# The two logical chains per tenant (004): ctl = control-plane evidence,
# dp = data-plane evidence. `make verify` checks both.
.PHONY: help dev down logs local venv migrate seed test verify verify-ctl verify-dp m0 m1 m2 part-a part-a-e2e demo clean

help:
	@echo "Part A — the control-group DB"
	@echo ""
	@echo "  make dev      bring up postgres + redis + gateway (Docker)"
	@echo "  make local    set up the venv + SQLite database (no Docker)"
	@echo "  make test     the whole suite"
	@echo "  make verify   verify both ledger chains (ctl + dp)"
	@echo "  make verify-ctl   verify the control-plane chain only"
	@echo "  make verify-dp    verify the data-plane chain only"
	@echo "  make part-a   M0, M1, M2, acceptance gates, then the production E2E gate"
	@echo "  make part-a-e2e   production-mode E2E gate (EV-PA-01, native PostgreSQL + Redis)"
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
	$(PY) -m pip install --editable .
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

verify-ctl:
	$(PY) -m scripts.verify_ledger --chain ctl

verify-dp:
	$(PY) -m scripts.verify_ledger --chain dp

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
	@echo "== Part A unit and integration gates =="
	$(PY) -m pytest tests/test_spans_and_redaction.py tests/test_part_a_acceptance.py tests/test_privacy_invariant.py tests/test_m3_production_schema.py tests/test_control_auth.py tests/test_s4_budget.py -v
	@echo "== Part A production E2E gate (EV-PA-01) =="
	$(MAKE) part-a-e2e

part-a-e2e:
	@echo "== Part A production-mode E2E (native isolated stack, EV-PA-01) =="
	@./scripts/native_e2e.sh
	@echo "EV-PA-01 evidence published: $(E2E_REPORT)"

demo:
	$(PY) -m scripts.demo_two_actors

clean:
	rm -rf .venv zerotrace.db .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} +
