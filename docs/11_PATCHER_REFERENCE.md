# ZeroTrace — Harness Patcher Reference
**Doc ID:** PATCH-01 · **Audience:** Track A, and anyone adding a new IDE or AI harness

How ZeroTrace gets in front of an AI coding tool, what each mechanism costs, and what a new
harness has to pass before it counts as supported.

**The thing worth internalising first:** the checker is transport-agnostic. `POST
/v1/prompt/check` takes text and returns a verdict. So adding a harness is a *distribution*
problem, not a detection one — and the reusable artifact is a conformance suite, not a pile
of adapters.

---

## 1. The four mechanisms, as a ladder

Higher is not automatically better. Each rung sees more and therefore can break more.

### Rung 1 — Native hook (best where it exists)

The harness invites us in. We receive the prompt text or the tool arguments, return a
verdict, and the harness sends its own request untouched.

**We never see the payload**, so skills cannot be corrupted, `cache_control` cannot be
invalidated, and there is no dispatched body to verify because we dispatch nothing.

| Harness | Events | Adapter |
|---|---|---|
| Claude Code | `UserPromptSubmit`, `PreToolUse` | `hooks/zt_check.py`, `hooks/zt_pretool.py` |
| Codex CLI | same scripts, `--codex` | `apply_patch` mapped; deny returned on **exit 0**, which is what Codex consumes — Claude Code uses exit 2 |

Prefer this wherever it exists. The only gap is structural: `PreToolUse` fires *before* the
tool runs, so on a `Read` it sees the path and not the contents.

### Rung 2 — Base-URL redirect (broad, per-tool)

The harness respects an environment variable or a settings key naming the API base. We
become the base, hold the real key, and forward.

| Harness | Knob |
|---|---|
| Codex CLI | `OPENAI_BASE_URL` |
| Aider | `OPENAI_API_BASE` / `ANTHROPIC_API_BASE` |
| Continue, Cline | `apiBase` in config |
| Most SDK-based tools | `ANTHROPIC_BASE_URL` / `OPENAI_BASE_URL` |

This is where the proxy lives, and where the conformance suite earns its keep — see §2.

### Rung 3 — HTTPS proxy + CA (the genuine catch-all)

For a harness we have never met. Set `HTTPS_PROXY` plus `NODE_EXTRA_CA_CERTS`,
`REQUESTS_CA_BUNDLE` and `SSL_CERT_FILE`, then exec. Catches anything using an ordinary
HTTP stack without knowing what it is.

Use for: an unknown tool, or a first-pass coverage measurement before writing an adapter.

### Rung 4 — Browser extension (the only thing that reaches side chat)

claude.ai, ChatGPT web, an IDE's own chat pane: first-party endpoints, own TLS stack, CSP.
**No environment variable and no proxy reaches these.** The extension is not a convenience
here, it is the only mechanism.

Three contexts, because MV3 requires it:

```
MAIN world   inject.js     patches window.fetch, postMessage out
ISOLATED     bridge.js     relays to the service worker
service wkr  background.js the only context whose fetch escapes page CSP
```

**Patch `window.fetch`, never `.value`.** React tracks its own value state, so assigning to
a textarea does nothing and the original text submits — the control appears to work and
does nothing.

---

## 2. Adding a harness: the four steps

### Step 1 — Pick the highest rung it supports

If it has a hook, stop there. A rewriting proxy costs you exactly what the hook gives free.

### Step 2 — Write a conformance fixture

`gateway/conformance/<harness>.json`, modelled on the three that exist:
`claude-messages.json`, `codex-responses.json`, `openai-chat.json`.

A fixture is one realistic request captured from the live tool — not hand-written. Include
the parts most likely to break: `cache_control` markers, tool/function definitions, system
or developer instructions, a nested tool result.

### Step 3 — Run the suite

```bash
python scripts/conformance.py
```

Five properties, each of which is a way we could break someone's tool:

