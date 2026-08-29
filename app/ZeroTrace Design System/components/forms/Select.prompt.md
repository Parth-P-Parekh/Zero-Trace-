# Select

\`\`\`jsx
<Select label="Action" options={['Redact', 'Block', 'Log only']} />
<Select size="sm" options={[{value:'24h',label:'Last 24h'},{value:'7d',label:'Last 7 days'}]} />
\`\`\`

Option labels are sentence case. Use a \`SegmentedControl\` instead when there are two or three short choices.
