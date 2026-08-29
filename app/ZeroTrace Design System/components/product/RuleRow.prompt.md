# RuleRow

\`\`\`jsx
<RuleRow name="us social security numbers" pattern="\\d{3}-\\d{2}-\\d{4}" action="Redact" hits="(27)" active onToggle={fn}/>
<RuleRow name="no raw card numbers" pattern="luhn:16" action="Block" hits="(2)" active={false}/>
\`\`\`

An inactive rule drops to ramp \`.52\` rather than disappearing — the operator must see what is switched off.
