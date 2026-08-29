# ZeroTrace Design System

**ZeroTrace — Autonomous AI Payload & PII Leak Sweeper.** A proxy agent that sits in front of outgoing LLM API calls, inspects payloads in-stream, detects PII, credentials and other confidential data, and auto-redacts before dispatch. Every intervention is logged as a patch.

The product is not scoped to one data class or one model vendor. It is a security guardrail for any product or SaaS company routing data through a frontier LLM — the firewall between application code and the model.

The scenario the brand is built around: *a developer sends a customer support log to a frontier model. ZeroTrace catches a social security number and a private API key in the stream, redacts them on the fly, and logs the patch.*

---

## Sources given

| Source | What it is | Status |
|---|---|---|
| `uploads/zerotrace-logo-sheet.pdf` | **ZeroTrace · wordmark v1.0 · logo sheet**, 3 pages. Sections 01 Type, 02 Opacity ramp, 03 Clear space, 04 Size ladder, 05 Surface, 06 Misuse, 07 Files. | Read in full. This is the ground truth for the identity. |
| `uploads/download.jpg` | Reference chrome — a marketing header ("MONELIO"): white bar, small pill nav, black full-bleed hero card with heavy rounding, floating white segmented pill control bottom-right. Unrelated brand; supplied as a visual reference. | Read as structural/chrome reference only. |
| `uploads/download (1).jpg` | Reference chrome — a rounded white panel containing a paired light card / near-black card, pill tag row, pill segmented control, pill buttons, small filled status dot. | Read as structural/chrome reference only. |
| Product brief | Title, description, why, scenario (above). Pasted in chat. | Used for copy, product surfaces, console content. |

**No codebase, Figma file, or slide deck was provided.** No component inventory exists in any source, so the component set here is authored from scratch against the logo sheet and reference chrome (see *Components* below). No product screenshots of ZeroTrace itself were provided — the UI kits are original interfaces built from the brief, not recreations.

### Missing files (please supply)

The logo sheet's section 07 lists seven SVGs that were **not** included in the upload:

```
zerotrace-primary.svg   zerotrace-primary-inverse.svg   zerotrace-mono.svg
zerotrace-lockup.svg    zerotrace-appicon.svg           zerotrace-monogram.svg
zerotrace-favicon.svg
```

The sheet is explicit: *"Never retype the mark: always use the supplied outlined SVGs."* Because those files are absent, **`assets/` contains no logo binary.** Wherever the mark is needed, this system renders the brand name as live type via the `Wordmark` component — Inter 400, all caps, `+0.04em`, per-letter opacity ramp, matching the sheet's geometry spec (Inter Regular at 100px, cap height 72.75, advance 626.87). **This is a stand-in and violates the sheet's own rule.** Drop the real SVGs into `assets/logo/` and swap `Wordmark` to render them.

No font binaries were supplied either. Inter (the specified face, SIL OFL) is loaded from Google Fonts in `tokens/fonts.css` — the correct family, not a substitute. See *Substitutions & flags*.

---

## Content fundamentals

The voice follows the logo sheet's logic: **the mechanism is the message.** State what happened, in what order, to what. Nothing is dramatised, because the product's whole claim is that nothing dramatic happened — the leak was caught before it left.

**Register.** Flat, technical, declarative. Present tense for behaviour, past tense for logged events. Sentences are short and load-bearing; no sentence exists to set up another one.

> ZeroTrace inspects every outbound payload before dispatch.
> Two values were redacted. The request completed in 240 ms.

**Person.** Second person for the reader's actions and the reader's system (*your payloads*, *your keys never leave*). Third person for the product's actions (*ZeroTrace redacts*, *the sweeper flagged*). Never first person — no *we*, no *our team*, no *we believe*. The product speaks about itself in the third person because it is an agent, not a company talking.

**Casing.** Sentence case everywhere in UI and prose. All-caps is reserved for two things: the wordmark, and eyebrow/label micro-type at 12px with `+0.12em` tracking (`SWEEP LOG`, `POLICY`, `LAST 24H`). Never all-caps for buttons, headings or emphasis. Title Case is never used.

**Numbers.** Always concrete and always unit-tagged. `240 ms`, `1.2M payloads`, `4 rules active`, `(27) findings`. Counts in parentheses when they qualify a noun, following the reference chrome: `(27) spikes found` → `(3) values redacted`. Never round up for effect; never write *thousands of* or *up to*.

**Naming the domain.** Use the product's own vocabulary consistently and never as a synonym chain: a **payload** is what goes out; a **finding** is a detected value; a **redaction** is the replacement; a **patch** is the log record; a **rule** is a policy entry; a **sweep** is one inspection pass. Say *redact*, not *scrub*, *mask*, *sanitise*, or *anonymise*.

