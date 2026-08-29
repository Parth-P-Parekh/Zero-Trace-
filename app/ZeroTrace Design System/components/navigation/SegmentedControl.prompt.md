# SegmentedControl

\`\`\`jsx
<SegmentedControl value={v} onChange={setV} items={['Personal','Business']} />
<SegmentedControl floating value={v} onChange={setV} items={[
  {value:'reviews',label:'Reviews',dot:'redacted'},{value:'solve',label:'Solve'},{value:'prevent',label:'Prevent'}]}/>
\`\`\`

Labels stay under two words. \`floating\` is for placement over a dark hero card, bottom-right, matching the reference chrome.
