# Input

\`\`\`jsx
<Input label="Rule name" placeholder="no raw card numbers" />
<Input icon="search" placeholder="Search payload ids" size="sm" />
<Input label="Pattern" mono defaultValue="\\d{3}-\\d{2}-\\d{4}" />
<Input label="Upstream base URL" prefix="https://" error="Host must resolve." />
\`\`\`

Placeholders show a realistic example value, never "Enter a rule name". Errors state what happened and what didn't: \`Upstream returned 503. Payload was not dispatched.\`