**Forbidden moves.** No fear-selling (*don't get breached*, *nightmare*, *disaster*). No hype adjectives (*revolutionary*, *seamless*, *powerful*, *cutting-edge*). No "this, not that" antithesis. No rhetorical questions. No exclamation marks. No metadiscourse (*here's why this matters*). Never say *AI-powered* — the product's autonomy is described by what it does, not by the label.

**Emoji: never.** Not in UI, not in marketing, not in docs, not in commit messages. The identity is achromatic and silent; an emoji is both a colour and a voice. Status is carried by a 6px dot, a mono glyph, or the word itself.

**Redaction in copy.** When example data appears, redact it the way the product does — with a solid ink block of the original character length, not with asterisks or `[REDACTED]` when shown visually. In plain text, the token form is `⟨redacted:ssn⟩`, lowercase, angle-bracketed, type-tagged.

**Microcopy examples.**

| Situation | Write |
|---|---|
| Empty sweep log | `No payloads inspected yet. Point your SDK base URL at the proxy to begin.` |
| Clean result | `Clean. Nothing redacted.` |
| Redacted result | `(2) values redacted — us_ssn, api_key. Dispatched.` |
| Blocked result | `Blocked. Rule "no raw card numbers" has no redaction strategy.` |
| Destructive confirm | `Delete rule "us_ssn"? Payloads matching it will dispatch unredacted.` |
| Error | `Upstream returned 503. Payload was not dispatched and was not stored.` |
| Marketing hero | `Your prompts leave with nothing in them.` |
| Marketing sub | `ZeroTrace inspects every outbound LLM call, redacts what shouldn't be in it, and logs the patch. Two lines of config.` |
| CTA | `Start sweeping` / `Read the docs` — verb-first, sentence case, never *Get started free!* |

---

## Visual foundations

### The one gesture

The logo sheet is unusually strict, and everything visual descends from a single idea: **ink draining left to right.** `ZERO` at full density, `TRACE` dissolving to nothing. Section 02 calls the ramp *"the identity"* — six fixed values, opacity not colour, resolving against whatever surface it sits on: `1.00 · .72 · .52 · .36 · .22 · .11`.

That ramp is the entire system. Text hierarchy, borders, dividers, disabled states, chart fills, hover feedback and the redaction mask are all drawn from those six stops. If a value isn't on the ramp, it isn't in the design.

### Colour

| Role | Value | Rule |
|---|---|---|
| Ink | `#111111` | never `#000` for ink |
| Paper | `#E8E8E6` | never `#FFF` for the page |
| Inverse ink | `#F2F2F0` | on dark |
| Dark surface | `#0B0B0B` | panels, hero cards, code |
| Muted | `#6B6B68` | **descriptor text only** |
| Accent | none — by design | — |

Approved backgrounds behind the mark: paper, white, dark surface, black. Nothing else. No brand colour, tint, gradient or image.

**Functional signal colours are a documented exception, UI only.** A security console has to distinguish clean / redacted / blocked pre-attentively, so `tokens/colors.css` defines four desaturated process inks (`--signal-clean #3F6B3A`, `--signal-redacted #8A6A1F`, `--signal-blocked #A8342A`, `--signal-info #3A5A6B`) plus soft companions. Constraints: never on or behind the wordmark; never as a fill larger than a 6–10px dot, a 1px rule, or a small pill's text+dot; never in marketing chrome. The soft variants back status pills at low saturation. Removing them entirely would still leave a working system — that is the test they must keep passing.

### Type

Inter 400 is the whole voice. Weight 500 for UI labels and 600 only for metric numerals; nothing heavier ever. Never Helvetica, Arial, Roboto or Montserrat (the sheet names these explicitly). Approved alternates if Inter is unavailable: ABC Diatype, Söhne Buch, Neue Haas Grotesk Display 55.

Tracking is a brand tell: `+0.04em` on the wordmark, `+0.12em` on 12px caps eyebrows, `-0.022em` at display sizes, `0` at body. Display type is set large and light — 42–72px at weight 400, line-height 1.06–1.22 — so headlines read as drawn ink rather than as bold statements. The reference chrome's headline treatment is used verbatim in marketing: **the first clause at full density, the continuation at ramp `.36`**, one line fading like the mark.

IBM Plex Mono carries payloads, keys, rule patterns, IDs and timestamps. Mono is never decorative — if it's mono, it's machine data.

### Space and layout

4px base, with 6px and 10px kept in the scale because the console runs dense. Page max 1200px, prose max 60ch, sidebar rail 232px, top bar 56px, table row 40px, field 36px. Section rhythm in marketing is 96/128px vertical; console panels are 24px padded with 12px internal gaps.

