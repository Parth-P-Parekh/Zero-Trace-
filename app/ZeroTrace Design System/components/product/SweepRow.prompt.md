# SweepRow

\`\`\`jsx
<SweepRow time="14:02:11" path="/v1/chat/completions" model="gpt-4o"
  findings={['us_ssn','api_key']} status="redacted" latency="240 ms" onClick={fn}/>
<SweepRow time="14:02:09" path="/v1/embeddings" model="text-embedding-3" status="clean" latency="88 ms"/>
\`\`\`

Rows are separated by a \`.11\` hairline only — no striping, no borders, no card per row. Put a caps header row above with the same grid.
