const DS = () => window.ZeroTraceDesignSystem_7f4295;

const FOOTER_COLS = [
  { h: 'Product', l: ['How it works', 'Coverage', 'Install', 'Pricing', 'Changelog'] },
  { h: 'Developers', l: ['Docs', 'Detector reference', 'Self-host guide', 'Status', 'SDKs'] },
  { h: 'Company', l: ['Security', 'Trust centre', 'Privacy', 'Terms', 'Contact'] },
];

function SiteFooter() {
  const { Wordmark, Button, Input, StatusDot } = DS();
  const link = { font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)', textDecoration: 'none' };
  return (
    <footer style={{ marginTop: 128, background: 'var(--surface-dark)', color: 'var(--ink-inverse)' }}>
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '64px 24px 32px', display: 'grid', gridTemplateColumns: '1.4fr repeat(3,1fr)', gap: 40 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, alignItems: 'flex-start' }}>
          <Wordmark size={22} tone="inverse" descriptor="payload sweeper" />
          <p style={{ font: 'var(--type-body-sm)', color: 'var(--text-on-dark-quiet)', maxWidth: '30ch' }}>
            The guardrail between your application and the model.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <StatusDot state="clean" size={6} live />
            <span style={{ font: 'var(--type-mono-sm)', color: 'var(--text-on-dark-quiet)' }}>all systems sweeping</span>
          </div>
        </div>
        {FOOTER_COLS.map((c) => (
          <div key={c.h} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <span style={{ font: 'var(--type-eyebrow)', letterSpacing: 'var(--tr-caps)', textTransform: 'uppercase', color: 'rgba(242,242,240,0.36)' }}>{c.h}</span>
            {c.l.map((l) => <a key={l} href="#" style={link}>{l}</a>)}
          </div>
        ))}
      </div>
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '20px 24px 40px', display: 'flex', alignItems: 'center', gap: 16, boxShadow: 'inset 0 1px 0 var(--border-on-dark)' }}>
        <span style={{ font: 'var(--type-mono-sm)', color: 'rgba(242,242,240,0.36)' }}>© 2026 ZeroTrace · SOC 2 Type II</span>
        <span style={{ flex: 1 }} />
        <Button size="sm" pill variant="ghost" onDark iconEnd="arrow-up-right">Trust centre</Button>
      </div>
    </footer>
  );
}
Object.assign(window, { SiteFooter });
