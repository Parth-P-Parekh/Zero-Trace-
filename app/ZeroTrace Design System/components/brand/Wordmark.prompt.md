# Wordmark

Renders the ZeroTrace mark; use it anywhere the logo goes — nav, footer, login, deck title, favicon-adjacent chrome.

\`\`\`jsx
<Wordmark size={20} />
<Wordmark size={64} drain />
<Wordmark size={18} tone="inverse" />
<Wordmark size={40} descriptor="payload sweeper" />
<Wordmark size={12} />           {/* mono fallback forced automatically */}
\`\`\`

- \`variant="mono"\` for one-colour repro, embroidery, foil, or placement over photography. Anything under 180px wide should be mono.
- Approved backgrounds only: paper \`#E8E8E6\`, white, dark \`#0B0B0B\`, black. Never a tint, gradient or image.
- Never recolour, never reverse the fade, never per-word fade, never add stroke/shadow/glow.
- This component is a **stand-in**: the brand's outlined SVGs were not supplied. Replace with \`<img src="assets/logo/zerotrace-primary.svg">\` when they arrive.
