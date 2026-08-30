#!/usr/bin/env bash
# Route Codex CLI through ZeroTrace. SKEL-01 §C.3 (rung 3).
# Same pattern as zt-claude.sh -- Codex respects OPENAI_BASE_URL.
set -euo pipefail
: "${ZT_GATEWAY:=http://localhost:8080}"
curl -sf "${ZT_GATEWAY}/healthz" >/dev/null || { echo "zt: gateway down; refusing." >&2; exit 1; }
export OPENAI_BASE_URL="${ZT_GATEWAY}/v1"
export ZT_SESSION="${ZT_SESSION:-$(uuidgen 2>/dev/null || date +%s%N)}"
echo "zt: proxying Codex via ${ZT_GATEWAY}" >&2
exec codex "$@"
