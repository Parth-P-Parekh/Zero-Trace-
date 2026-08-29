#!/usr/bin/env bash
# Route Claude Code through ZeroTrace. SKEL-01 §C.1 (rung 1).
#
# The gateway holds the real key; Claude Code never sees it. The session id is minted
# HERE, per launch -- not per request (the codename would change every turn, breaking
# both referential stability and the upstream prompt cache) and not per actor forever
# (the codename becomes a permanent tracking tag). See CODE-01 §7.1.
set -euo pipefail

: "${ZT_GATEWAY:=http://localhost:8080}"

if ! curl -sf "${ZT_GATEWAY}/healthz" >/dev/null 2>&1; then
  echo "zt: gateway unreachable at ${ZT_GATEWAY} -- refusing to launch unprotected." >&2
  echo "zt: start it with  uvicorn gateway.app:app --port 8080" >&2
  exit 1
fi

export ANTHROPIC_BASE_URL="${ZT_GATEWAY}"
export ZT_SESSION="${ZT_SESSION:-$(uuidgen 2>/dev/null || date +%s%N)}"

echo "zt: proxying Claude Code via ${ZT_GATEWAY} (session ${ZT_SESSION:0:8})" >&2
exec claude "$@"