| Check | Why |
|---|---|
| Round-trip fidelity | No edits must return byte-identical bytes |
| `cache_control` preserved *at position* | Otherwise the prefix re-bills every turn — a ~10× cost increase with an invisible cause |
| Tool/function definitions unmodified | A rewritten schema breaks the tool and looks like a model bug |
| System / developer instructions unmodified | Skills ship through these |
| SSE frames relayed intact | Streamed responses must arrive whole |
| A planted credential in user content still blocks | Read-only origins are not a bypass |

**Add the fixture before the adapter.** A harness onboarded without one is an untested
integration, and the failure mode is breaking someone's tool — which costs more than the
credential it would have caught.

### Step 4 — Register coverage

Emit `x-zerotrace-harness: <name>` so `CoverageMonitor` counts it. Without this the tool is
invisible to the coverage report and you cannot answer "is it actually routed?"

---

## 3. What the proxy will not do to a payload

These are enforced, not conventions, and they are why rung 2 is survivable.

- **`tools` / `functions` / `tool_choice`** → origin `tool_definition`. Scanned, never
  rewritten, and **never enforces** — a doc-example AWS key in a skill's description is the
  tool author talking, and the user cannot fix it by editing their prompt.
- **`system` / `instructions`** → origin `system`. Scanned, never rewritten. Only the
  CREDENTIAL family may enforce, because a live key in `CLAUDE.md` or `AGENTS.md` is a real
  leak the user *can* remove.
- **Protocol scaffolding** (`model`, `role`, `type`, `cache_control`, JSON-Schema keywords)
  → origin `metadata`. Not scanned at all.
- **Editing is byte-splicing**, never re-serialisation. Nothing untouched is rewritten.
- **Headers are a denylist.** Hop-by-hop and anything named by `Connection` are stripped;
  everything else forwards. An allowlist silently dropped headers from harnesses we had not
  enumerated, and the failure looked like the harness was broken.

**The concept generalises; the field names do not.** `tools` vs `functions` vs whatever the
next harness calls it is exactly what a fixture pins down.

---

## 4. What Track A needs from this

Track A never talks to a harness. The relevant surface is one call and three facts.

**The call** — `POST /decide`, per SKEL-01 §1.2:

```
{ actor, findings[], risk, leg, destination, origins }  ->  Decision
```

**Fact 1 — `origins` decides whether a finding may enforce at all.** Only the span tree
knows where a finding sat, so Track B sends it. `may_enforce(origin, family)` in
`contracts/types.py` is the rule:

| Origin | Enforces |
|---|---|
| `user`, `assistant`, `tool_call`, `tool_result` | everything |
| `system`, `instructions` | CREDENTIAL only |
| `tool_definition` | **nothing** |
| `metadata` | nothing (never scanned) |

**Fact 2 — `channel` changes the available actions.** On `cli` and `mcp`, `tokenize` is not
available and blocks instead. Claude Code writes model output to disk, so a tokenised value
becomes a literal `⟨PERSON_a41⟩` in a source file, and redaction is one-way. Refusing is
strictly better than silently corrupting a repository.

**Fact 3 — write rules against `family`, not `class`.** Track B adds classes; families
absorb them. VOCAB-01 §1 Rule 2.

---

## 5. Honest limits

- **Any rung is one unset variable from being bypassed.** That is not fixable by better
  interception. It is why `gateway/coverage.py` exists, and why the DNS/flow-log join
  (TODO-01 §2.4) matters — today coverage answers "what did we see", not "what did we
  miss".
- **Rung 2 sees the whole payload**, so it *can* corrupt skills and break the cache. The
  guards in §3 are what make it safe, and they are only proven for harnesses with a
  fixture.
- **Auth shapes are not yet covered by the suite.** Subscription OAuth, `Bearer` vs
  `x-api-key`, per-harness beta headers. This will surface as "the proxy broke my tool" on
  a harness nobody tested. TODO-01 §2.4.
- **The prompt-cache guarantee is verified for markers, not for a real hit.**
  `scripts/verify_prompt_cache.py` is opt-in and billable because that is the only way to
  prove it. Run it once per new harness.
