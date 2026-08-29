const DS = () => window.ZeroTraceDesignSystem_7f4295;

const PRICING_PLANS = [
  { name: 'Solo', price: '$0', unit: '/ month', note: '100K payloads, 1 environment, community detectors.', cta: 'Start sweeping', variant: 'secondary' },
  { name: 'Team', price: '$390', unit: '/ month', note: '10M payloads, unlimited environments, custom rules, SIEM mirror.', cta: 'Start a trial', variant: 'primary', dark: true },
  { name: 'Self-hosted', price: 'Talk to us', unit: '', note: 'Runs in your VPC. Nothing leaves your network, including patch records.', cta: 'Contact sales', variant: 'secondary' },
];

function Pricing() {
  const { Card, Button, Badge, Metric } = DS();
  return (
    <section id="pricing" style={{ maxWidth: 1200, margin: '0 auto', padding: '128px 24px 0' }}>
      <h2 style={{ font: 'var(--w-regular) var(--t-42)/1.14 var(--font-core)', letterSpacing: 'var(--tr-display)' }}>Priced per payload swept</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, marginTop: 40 }}>
        {PRICING_PLANS.map((p) => (
          <Card key={p.name} tone={p.dark ? 'dark' : 'paper'} pad={24} style={{ display: 'flex', flexDirection: 'column', gap: 14, minHeight: 260 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ font: 'var(--type-eyebrow)', letterSpacing: 'var(--tr-caps)', textTransform: 'uppercase', color: p.dark ? 'rgba(242,242,240,0.52)' : 'var(--muted)' }}>{p.name}</span>
              {p.dark ? <Badge onDark>most common</Badge> : null}
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <span style={{ font: 'var(--w-semibold) var(--t-33)/1.06 var(--font-core)', letterSpacing: 'var(--tr-display)', color: p.dark ? 'var(--ink-inverse)' : 'var(--ink)' }}>{p.price}</span>
              <span style={{ font: 'var(--type-body-sm)', color: p.dark ? 'rgba(242,242,240,0.52)' : 'var(--text-quiet)' }}>{p.unit}</span>
            </div>
            <p style={{ font: 'var(--type-body-sm)', color: p.dark ? 'rgba(242,242,240,0.72)' : 'var(--text-quiet)', flex: 1 }}>{p.note}</p>
            <Button full pill variant={p.dark ? 'inverse' : 'secondary'}>{p.cta}</Button>
          </Card>
        ))}
      </div>
    </section>
  );
}
Object.assign(window, { Pricing });
