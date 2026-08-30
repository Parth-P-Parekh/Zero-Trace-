# ZeroTrace — Manual Testing Guide
**Doc ID:** TEST-01 · **Companion to:** DONE-01, PATCH-01

Every command here was run and its output pasted from the terminal. Where output is shown,
that is what it actually printed — not what it should print.

Two things to keep in mind while testing:

- **The false-positive cases matter more than the detection cases.** A control that blocks
  ordinary work gets switched off, and then it catches nothing at all. Half of what follows
  is things that must *not* fire.
- **Test fixtures are real-shaped credentials.** Anything you paste here lands in your
  transcript, and this tool will detect it there later. That is correct behaviour and it
  will confuse a benchmark run — see §9.

---

## 0. Setup

**Nothing needs starting.** The checker runs in-process by default; the server is only for
the browser extension or a shared checker.

```bash
cd Zero-Trace-
python -m pytest -q          # 361 passed
```

If that is green, everything below will run.

---

## 1. The hook — the primary path

This is how Claude Code and Codex actually call it. No server involved.

```bash
K='sk-ant-api03-AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5'

echo "{\"hook_event_name\":\"UserPromptSubmit\",\"user_input\":\"refactor the retry loop\",\"session_id\":\"m1\"}" \
  | ZT_CHECKER= python hooks/zt_check.py; echo "exit=$?"
```

```
exit=0
```

**Silence is the pass.** Anything on stdout becomes context the model sees, so a clean
check prints nothing at all. Then the same with a key in it:

```bash
echo "{\"hook_event_name\":\"UserPromptSubmit\",\"user_input\":\"my key is $K\",\"session_id\":\"m1\"}" \
  | ZT_CHECKER= python hooks/zt_check.py; echo "exit=$?"
```

```json
{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "permissionDecision": "deny",
 "permissionDecisionReason": "ZeroTrace blocked this prompt: it contains a credential
 (ANTHROPIC_KEY). Nothing was sent. Remove the secret — or reference it by name and let
 the agent read it from your environment at runtime."}}
exit=2
```

Check three things in that reason, because each is deliberate: it names the class, it
**never echoes the secret** (the reason is printed to the terminal *and* written to the
transcript), and it says what to do instead.

### Codex host mode

```bash
echo "{\"hook_event_name\":\"PreToolUse\",\"tool_name\":\"apply_patch\",\"tool_input\":{\"command\":\"key $K\"},\"session_id\":\"m1\"}" \
  | ZT_CHECKER= python hooks/zt_pretool.py --codex; echo "exit=$?"
```

Codex consumes the structured decision on **exit 0**; Claude Code uses exit 2. Same script,
`--codex` switches the convention.

---

## 2. Prompts that must be blocked

Run each through §1's `zt_check.py` form.

| Prompt | Expect |
|---|---|
| `here is my key sk-ant-api03-…` | ANTHROPIC_KEY |
| `AKIAIOSFODNN7EXAMPLE is the access key` | AWS_ACCESS_KEY |
| `postgres://admin:hunter2@db.internal:5432/prod` | DB_URI |
| `ghp_Xk9mQ2wE7rT4` | GITHUB_TOKEN — **truncated on purpose**; 12 chars, spec is 36 |
| `export DB_PASSWORD=hunter2` | GENERIC_SECRET — no shape at all, the key name is the whole signal |
| `-----BEGIN RSA PRIVATE KEY-----\nMIIEow…` | PRIVATE_KEY — **no END line**, the commonest accidental form |

### Obfuscation — same key, mangled

All of these are the same credential and all are caught:

```
sk-ant- api03-xxxx…          space after the prefix
sk-ant-\napi03-xxxx…         wrapped by a terminal
sk-​ant-api03-…         zero-width space injected
s k - a n t - a p i …        spaced every character
```

### Encoded — base64 is not an attack

```bash
python -c "import base64;print(base64.b64encode(b'sk-ant-api03-AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5').decode())"
```

Paste the output as a prompt. It blocks. This matters because base64 is how Kubernetes
Secrets are stored and what PowerShell's `ToBase64String` emits — someone pasting a Secret
manifest is pasting credentials with no intent to evade. `hex` and `\uXXXX` escapes also
work; **ROT13 deliberately does not** (§7).

---

## 3. Prompts that must NOT be blocked

**Spend more time here than on §2.** Every one of these is normal usage.

