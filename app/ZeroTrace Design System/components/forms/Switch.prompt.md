# Switch

\`\`\`jsx
<Switch checked={rule.active} onChange={fn} label="Active" />
<Switch checked hint="Applies to every outbound call." label="Sweep streaming responses" />
\`\`\`

Switches apply immediately with no confirm — if the change is destructive, use a \`Dialog\`.
