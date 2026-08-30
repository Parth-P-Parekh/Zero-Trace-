# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js 15 (App Router) + TypeScript, consuming the existing ZeroTrace Design System at `app/ZeroTrace Design System/` as the component and token layer. **No Tailwind, no shadcn/ui** — the design system ships its own CSS custom-property token layer and `.jsx` components, and a utility framework would fight its ramp/spacing rules. Confirmed by the user; this supersedes the Tailwind/shadcn line in CODE-01 §1, which must be amended.

The design system folder is **read-only and exclusive**. Everything built lives outside it, under `app/console/` and `app/marketing/`.

## Users

Confirmed from PROD-01 §2, in priority order:

- **CISO / head of security** — primary buyer. Job: *"Prove that no team can send customer data to a model without me knowing."* Needs enforcement that does not depend on app teams cooperating, a coverage number they can defend, and evidence an auditor accepts.
- **Platform / SRE** — primary operator. Job: *"Give every team a safe default without reviewing every prompt, and without becoming the bottleneck."* Deploys once into the egress path; needs org policy with per-BU overrides and predictable behaviour under load and failure.
- **AI application engineer** — not a buyer, and the product's promise to them is that they do nothing. No SDK, no key, no config. Latency budget intact, model output still coherent.
- **Compliance / DPO** — job: *"Prove to an auditor what left the building and what didn't."* Tamper-evident ledger, exportable evidence, no raw sensitive data in it.
- **Agent-platform operator** — needs coverage of tool results and inter-agent hops, not just the user turn.

The console is used by the first two daily, the fourth periodically, and the third almost never.

## Product Purpose

ZeroTrace is an enterprise egress firewall for AI traffic. It deploys inside the customer's own perimeter, sits in the path applications already take to reach a model, and redacts secrets and personal data out of outbound *and* inbound LLM and agent payloads — one way, nothing restored — while rewriting its own detection rules as it learns.

Success: a security organisation can state, with evidence, what left the building and what did not, without any application team having integrated anything.

## Positioning

Three mechanisms a neighbouring product could not truthfully claim, from PROD-01 §1.3:

- **N1 — self-hardening detection.** The LLM adjudicator is a teacher, not the runtime. When it catches what deterministic rules missed, a synthesizer writes a new deterministic detector, a validator proves it against the corpus, and it is promoted to the hot path. Escalation rate, latency and cost all fall as traffic grows.
- **N2 — compositional re-identification scoring.** Risk is computed over the *set* of quasi-identifiers present, not per entity. Catches records with no flaggable entity that still identify a person.
- **N3 — utility-preserving redaction that is one-way.** Format-preserving, referentially stable tokens derived by keyed HMAC. The same original always yields the same token across hops, sessions and restarts. **Nothing is ever reversed** — there is no plaintext stored and no restoration path.

And the deployment posture, which is the enterprise claim: enforcement is administrative, not voluntary. Provider domains are denied at the network boundary; a coverage monitor names any workload that tried another route.

## Operating Context

- Deployed by platform or security into the egress path — mesh sidecar (Envoy `ext_proc`) or transparent gateway under the enterprise's own CA. An explicit endpoint exists but is not the deployment model.
- Runs entirely inside the customer's VPC. Payloads never reach the vendor; only a signed usage counter does.
- Actors resolve from the enterprise IdP: OIDC/SAML for people, SCIM group sync for clearance, SPIFFE workload identity for services. **No developer-held keys exist in the product.**
- Console roles are `security` (all, plus approvals), `platform` (all read, policy write, no approvals), `bu_owner` (own BU only). Enforced server-side.
- Policy is org-scoped; business units inherit and may narrow an action but never widen it.

## Capabilities and Constraints

Console surfaces (PROD-01 C17, confirmed in scope with the user):

| Surface | Job |
|---|---|
| Login | SSO entry |
| Traffic feed | Live requests: actor, classes, action, latency, risk |
| Payload inspector | One request's decision diff — spans, classes, the rule that fired, both legs |
| Detectors | Registry with provenance, precision/recall/runtime, promote/rollback |
| Policy | YAML editor, version history, exceptions and approvers |
| Coverage | Coverage %, direct-egress exception list, per workload |
| Licence | Tier, usage by leg, signed counter, payment link |

Marketing page (zerotrace.dev) also confirmed in scope — a separate visitor mode from the console.

**Hard constraints that shape every screen:**

