#!/usr/bin/env bash
# Native Part A production E2E gate. This starts isolated PostgreSQL and Redis
# processes under a temporary directory, so developer services are untouched.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
PGHOST="${ZT_E2E_PG_HOST:-127.0.0.1}"
PGPORT="${ZT_E2E_PG_PORT:-15432}"
PGUSER="${PGUSER:-$(id -un)}"
DB="zerotrace_e2e_${$}_$(date +%s)"
REDIS_HOST="${ZT_E2E_REDIS_HOST:-127.0.0.1}"
REDIS_PORT="${ZT_E2E_REDIS_PORT:-16379}"
GATEWAY_PORT="${ZT_E2E_GATEWAY_PORT:-18000}"
UPSTREAM_PORT="${ZT_E2E_UPSTREAM_PORT:-19001}"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/zerotrace-e2e.XXXXXX")"
LOGS="$TMP/logs"
ARTIFACTS="$TMP/artifacts"
EVIDENCE="$ROOT/../evidence"
PGDATA="$TMP/postgres"
GATEWAY_PID=""
UPSTREAM_PID=""
REDIS_PID=""
PG_STARTED=0
PG_STOPPED=0

fail() { echo "ERROR: $*" >&2; exit 2; }
require_command() {
  command -v "$1" >/dev/null 2>&1 ||
    fail "$1 is required for part-a-e2e (install PostgreSQL/Redis and ensure its binaries are on PATH)"
}

for command in initdb pg_ctl psql createdb redis-server redis-cli; do require_command "$command"; done
[[ -x "$PY" ]] || fail "Python executable not found at $PY (run make venv first)"
"$PY" -c 'import uvicorn' >/dev/null 2>&1 || fail "uvicorn is unavailable in $PY"

mkdir -p "$LOGS" "$ARTIFACTS" "$EVIDENCE/04_jtbd"
rm -f "$EVIDENCE/04_jtbd/EV-PA-01-part-a-e2e.json" "$EVIDENCE/04_jtbd/EV-PA-01-part-a-e2e.json.tmp"

cleanup() {
  set +e
  [[ -n "$GATEWAY_PID" ]] && kill "$GATEWAY_PID" 2>/dev/null || true
  [[ -n "$UPSTREAM_PID" ]] && kill "$UPSTREAM_PID" 2>/dev/null || true
  if [[ -n "$REDIS_PID" ]]; then
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" shutdown nosave >/dev/null 2>&1 ||
      kill "$REDIS_PID" 2>/dev/null || true
  fi
  if [[ "$PG_STARTED" == 1 ]]; then
    pg_ctl -D "$PGDATA" -w stop -m fast >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP"
}
trap cleanup EXIT INT TERM

initdb -D "$PGDATA" --auth=trust --username="$PGUSER" --no-locale --encoding=UTF8 \
  >"$LOGS/postgres-initdb.log" 2>&1 ||
  fail "could not initialize isolated PostgreSQL cluster at $PGDATA"
pg_ctl -D "$PGDATA" -w start -o "-h $PGHOST -p $PGPORT" -l "$LOGS/postgres.log" >/dev/null ||
  fail "could not start isolated PostgreSQL at $PGHOST:$PGPORT"
PG_STARTED=1
for _ in $(seq 1 60); do
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -w -c 'select 1' >/dev/null 2>&1 && break
  sleep 0.25
done
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -w -c 'select 1' >/dev/null 2>&1 ||
  fail "isolated PostgreSQL did not become ready at $PGHOST:$PGPORT"
createdb -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -w "$DB" ||
  fail "could not create isolated PostgreSQL database $DB"

export ZT_ENV=prod
export ZT_PG_DSN="postgresql+asyncpg://${PGUSER}@${PGHOST}:${PGPORT}/${DB}"
export ZT_REDIS_URL="redis://${REDIS_HOST}:${REDIS_PORT}/0"
export ZT_OIDC_ISSUER=http://e2e-oidc-stub.invalid
export ZT_OIDC_CLIENT_ID=zerotrace
export ZT_OIDC_CLIENT_SECRET=e2e-zt-test-secret-7f3a9c1e4b8d2f6a0c5e9b1d
export ZT_OIDC_STUB_ENABLED=true
export ZT_UPSTREAM=passthrough
export ZT_UPSTREAM_BASE_URL="http://127.0.0.1:${UPSTREAM_PORT}"
export ZT_E2E_GATEWAY_URL="http://127.0.0.1:${GATEWAY_PORT}"
export ZT_E2E_UPSTREAM_URL="http://127.0.0.1:${UPSTREAM_PORT}"
export ZT_E2E_ARTIFACTS_DIR="$ARTIFACTS"
export ZT_E2E_LOGS_DIR="$LOGS"
export ZT_E2E_EVIDENCE_DIR="$EVIDENCE"

