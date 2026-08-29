# Dialog

Only for decisions with consequences — deleting a rule, disabling the sweeper.

\`\`\`jsx
<Dialog open={open} destructive
  title='Delete rule "us_ssn"?'
  description="Payloads matching it will dispatch unredacted."
  confirmLabel="Delete rule" onConfirm={fn} onCancel={close}/>
\`\`\`

Title is the question, description is the consequence, confirm label names the act — never "OK".
