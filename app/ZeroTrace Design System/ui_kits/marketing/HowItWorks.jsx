const DS = () => window.ZeroTraceDesignSystem_7f4295;

const HIW_STEPS = [
  { n: '01', t: 'Point the base URL', d: 'One config line. Same routes, same responses, your own provider keys — the proxy is transparent.' },
  { n: '02', t: 'Sweep in the stream', d: '41 detectors run on the serialised body before dispatch. Nothing is buffered to disk and nothing waits.' },
  { n: '03', t: 'Redact or block', d: 'Matched values are replaced in place. A rule with no redaction strategy withholds the request instead.' },
  { n: '04', t: 'Log the patch', d: 'Every intervention is recorded with a salted hash of the value, the rule that caught it, and the latency it cost.' },
];

function HowItWorks() {
  const { Card, Badge, Tag, Button, SweepRow } = DS();
  return (
    <section id="how" style={{ maxWidth: 1200, margin: '0 auto', padding: '128px 24px 0' }}>
      <h2 style={{ font: 'var(--w-regular) var(--t-42)/1.14 var(--font-core)', letterSpacing: 'var(--tr-display)', maxWidth: '24ch' }}>
        Four steps, none of which your application code notices
      </h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginTop: 40 }}>
        {HIW_STEPS.map((s) => (
          <Card key={s.n} pad={20} interactive style={{ display: 'flex', flexDirection: 'column', gap: 10, minHeight: 200 }}>
            <span style={{ font: 'var(--type-mono-sm)', color: 'var(--text-faint)' }}>{s.n}</span>
            <span style={{ font: 'var(--type-h3)', letterSpacing: 'var(--tr-heading)' }}>{s.t}</span>
            <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>{s.d}</span>
          </Card>
        ))}
      </div>

      <div id="coverage" style={{ marginTop: 128 }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 32 }}>
          <h2 style={{ font: 'var(--w-regular) var(--t-42)/1.14 var(--font-core)', letterSpacing: 'var(--tr-display)', maxWidth: '22ch' }}>
            Not just keys and social security numbers
          </h2>
          <p style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '38ch' }}>
            Detectors cover identifiers, secrets, financial data, health records and anything you can express as a pattern or a custom rule.
          </p>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 24 }}>
          {['us_ssn', 'api_key', 'jwt', 'pan', 'iban', 'email', 'phone', 'address', 'passport', 'nhs_number', 'aws_secret', 'private_key', 'oauth_token', 'dob', 'mrn', 'plate', 'tax_id', 'custom:*'].map((t) => (
            <Tag key={t} mono>{t}</Tag>
          ))}
        </div>
        <Card pad={0} style={{ marginTop: 28 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '78px 1fr 96px 150px 74px 64px 20px', gap: 12, padding: '10px 12px', font: 'var(--type-eyebrow)', letterSpacing: 'var(--tr-caps)', textTransform: 'uppercase', color: 'var(--muted)', boxShadow: 'inset 0 -1px 0 var(--border-hairline)' }}>
            <span>Time</span><span>Path</span><span>Model</span><span>Findings</span><span>Result</span><span>Latency</span><span />
          </div>
          <SweepRow time="14:02:11" path="/v1/chat/completions" model="gpt-4o" findings={['us_ssn', 'api_key']} status="redacted" latency="240 ms" />
          <SweepRow time="14:02:09" path="/v1/embeddings" model="text-embedding-3" status="clean" latency="88 ms" />
          <SweepRow time="14:01:58" path="/v1/messages" model="claude-sonnet" findings={['pan', 'email', 'phone']} status="blocked" latency="—" />
        </Card>
      </div>
    </section>
  );
}
Object.assign(window, { HowItWorks });