run_migrations() { (cd "$ROOT" && "$PY" -m alembic upgrade head && "$PY" -m scripts.seed_demo); }
wait_http() {
  local url="$1"; local attempts=0
  until "$PY" -c 'import sys,urllib.request; urllib.request.urlopen(sys.argv[1], timeout=1)' "$url" >/dev/null 2>&1; do
    attempts=$((attempts + 1)); (( attempts < 60 )) || fail "service did not become ready: $url"; sleep 0.5
  done
}
start_upstream() {
  (cd "$ROOT" && exec "$PY" -m uvicorn tests.e2e.upstream_app:app --host 127.0.0.1 --port "$UPSTREAM_PORT" --workers 1) >"$LOGS/upstream.log" 2>&1 & UPSTREAM_PID=$!
  wait_http "http://127.0.0.1:${UPSTREAM_PORT}/healthz"
}
start_gateway() {
  (cd "$ROOT" && exec "$PY" -m uvicorn tests.e2e.app:app --host 127.0.0.1 --port "$GATEWAY_PORT" --workers 1) >"$LOGS/gateway.log" 2>&1 & GATEWAY_PID=$!
  wait_http "http://127.0.0.1:${GATEWAY_PORT}/readyz"
}
stop_gateway() { [[ -z "$GATEWAY_PID" ]] || kill "$GATEWAY_PID" 2>/dev/null || true; wait "$GATEWAY_PID" 2>/dev/null || true; GATEWAY_PID=""; }
stop_upstream() { [[ -z "$UPSTREAM_PID" ]] || kill "$UPSTREAM_PID" 2>/dev/null || true; wait "$UPSTREAM_PID" 2>/dev/null || true; UPSTREAM_PID=""; }
stop_redis() {
  [[ -z "$REDIS_PID" ]] && return
  redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" shutdown nosave >/dev/null 2>&1 || kill "$REDIS_PID" 2>/dev/null || true
  REDIS_PID=""
}
start_redis() {
  rm -f "$TMP/redis.pid"
  redis-server --bind "$REDIS_HOST" --port "$REDIS_PORT" --save '' --appendonly no \
    --daemonize yes --pidfile "$TMP/redis.pid" --logfile "$LOGS/redis.log"
  REDIS_PID="$(cat "$TMP/redis.pid")"
  for _ in $(seq 1 30); do redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping >/dev/null 2>&1 && return; sleep 0.2; done
  fail "isolated Redis did not become ready at $REDIS_HOST:$REDIS_PORT"
}
stop_postgres() { pg_ctl -D "$PGDATA" -w stop -m fast >/dev/null || fail "could not stop PostgreSQL natively"; PG_STOPPED=1; }
start_postgres() { pg_ctl -D "$PGDATA" -w start >/dev/null || fail "could not restart PostgreSQL natively"; PG_STOPPED=0; }
run_phase() { echo "== E2E phase: $1 =="; (cd "$ROOT" && "$PY" -m tests.e2e.runner --phase "$1"); }

run_migrations
start_redis
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n 0 FLUSHDB >/dev/null
[[ -z "$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n 0 --scan --pattern 'zt:policy:*')" ]] || fail "policy keys present at gate start"
start_upstream
start_gateway
run_phase s4
run_phase before-restart
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n 0 FLUSHDB >/dev/null
[[ -z "$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n 0 --scan --pattern 'zt:policy:*')" ]] || fail "policy keys remain after Redis flush"
stop_redis
stop_gateway
start_gateway
run_phase redis-down
start_redis
stop_gateway
start_gateway
run_phase after-restart
stop_postgres
run_phase postgres-down
start_postgres
run_phase recovered
run_phase load
stop_gateway
stop_upstream
run_phase audit
[[ -s "$EVIDENCE/04_jtbd/EV-PA-01-part-a-e2e.json" ]] || fail "audit passed but canonical report is missing"
"$PY" -c 'import json,sys; p=json.load(open(sys.argv[1])); assert p.get("status")=="pass"' "$EVIDENCE/04_jtbd/EV-PA-01-part-a-e2e.json" || fail "canonical report does not declare status pass"
echo "EV-PA-01 evidence published: $EVIDENCE/04_jtbd/EV-PA-01-part-a-e2e.json"
