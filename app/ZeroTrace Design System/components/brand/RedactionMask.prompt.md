# RedactionMask

Use wherever a detected value is shown as redacted — payload views, sweep log rows, marketing code samples, docs.

\`\`\`jsx
<code>"ssn": "<RedactionMask type="us_ssn">123-45-6789</RedactionMask>"</code>
<RedactionMask length={32} type="api_key" animate />
<RedactionMask type="email" revealed>ana@acme.io</RedactionMask>
\`\`\`

- Block width always matches the original character count — the shape of the data survives, the data doesn't.
- \`animate\` plays the drain sweep; use it once per view, on the value being caught, not on every mask.
- In plain-text contexts write the token form instead: \`⟨redacted:us_ssn⟩\`.
