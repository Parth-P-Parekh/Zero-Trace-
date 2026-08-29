# Button

Any action. One primary per view; everything else secondary or ghost.

\`\`\`jsx
<Button>Start sweeping</Button>
<Button variant="secondary" iconEnd="arrow-right">Restart investigation</Button>
<Button variant="ghost" icon="copy" size="sm">Copy patch</Button>
<Button variant="inverse" pill onDark>Read the docs</Button>
<Button disabled>Dispatch</Button>
\`\`\`

Labels are verb-first sentence case, never all-caps, never with an exclamation mark. \`pill\` matches the reference chrome for marketing and segmented contexts; console buttons stay on the 6/8px radii.