Fixed elements: the console top bar and rail are fixed; marketing nav is sticky and gains a hairline bottom border plus backdrop blur only after scroll. Nothing else is fixed. The wordmark keeps `0.6 × cap height` clear space in every context — no rules, type, image edges or UI chrome enter it, and it is never given a container, badge or plate.

### Backgrounds

Flat paper or flat dark. **No gradients as decoration, no photography, no illustration, no patterns, no noise/grain, no mesh.** The two gradients in the system are functional: protection fades that let content pass under a fixed bar (`--fade-paper-down`, `--fade-dark-up`), and the ramp itself when expressed as a horizontal opacity gradient over a sweep visualisation. Full-bleed means full-bleed flat colour — a near-black card breaking the paper grid, as in the reference chrome.

### Cards and borders

Two card species, both from the reference chrome:

- **Paper card** — `--surface-card` white on paper, `1px` `--border-hairline`, radius 12px, shadow `--sh-2`. Content cards, table containers, rule rows.
- **Dark card** — `#0B0B0B`/`#161615`, no border, radius 12–16px, shadow `--sh-3`. Used for the one thing on a screen that matters most: the live payload, the hero, the blocked event.

Outer containers that group cards use radius 16–20px and `--sh-4`. Radii: 4px on inputs and small pills, 8px on buttons, 12px on cards, 16–20px on shells, `999px` on pills and toggles. The app icon is 512×512 with a 112px radius (0.219 ratio) per the sheet. Nothing else is rounded — never a rounded corner with a coloured left border.

Borders are always hairline and always ramp-derived: `.11` for dividers, `.22` for field outlines, `.36` for emphasis. There are no 2px borders except focus.

### Shadows

Soft, wide, achromatic — ink at 4–10% spread over 10–64px, always straight down. `--sh-1` through `--sh-4`. No coloured shadows, no glows, no inner shadows except the hairline inset used on pressed toggles. Shadow never substitutes for a border; cards on paper carry both.

### Transparency and blur

Transparency is the ramp, so it is used constantly for *ink on surface* and almost never for *surface on surface*. Two exceptions: the sticky marketing nav (`backdrop-filter: saturate(120%) blur(14px)` over 72% paper) and modal scrims (ink at `.36`). Panels are opaque. Glass is not a look here.

### Motion

Nothing bounces, nothing overshoots, nothing springs. Ink either is there or it isn't. `--ease-out cubic-bezier(0.22,1,0.36,1)` for entrances, `--ease-in-out` for state, `linear` for progress and streams. Durations: 80ms instant, 140ms hover, 200ms base, 320ms slow, and one signature — `--d-drain 900ms`, the left-to-right sweep used for the wordmark drain on first paint, the redaction mask filling in, and the scanline crossing a payload. Fades and 4–8px translations only; never scale-in from 0.9, never rotation. `prefers-reduced-motion` zeroes every duration.

### Interaction states

- **Hover** on ink surfaces: text goes from ramp `.72` → `1.00`; ghost buttons take a `rgba(17,17,17,0.05)` wash; solid ink buttons lighten to `#2A2A28`; card hover lifts `--sh-2` → `--sh-3` with no translation. Links darken their underline from `.36` to full ink. Never a colour change.
- **Press**: no shrink, no transform. Solid buttons darken to `#0B0B0B`; ghost wash deepens to `0.09`; toggles gain `--sh-inset-hair`. 80ms.
- **Focus**: `box-shadow: 0 0 0 3px rgba(17,17,17,0.14)` ring, no outline, no colour. On dark, `rgba(242,242,240,0.18)`.
- **Disabled**: opacity `0.36` — ramp stop, not grey paint. Cursor `not-allowed`. No hatch, no lighter fill.
- **Selected**: ink fill with inverse text on pill segments (reference chrome), or a 1px ink left edge on rail items — never a coloured highlight.

### Imagery

There is none, and that is the position: no photography, no 3D renders, no stock, no illustration. If imagery ever becomes necessary, the sheet's constraint applies — the mark goes mono over it — and the tonality would be cool-neutral, high-contrast, desaturated to near-monochrome with fine grain. Product visuals are the interface itself: real console panels, real payload text, real mono data.

---

## Iconography

**No icon set was supplied** — the logo sheet is wordmark-only and explicitly rejects a symbol (*"No symbol, no icon, no metaphor bolted on"*). There is no icon font, sprite sheet, or SVG set in any source.

**Substitution, flagged:** this system uses **Lucide** (`lucide@0.454.0`, ISC), linked from CDN in the UI kits and card HTML, because its 1.5px-stroke achromatic outline style is the closest available match to a monoline achromatic identity with no fill and no colour. It is a substitute, not the brand's set.

Rules for using it:

