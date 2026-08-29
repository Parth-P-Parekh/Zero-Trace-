# UI kit — ZeroTrace Console

The operator surface: what left, what was found in it, what the rules did about it.

**This is an original interface, not a recreation.** No ZeroTrace product source (codebase, Figma, screenshots) was provided — only the wordmark logo sheet and two unrelated reference-chrome images. Treat these screens as proposals built from the brief and the visual foundations.

## Screens

| File | Surface |
|---|---|
| `ConsoleShell.jsx` | Fixed 232px dark rail (wordmark, nav, environments, live proxy status) + 56px blurred sticky top bar. |
| `SweepLog.jsx` | Default view. Four metrics, counted tabs, search, dense 40px sweep rows. |
| `Inspector.jsx` | 620px right drawer. Payload view with the scanline sweep, findings table, event timeline. |
| `PolicyRules.jsx` | Rule table with live switches, new-rule dialog, destructive delete confirm, fail-closed setting. |
| `Integration.jsx` | Snippet card, endpoint/key fields, sweep behaviour checkboxes. |
| `data.js` | Fixture payloads and rules. Every sample value is fake and shown redacted. |

## Interactions in `index.html`

- Rail switches between the four views.
- Any sweep row opens the Inspector; the payload runs its 1.8s scanline once per row.
- Rules toggle live; the ⋯ action opens the destructive delete confirm; **New rule** opens the dialog and fires a toast.
- Search and tab filters both narrow the log; emptying the result shows the empty state.

## Composition

Built entirely from the authored primitives — `ConsoleShell` composes `Wordmark`, `RailItem`, `IconButton`, `Badge`, `StatusDot`, `Tooltip`; no primitive is re-implemented here. The one dark card per screen rule holds: the rail and the payload view carry the weight, everything else is paper.
