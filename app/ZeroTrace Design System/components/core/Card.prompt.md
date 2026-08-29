# Card

\`\`\`jsx
<Card>Sweep summary</Card>
<Card tone="dark" pad={20}>Live payload</Card>
<Card tone="shell" pad={12}><Card>…</Card><Card tone="dark">…</Card></Card>
\`\`\`

At most one \`tone="dark"\` card per screen — it is the focal point, not a style. \`shell\` is the soft outer container from the reference chrome that holds a paired light/dark set.