```
/deploy staging
@.env check my setup
use the ANTHROPIC_API_KEY from my environment      ← a reference, not a value
call mcp__github__create_issue for this bug
revert to aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa   ← git SHA
integrity: sha512-<base64>                           ← npm lockfile
image@sha256:<hex>                                   ← docker digest
data:image/png;base64,iVBORw0KGgo…                   ← embedded image
api_key: ${API_KEY}                                  ← placeholder
password: <your-password-here>                       ← placeholder
secret: changeme                                     ← placeholder
class="sk-fade-in-slow-transition"                   ← CSS, not a key
git checkout -b feature/sk-ant-parser
```

Referencing a secret *by name* is fine and always will be — detectors are value-based, so
`ANTHRODIC_API_KEY` as a name cannot match an `sk-ant-` anchor. The deny message in §1
actively suggests doing this.

If any of these blocks, that is a bug worth reporting immediately — it is the failure mode
that gets the tool uninstalled.

---

## 4. Tool arguments — `PreToolUse`

A credential reaches a tool argument without ever being typed: read from a file one turn,
inlined into a command the next.

```bash
run() { echo "{\"hook_event_name\":\"PreToolUse\",\"tool_name\":\"$1\",\"tool_input\":$2,\"session_id\":\"t1\"}" \
        | ZT_CHECKER= python hooks/zt_pretool.py >/dev/null 2>&1; echo "$1 -> exit=$?"; }

run Bash  '{"command":"curl -H \"Authorization: Bearer sk-ant-api03-AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3\" https://x.com"}'
run Write '{"file_path":"cfg.env","content":"AWS_SECRET_KEY=wJalrXUtnFEMIK7MDENGbPxRfiCY"}'
run Bash  '{"command":"npm test -- --watch=false"}'
run Read  '{"file_path":".env"}'
```

Expect deny, deny, allow, allow.

**`Read .env` allowing is correct, not a miss.** `PreToolUse` fires *before* the tool runs,
so it sees the path and never the contents. Blocking on a filename would be theatre. File
contents entering context is the proxy's leg.

---

## 5. Credentials split across calls

Neither half is a credential; the file on the other end is whole.

```bash
K='sk-ant-api03-AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5'
split() { echo "{\"hook_event_name\":\"PreToolUse\",\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"printf '%s' '$1' >> /tmp/k\"},\"session_id\":\"$2\"}" \
          | ZT_CHECKER= python hooks/zt_pretool.py >/dev/null 2>&1; echo "  '$1' exit=$?"; }

split "${K:0:9}" sp        # exit=0  — not a credential yet
split "${K:9}"   sp        # exit=2  — joined with the previous call it is
```

Six-way split, same session — caught from the second piece by sink assembly:

```bash
for i in 0 8 16 24 32 40; do split "${K:$i:8}" six; done
```

Two things that must still pass:

```bash
split "${K:0:9}" alice ; split "${K:9}" bob      # different sessions: no bridge
```

And chunked file writing, which is completely ordinary:

```bash
run Bash '{"command":"printf \"# Setup\\n\" >> docs/setup.md"}'
```

---

## 6. The server — proxy and browser paths

Only needed for the extension or a shared checker.

```bash
pip install fastapi uvicorn httpx
python -m uvicorn gateway.app:app --port 8080
```

```bash
curl -s -X POST http://127.0.0.1:8080/v1/prompt/check \
  -H 'content-type: application/json' -H 'x-zerotrace-harness: claude-code' \
  -d '{"text":"refactor the retry loop"}'
```

```json
{"allow":true,"reason":"","classes":[],"findings":0,"latency_ms":1.19,"degraded":null}
```

Routes: `/v1/prompt/check` (side-car), `/v1/prompt/scan` (extension), `/v1/messages`,
`/v1/chat/completions`, `/v1/responses` (proxy), `/v1/coverage`, `/healthz`, `/readyz`.

**To point a real CLI at it**, use the wrappers — they refuse to launch if the checker is
unreachable rather than running unprotected:

```bash
./scripts/zt-claude.sh      # ANTHROPIC_BASE_URL
./scripts/zt-codex.sh       # OPENAI_BASE_URL
```

---

## 7. Things that are deliberately NOT caught

Test these to confirm the boundary is where the docs say, not to file bugs.