- **Stroke 1.5px, size 16px** in console UI (18px for rail items, 14px inside pills). Never filled, never duotone, never two-tone.
- **`currentColor` always** — icons inherit the ramp stop of the text they sit with, so a quiet label's icon is quiet too. Icons are never coloured independently, including with signal colours; a signal is a dot, not a coloured icon.
- **Icons never travel alone in marketing.** In the console they may stand alone in a 28px icon button with a tooltip. In marketing there are no icons at all — no feature-grid icon cards.
- **Working set:** `shield`, `scan-line`, `eye-off`, `key-round`, `file-text`, `activity`, `list-filter`, `settings-2`, `chevron-right`, `chevron-down`, `arrow-right`, `arrow-up-right`, `check`, `x`, `copy`, `search`, `plus`, `more-horizontal`, `clock`, `terminal`, `book-open`, `external-link`.
- **No emoji, ever.** See *Content fundamentals*.
- **Unicode as glyph** is permitted in mono contexts only, where it is data rather than decoration: `·` as a separator in eyebrow type, `→` inside inline links following the reference chrome's `Restart investigation →`, `⟨ ⟩` for redaction tokens, `▍` as the redaction block in text-only output.
- The redaction mask itself is **not an icon** — it is a filled rect at ramp `.11` with a `.36` 1px rule, sized to the character run it replaces. Never a lock, never an asterisk, never a blur.

---

## Substitutions & flags

1. **Logo SVGs missing** — all seven files from logo sheet §07. The `Wordmark` component renders live type as a stand-in, against the sheet's own instruction. **Please supply the SVGs.**
2. **Font binaries missing** — Inter is the *correct* specified family but is loaded from Google Fonts rather than self-hosted woff2. Supply the licensed binaries for `assets/fonts/` if self-hosting matters.
3. **IBM Plex Mono is an addition.** The sheet specifies no mono face; the product cannot be designed without one. Chosen for its grotesque skeleton alongside Inter. Swap freely.
4. **Lucide icons are a substitution.** See *Iconography*.
5. **Signal colours are an addition.** Documented above with the constraints that keep them out of the identity.
6. **Reference chrome, not brand chrome.** Pill nav, segmented pills, paired light/dark cards and the soft outer shell come from `download.jpg` / `download (1).jpg`, which are other brands' surfaces supplied as references. They are treated as structural conventions and re-rendered in ZeroTrace's achromatic palette.
7. **UI kits are original, not recreations.** No ZeroTrace product source existed. Screens are built from the brief; treat them as proposals.

### Intentional additions

| Addition | Reason |
|---|---|
| `Wordmark` | The identity needs a component; the SVGs are missing. |
| `RedactionMask` | The product's core visual act. Nothing in a generic set expresses it. |
| `PayloadView` | Streaming payload inspection is the product's primary surface. |
| `StatusDot` | Carries state where colour-as-fill is forbidden. |
| `Icon` | Wrapper enforcing size/stroke/`currentColor` over the substituted Lucide set. |
| `Metric`, `Table`, `Toast`, `Tooltip`, `Dialog`, `Tabs` etc. | No source inventory existed, so a standard set is authored per the from-scratch path. |

---

## Index

**Root**

- `styles.css` — the single entry point consumers link. `@import` lines only.
- `readme.md` — this file.
- `SKILL.md` — Agent Skills front matter for use outside this project.
- `thumbnail.html` — homepage tile.

**`tokens/`** — `fonts.css`, `colors.css`, `typography.css`, `spacing.css`, `borders.css`, `elevation.css`, `motion.css`, `base.css`

**`guidelines/`** — foundation specimen cards (Design System tab): brand, colour, type, spacing, elevation, motion.

**`components/`**

| Group | Components |
|---|---|
| `brand/` | `Wordmark`, `RedactionMask` |
| `core/` | `Button`, `IconButton`, `Icon`, `Card`, `Badge`, `Tag`, `Metric`, `StatusDot` |
| `forms/` | `Input`, `Select`, `Checkbox`, `Radio`, `Switch` |
| `navigation/` | `Tabs`, `SegmentedControl`, `RailItem` |
| `feedback/` | `Dialog`, `Toast`, `Tooltip`, `EmptyState` |
| `product/` | `PayloadView`, `SweepRow`, `RuleRow` |

Each directory has `<Name>.jsx`, `<Name>.d.ts`, `<Name>.prompt.md`, and one `@dsCard` HTML.

**`ui_kits/`**

- `console/` — the ZeroTrace Console: Sweep Log, Payload Inspector, Policy Rules, Integration/Settings. `index.html` is an interactive click-through.
- `marketing/` — zerotrace.dev: hero, how-it-works, install, pricing, footer. `index.html` is the live page.

No slide template was supplied, so no sample slides exist.
