# Design

<!-- impeccable:design-schema 1 -->

## Status: inherited, not invented

`app/ZeroTrace Design System/` is the visual authority. It arrived complete — tokens, 25 components, two UI kits, and a readme that reads like a brand manual because it was derived from a real logo sheet. This file records that world and the decisions made to **extend** it onto surfaces it did not already cover. Nothing here replaces it.

Where this file and the design system disagree, the design system wins and this file is the bug.

## The one gesture

**Ink draining left to right.** `ZERO` at full density, `TRACE` dissolving. The six-stop opacity ramp — `1.00 · .72 · .52 · .36 · .22 · .11` — is the identity, and it is the *only* source of tonal value in the system. Text hierarchy, borders, dividers, disabled states, chart fills, hover feedback and the redaction mask all resolve to a ramp stop. A value not on the ramp is not in the design.

This has a consequence worth stating plainly, because it is the thing most likely to be violated under time pressure: **there is no accent colour.** Not a muted one, not a "brand blue used sparingly". The absence is the position.

## Palette

| Role | Value |
|---|---|
| Ink | `#111111` — never `#000` |
| Paper | `#E8E8E6` — never `#FFF` for the page |
| Inverse ink | `#F2F2F0` |
| Dark surface | `#0B0B0B`, card `#161615` |
| Muted | `#6B6B68` — descriptor text only |

Four functional signal inks (`--signal-clean` `#3F6B3A`, `--signal-redacted` `#8A6A1F`, `--signal-blocked` `#A8342A`, `--signal-info` `#3A5A6B`) exist for one reason: an operator has to separate clean / redacted / blocked pre-attentively. Constraints, enforced: never larger than a 6–10px dot, a 1px rule, or a small pill's text-plus-dot; never on or behind the wordmark; never in marketing. Every status pairs its dot with a **word**, so the signal never carries meaning alone.

## Type

Inter 400 is the whole voice. 500 for UI labels, 600 for metric numerals only — nothing heavier exists. IBM Plex Mono carries payloads, keys, span paths, hashes, IDs and timestamps: **if it is mono, it is machine data.** Mono is never a costume for "technical".

Tracking is the brand tell: `+0.04em` wordmark, `+0.12em` on 12px caps eyebrows, `-0.022em` at display sizes, `0` at body. Display type sets large and light — 42–72px at weight 400 — so headlines read as drawn ink, not as bold statements.

**Eyebrows are kept**, against the general craft-floor ban, because this brief specifies them: they are functional micro-labels on metrics, column heads and section markers, not decorative kickers stacked above headings. The banned pattern — a caps label floating above a display headline purely for texture — appears nowhere, including in marketing.

## Extension decisions

The design system's console kit covers four screens under the product's earlier framing (sweep log, inspector, policy rules, integration). PROD-01 now names seven. These are the decisions made to cover the gap without inventing a second identity.

**1. The shell is inherited verbatim.** Dark 232px rail, sticky; wordmark at 17px inverse; rail items with counts; an environments group; a live status footer with a pulsing `StatusDot`. Main column with a 56px sticky topbar at 82% paper plus `--blur-panel` and an inset bottom hairline. Content at 24px padding, 1200px max. Every new route drops into this shell unchanged.

**2. Rail groups, because seven items is past the point where a flat list scans.** Three labelled groups following the existing "Environments" precedent: *Traffic* (Traffic, Findings), *Control* (Detectors, Policy), *Assurance* (Coverage, Ledger, Licence). The group label uses the same 12px caps treatment the kit already uses.

**3. One dark card per screen, spent on the thing that matters most on that screen.** This is the kit's own rule and it is the primary compositional tool for hierarchy in a world with no accent colour:

| Route | The dark card |
|---|---|
| Traffic | Added latency, p95, both legs |
| Inspector | The payload itself — `PayloadView`, the focal object |
| Detectors | The falling escalation-rate curve — N1's proof |
| Policy | The active policy version and its YAML |
| Coverage | The coverage percentage — the number a CISO asks for first |
| Licence | Usage against the licensed volume |

**4. The escalation curve is drawn, not charted.** No chart library. A single inline SVG polyline over a ramp-derived horizontal opacity gradient — which is the readme's one sanctioned functional use of a gradient, and which happens to *be* the product's argument: the line falls as the system teaches itself. Fills come from the ramp resolved against dark.

**5. Redaction is shown with the real component.** `RedactionMask` renders every masked value in the inspector, at the true character length of the original. The console never renders a sensitive value — the mask is not a visual metaphor here, it is the actual product invariant made visible.

**6. Two states no kit screen had, both mandated by PROD-01:**
- **Degraded** — a stage that failed open. A `Badge` with `status="info"` in the topbar plus a line naming the stage, on every affected request. Never hidden, never a silent success.
- **Stubbed** — SSO, SCIM, HA, air-gap and cloud flow-log connectors are not built. Any surface touching them carries a plain hairline note saying so. Overclaiming loses a security buyer permanently, and SSOT §2.2 makes it a submission risk.

**7. Marketing is Persuade, and gets exactly one bold move.** The hero shows the product's actual behaviour: a prompt carrying a credential reaches the boundary, ZeroTrace detects the breach, and **the request stops there** — the model never receives it, and the caller gets an error naming what was found. The gesture is the identity's own, inverted: the wordmark's drain completes, and here the scan sweeps left to right and arrives at a boundary the payload does not cross. It fires once; this is an event, not an animation. Example data is rendered the way the product renders it — solid ink blocks at the original character length, never plaintext. No big-number hero, no feature-icon grid, no gradient. The headline uses the reference chrome's treatment the readme names — first clause at full ink, continuation at ramp `.36`, fading like the mark.

**8. The console is closed by default, and the login page says why.** The console is reachable only through sign-in — there is no direct link to it anywhere on the site, including the top nav. While SSO is stubbed, one local admin credential opens it, and the sign-in page states that plainly rather than implying the product has accounts of its own. The dark panel carries the position (*"The console is closed by default"*); the paper side carries the form. Signal colour appears exactly once, as the 6px dot beside a failed attempt.

## Motion

Nothing bounces, overshoots or springs. Fades and 4–8px translations only; `--ease-out` for entrances, `--ease-in-out` for state, `linear` for streams. The one authored moment is `--d-drain` at 900ms: the wordmark on first paint, the redaction mask filling in, the scanline crossing a payload. It fires once per surface, not on every section. `prefers-reduced-motion` zeroes it, and the reduced path is a plain fade, never a jump.

## Browser surfaces

The parts not drawn still carry the design, so they are themed from the ramp rather than left to the browser: selection is ink at `.11` with full-ink text; the caret is ink; scrollbars are `.22` thumbs on transparent tracks; focus is the token `--sh-focus` ring at 3px, never removed; mono numerals in tables use `font-variant-numeric: tabular-nums`, without which every latency column is visually ragged.

## What would make this wrong

- A colour appearing anywhere as decoration.
- A revealed original value in the console — there is no such operation, and a UI affordance implying one is a product lie.
- A second bold move in marketing competing with the drain.
- A card nested inside a card.
- An emoji, anywhere.
