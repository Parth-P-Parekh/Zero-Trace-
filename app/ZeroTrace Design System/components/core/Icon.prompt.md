# Icon

Use for every glyph in console UI. Marketing surfaces carry no icons.

\`\`\`jsx
<Icon name="scan-line" />
<Icon name="eye-off" size={14} />
<Icon name="chevron-right" style={{ opacity: 0.52 }} />
\`\`\`

Working set: shield, scan-line, eye-off, key-round, file-text, activity, list-filter, settings-2, chevron-right, chevron-down, arrow-right, arrow-up-right, check, x, copy, search, plus, more-horizontal, clock, terminal, book-open, external-link.

Always inherits \`currentColor\` — never give an icon its own colour, including signal colours. A signal is a \`StatusDot\`, not a coloured icon.
