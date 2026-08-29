# Route Claude Code through ZeroTrace. SKEL-01 §C.1 (rung 1).
# Session id is minted per launch -- see zt-claude.sh for why.
$ErrorActionPreference = "Stop"
if (-not $env:ZT_GATEWAY) { $env:ZT_GATEWAY = "http://localhost:8080" }

try   { Invoke-WebRequest -Uri "$($env:ZT_GATEWAY)/healthz" -UseBasicParsing -TimeoutSec 2 | Out-Null }
catch {
  Write-Error "zt: gateway unreachable at $($env:ZT_GATEWAY) -- refusing to launch unprotected.`nzt: start it with  uvicorn gateway.app:app --port 8080"
  exit 1
}

$env:ANTHROPIC_BASE_URL = $env:ZT_GATEWAY
if (-not $env:ZT_SESSION) { $env:ZT_SESSION = [guid]::NewGuid().ToString() }
Write-Host "zt: proxying Claude Code via $($env:ZT_GATEWAY) (session $($env:ZT_SESSION.Substring(0,8)))"
& claude @args