- **The console must never display a sensitive value.** Findings carry span paths, classes and offsets only. The decision diff renders `⟨PERSON_a41⟩` against `[PERSON, 12 chars]` — enough to understand the decision, not enough to leak it. This is a product invariant (PROD-01 §7), not a preference.
- **Tokens are never reversible.** No UI affordance may imply "reveal original" or "unmask". There is no such operation.
- **The console is closed by default.** It is reachable only through sign-in, and no surface links to it directly. While the IdP integration is stubbed, a single **break-glass local admin credential** opens it — a session cookie signed server-side, rate-limited, with no shipped default in production. This is a stand-in for C22, labelled as one in the interface, and it is the first thing deleted when OIDC and SCIM are real. It does not change the position that the product holds no accounts of its own.
- **Redaction is one-way and covers both legs** — outbound to the model, inbound from it. Findings carry a `leg`.
- **Latency is a first-class number**: p50 ≤ 30ms, p95 ≤ 65ms across both legs, per-stage budgets S0–S6.
- **Degradation is stated, never hidden.** A stage that fails open sets `X-ZeroTrace-Degraded` and the UI must show it.
- Domain vocabulary is fixed: a **payload** goes out, a **finding** is a detected span, a **redaction** is the replacement, a **detector** is a rule, a **leg** is outbound or inbound, the **ledger** is the tamper-evident record, **coverage** is the share of AI egress that traversed ZeroTrace.

**Terminology conflict to resolve in copy:** the design system readme uses "sweep" and "patch" from the earlier product framing. PROD-01 uses "request/finding" and "ledger". PROD-01 wins; "sweep" and "patch" are not used.

## Brand Commitments

Binding, from `app/ZeroTrace Design System/` (the user made this system authoritative):

- **The opacity ramp is the identity** — six fixed stops `1.00 · .72 · .52 · .36 · .22 · .11`. Text hierarchy, borders, dividers, disabled states, chart fills and the redaction mask all draw from it. A value not on the ramp is not in the design.
- **No accent colour, by design.** Ink `#111111` (never `#000`), paper `#E8E8E6` (never `#FFF`), inverse `#F2F2F0`, dark surface `#0B0B0B`, muted `#6B6B68` for descriptor text only.
- **Four functional signal inks are a documented UI-only exception** — clean/redacted/blocked/info, desaturated, never larger than a 6–10px dot, a 1px rule, or a small pill's text+dot. Never in marketing chrome, never near the wordmark.
- **Inter 400 is the whole voice.** 500 for UI labels, 600 only for metric numerals. Never heavier. IBM Plex Mono for payloads, keys, IDs, timestamps — if it's mono, it's machine data.
- **No imagery.** No photography, illustration, 3D, gradients as decoration, patterns, noise, or mesh.
- **No emoji, anywhere** — not in UI, marketing, docs, or commit messages.
- **Voice:** flat, technical, declarative. Present tense for behaviour, past for logged events. Second person for the reader, third person for the product. Never first person. Sentence case everywhere; all-caps only for the wordmark and 12px `+0.12em` eyebrows. Numbers always concrete and unit-tagged (`240 ms`, `(3) values redacted`).
- **Forbidden:** fear-selling, hype adjectives, "this not that" antithesis, rhetorical questions, exclamation marks, metadiscourse, the phrase "AI-powered".
- **Motion:** nothing bounces, overshoots, or springs. Fades and 4–8px translations only. One signature — `--d-drain 900ms`, the left-to-right sweep.

## Evidence on Hand

- `docs/01_PRODUCT_ARCHITECTURE.md` (PROD-01) — architecture, components C1–C23, API contract, policy language, pricing.
- `docs/CODE.md` (CODE-01) — implementation plan, full API shapes, corpus schema, stage budgets.
- `docs/00_SSOT_RULES_AND_SCORING.md` — binding rules and evidence IDs.
- `app/ZeroTrace Design System/` — tokens, 23 components, two UI kits (console and marketing), guidelines.

**Absences that must not be fabricated:** no backend exists — CODE-01 is a plan, not code. No customers, no testimonials, no benchmark results, no press, no real traffic. The seven logo SVGs named in the logo sheet were never supplied; the `Wordmark` component renders live type as a flagged stand-in. All pricing figures in PROD-01 §12 are marked assumed. The frontend runs on fixtures shaped to the PROD-01 §8 / CODE-01 §15 contract, behind one typed client, so a real backend swaps in without touching the views.

## Product Principles

1. **Show the mechanism, not the reassurance.** The product's claim is that nothing dramatic happened. Every screen states what occurred, in what order, to what — and never dramatises it.
2. **The console cannot leak what the proxy caught.** Any screen that would need a sensitive value to be useful is designed wrong. Span paths, classes and offsets are the vocabulary.
3. **Coverage before detection quality.** A security buyer asks "is this all the traffic?" before "how good is the matching?" The coverage number and its exception list outrank the detection metrics in hierarchy.
4. **Evidence is the artifact.** Provenance on a synthesized detector, the approver on an exception, the hash chain on the ledger — these are the things being bought, so they get the strongest treatment on screen.
5. **Honest degradation.** A stubbed capability, a failed-open stage, an assumed number — each is labelled in the interface. Overclaiming loses a security buyer permanently.

## Accessibility & Inclusion

- The identity is achromatic and status is carried by shape and text as well as the four signal inks — never colour alone. Every status pill pairs a dot with a word.
- Focus is a `0 0 0 3px rgba(17,17,17,0.14)` ring, never removed, never colour-only.
- `prefers-reduced-motion` zeroes every duration, including the `--d-drain` signature.
- Dense operator UI: 40px table rows, 36px fields, 13–16px body. Keyboard navigation across the traffic feed and detector registry is a requirement, not an enhancement.
