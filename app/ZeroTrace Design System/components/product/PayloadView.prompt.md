# PayloadView

The product's hero surface. Use it in the console inspector, the marketing hero, and docs.

\`\`\`jsx
<PayloadView
  id="pl_8f3a21c9e04b" model="gpt-4o" latency="240 ms" status="redacted" scanning
  lines={[
    '{',
    '  "messages": [{ "role": "user", "content":',
    ['    "customer ssn ', { mask: '123-45-6789', type: 'us_ssn' }, ', key ', { mask: 'sk-live-9fj2k', type: 'api_key' }, '"'],
    '  }]',
    '}',
  ]}/>
\`\`\`

Never show an unredacted value in any artefact, including mocks. \`scanning\` runs the sweep once on first paint; don't leave it looping in static screenshots.
