const DS = () => window.ZeroTraceDesignSystem_7f4295;

function Hero() {
  const { Button, PayloadView, SegmentedControl, Metric } = DS();
  const [mode, setMode] = React.useState('redact');
  const [scan, setScan] = React.useState(true);
  React.useEffect(() => { setScan(true); const t = setTimeout(() => setScan(false), 2200); return () => clearTimeout(t); }, [mode]);

  const lines = mode === 'redact'
    ? ['{', '  "messages": [{ "role": "user", "content":',
        ['    "support log — ssn ', { mask: '123-45-6789', type: 'us_ssn' }, ','],
        ['     key ', { mask: 'sk-live-9fj2kd01', type: 'api_key' }, '"'],
        '  }]', '}']
    : ['{', '  "messages": [{ "role": "user", "content":', '    "support log — ssn 123-45-6789,', '     key sk-live-9fj2kd01"', '  }]', '}'];

  return (
    <section style={{ maxWidth: 1200, margin: '0 auto', padding: '48px 24px 0' }}>
      <h1 style={{ font: 'var(--w-regular) var(--t-72)/1.06 var(--font-core)', letterSpacing: 'var(--tr-display)', maxWidth: '17ch' }}>
        Your prompts leave <span style={{ opacity: 0.36 }}>with nothing in them</span>
      </h1>
      <p style={{ marginTop: 20, font: 'var(--type-body)', color: 'var(--text-body)', maxWidth: '58ch' }}>
        ZeroTrace inspects every outbound LLM call, redacts what shouldn't be in it, and logs the patch. Two lines of config.
      </p>
      <div style={{ display: 'flex', gap: 10, marginTop: 24, alignItems: 'center' }}>
        <Button size="lg" pill>Start sweeping</Button>
        <Button size="lg" pill variant="secondary" iconEnd="arrow-right">Read the docs</Button>
      </div>

      <div style={{ position: 'relative', marginTop: 40, background: 'var(--surface-dark)', borderRadius: 'var(--r-20)', padding: '32px 32px 40px', boxShadow: 'var(--sh-4)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 32, marginBottom: 22 }}>
          <div>
            <div style={{ font: 'var(--type-eyebrow)', letterSpacing: 'var(--tr-caps)', textTransform: 'uppercase', color: 'rgba(242,242,240,0.36)' }}>Outbound payload</div>
            <div style={{ marginTop: 8, font: 'var(--w-regular) var(--t-26)/1.22 var(--font-core)', letterSpacing: 'var(--tr-heading)', color: 'var(--ink-inverse)' }}>
              Two values caught mid-stream
            </div>
          </div>
          <SegmentedControl floating value={mode} onChange={setMode} items={[{ value: 'redact', label: 'With ZeroTrace' }, { value: 'raw', label: 'Without' }]} />
        </div>
        <PayloadView lines={lines} model="gpt-4o" latency={mode === 'redact' ? '240 ms' : '236 ms'} status={mode === 'redact' ? 'redacted' : 'blocked'} scanning={scan && mode === 'redact'} id="pl_8f3a21c9e04b" style={{ boxShadow: 'none', background: '#000' }} />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 24, marginTop: 28, paddingTop: 24, boxShadow: 'inset 0 1px 0 var(--border-on-dark)' }}>
          <Metric label="Added latency" value="4" unit="ms" note="p95, in-stream" size="sm" onDark />
          <Metric label="Detectors" value="41" note="pii, secrets, financial" size="sm" onDark />
          <Metric label="Payloads swept" value="1.24M" note="last 24h, all workspaces" size="sm" onDark />
        </div>
      </div>
    </section>
  );
}
Object.assign(window, { Hero });