| Case | Why |
|---|---|
| ROT13 / reversed / ASCII-code encoded key | Nobody encodes a key that way by accident. N encodings at depth k costs N^k rescans and an adversary composes faster than anyone enumerates. Deliberate evasion is coverage monitoring's problem |
| Triple-nested base64 | Depth stops at 2, which covers `base64(json({...}))` |
| A key in a *tool schema* description | The tool author wrote it; the user cannot fix it by editing a prompt. Detected and reported, never enforced |
| Contents of a file read by the agent | `PreToolUse` fires before the tool runs |
| A streamed response body | Inbound leg unscanned — `X-ZeroTrace-Degraded: inbound_stream_unscanned` |
| `PERSON`, `ORG`, `GPE`, `ADDRESS` | Tier 3; S2/S3 not built. **Do not demo these** |

---

## 8. Evidence

```bash
python scripts/verify_ledger.py --dir evidence/ledger
```

```
  ok      acme                     2 records   head 979c627a35b2360c...
PASS -- every chain verifies from genesis.
```

**Prove it actually detects tampering** — this is the test worth doing by hand:

```bash
python - <<'PY'
import json, os
f = "evidence/ledger/acme.jsonl"
rows = [json.loads(l) for l in open(f, encoding="utf-8")]
rows[0]["payload"]["allowed"] = True          # flip a decision after the fact
open(f, "w", encoding="utf-8").write("\n".join(json.dumps(r) for r in rows) + "\n")
PY
python scripts/verify_ledger.py --dir evidence/ledger; echo "exit=$?"
```

```
  BROKEN  acme   ledger diverges at record 1: record_hash does not match its contents
FAIL -- at least one chain does not verify.
exit=1
```

Also confirm no secret reached it:

```bash
grep -c "sk-ant-api03" evidence/ledger/*.jsonl      # expect 0
```

---

## 9. Benchmarks

```bash
python bench/real_traffic.py --turns 250
```

```
  BLOCKED            0 / 250   (0.0%)
    self-referential 0   (this repo's own transcripts; its fixtures are real-shaped credentials)
    external         0 / 211   <- the number that means something
  latency (cold, no cache)   p50 1.2 ms   p95 11.6 ms   over 50ms 0
```

**Quote the external number.** The self-referential line exists because this repo's
transcripts are full of the fixtures from §2, and the tool detects them there exactly as
designed — counting those makes the metric drift as development continues.

```bash
python scripts/conformance.py
```

```
PASS claude-code-messages
PASS codex-responses
PASS openai-chat-compatible
```

Run this after touching anything in the proxy path. It checks the five ways we could break
someone's tool: round-trip fidelity, `cache_control` preserved at position, tool and system
content unmodified, SSE frames intact, and a planted credential still blocked.

---

## 10. Coverage

```bash
curl -s http://127.0.0.1:8080/v1/coverage
```

```json
{"scope":"gateway_observed_only","direct_egress_visible":false,
 "denominator_available":false,"total_requests":2, …}
```

**Read those three flags before quoting any coverage percentage.** They are honest about
the limit: this counts what came *through* the gateway, not what should have. Until the
DNS/flow-log join lands it answers "what did we see", not "what did we miss" — and only the
second question supports a coverage claim.

---

## 11. Live in Claude Code

```bash
python hooks/install.py        # merges into .claude/settings.json, idempotent
```

Then in a **new** session in this repo, paste a fake key into a prompt. It should refuse to
send. `python hooks/install.py --remove` undoes it.

Two things worth testing deliberately, because they are where the design choices show:

- **Autocomplete, the `/` menu, `@` file picker and tab completion are untouched.** The
  hook fires once, on submit, and never sees a keystroke. Confirm this rather than assume it.
- **Set `ZT_CHECKER` to an unreachable address.** You should be blocked with a message
  naming both the fix and `ZT_FAIL=open`. That is fail-closed. If it feels too aggressive
  in daily use, that is a real signal — the default is one environment variable.

---

## 12. Browser extension

Load `extension/` unpacked in Chrome (`chrome://extensions` → Developer mode → Load
unpacked). Set the checker URL in options. The server from §6 must be running — a browser
cannot import Python.

Paste a fake key into claude.ai and submit. It should be refused before it leaves the
browser.

**If the gateway is unreachable the extension must refuse to submit**, not submit
unscanned. Test that by stopping the server.

---

## What a failure means

| Symptom | Read this |
|---|---|
| Ordinary prompt blocked | A false positive — the most serious kind of bug here. Note the class and detector from the reason string |
| Real credential allowed | Check §7 first; it may be a documented boundary rather than a miss |
| Hook prints on a clean prompt | Regression — clean checks must be silent on both streams |
| Tool broke after routing through the proxy | Run `scripts/conformance.py`; if it passes, the harness needs its own fixture (PATCH-01 §2) |
| Ledger verify fails unexpectedly | Something rewrote the file. It is append-only by design |
