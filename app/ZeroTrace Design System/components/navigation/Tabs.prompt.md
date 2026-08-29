# Tabs

\`\`\`jsx
<Tabs value={t} onChange={setT} items={[
  {value:'all',label:'All payloads',count:1243},
  {value:'redacted',label:'Redacted',count:27},
  {value:'blocked',label:'Blocked',count:2},
]}/>
\`\`\`

Counts render in mono parentheses. For two or three short toggle-like choices use \`SegmentedControl\` instead.
