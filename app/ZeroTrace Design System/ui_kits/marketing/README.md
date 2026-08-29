# UI kit — zerotrace.dev

The marketing site. First contact: what the product does, in the product's own artefacts.

**Original, not a recreation.** No ZeroTrace website source was provided. The chrome conventions — pill nav buttons, a full-bleed near-black hero card with heavy rounding, a floating white segmented pill over it, paired light/dark cards — are lifted structurally from the two reference images supplied (`uploads/download.jpg`, `uploads/download (1).jpg`) and re-rendered in ZeroTrace's achromatic palette.

## Sections

| File | Section |
|---|---|
| `SiteNav.jsx` | Sticky nav. Transparent at rest; gains 72% paper, blur and a hairline after 8px of scroll. |
| `Hero.jsx` | 72px fading headline, then a dark hero card holding a live `PayloadView`. The floating segmented pill switches **With ZeroTrace / Without**, which re-runs the sweep. |
| `HowItWorks.jsx` | Four numbered steps as interactive paper cards, then coverage: the full detector tag set and three real sweep rows. |
| `Install.jsx` | node / python / curl snippet card with dark tabs. |
| `Pricing.jsx` | Three plans; the middle one is the screen's single dark card. |
| `SiteFooter.jsx` | Dark footer with the descriptor lockup and live status. |

## Rules held

- No icons anywhere in marketing (per ICONOGRAPHY). No imagery, no illustration, no gradient decoration.
- Exactly one dark focal surface per section.
- The headline uses the fading treatment: first clause at full ink, continuation at ramp `.36`.
- Every sample value in the hero payload is fake and shown redacted.
