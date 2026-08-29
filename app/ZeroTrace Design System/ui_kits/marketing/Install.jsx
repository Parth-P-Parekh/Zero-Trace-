const DS = () => window.ZeroTraceDesignSystem_7f4295;

const INSTALL_TABS = {
  node: ['import OpenAI from "openai";', '', 'const client = new OpenAI({', '  baseURL: "https://proxy.zerotrace.dev/v1",', '});'],
  python: ['from openai import OpenAI', '', 'client = OpenAI(', '    base_url="https://proxy.zerotrace.dev/v1",', ')'],
  curl: ['curl https://proxy.zerotrace.dev/v1/chat/completions \\', '  -H "Authorization: Bearer $OPENAI_API_KEY" \\', '  -d @payload.json'],
};

function Install() {
  const { Tabs, Button, IconButton, Tooltip, StatusDot, Badge } = DS();
  const [tab, setTab] = React.useState('node');
  return (
    <section id="install" style={{ maxWidth: 1200, margin: '0 auto', padding: '128px 24px 0' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.15fr', gap: 48, alignItems: 'center' }}>
        <div>
          <h2 style={{ font: 'var(--w-regular) var(--t-42)/1.14 var(--font-core)', letterSpacing: 'var(--tr-display)', maxWidth: '18ch' }}>
            Two lines of config
          </h2>
          <p style={{ marginTop: 16, font: 'var(--type-body)', color: 'var(--text-body)', maxWidth: '46ch' }}>
            Your provider keys stay with you. ZeroTrace never stores payload bodies — only the patch record and a salted hash of each finding.
          </p>
          <div style={{ display: 'flex', gap: 10, marginTop: 24 }}>
            <Button pill>Start sweeping</Button>
            <Button pill variant="secondary" iconEnd="arrow-up-right">Self-host guide</Button>
          </div>
        </div>
        <div style={{ background: 'var(--surface-code)', borderRadius: 'var(--r-16)', boxShadow: 'var(--sh-4)', overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 12px 0 20px' }}>
            <Tabs onDark value={tab} onChange={setTab} items={[{ value: 'node', label: 'node' }, { value: 'python', label: 'python' }, { value: 'curl', label: 'curl' }]} style={{ flex: 1, boxShadow: 'none' }} />
            <Tooltip label="Copy"><IconButton name="copy" label="Copy snippet" size={26} onDark /></Tooltip>
          </div>
          <pre style={{ margin: 0, padding: '18px 20px 26px', font: 'var(--type-mono)', letterSpacing: 'var(--tr-mono)', lineHeight: 1.62, color: 'var(--text-on-dark-body)', overflowX: 'auto' }}>{INSTALL_TABS[tab].join('\n')}</pre>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 20px', boxShadow: 'inset 0 1px 0 var(--border-on-dark)' }}>
            <StatusDot state="clean" size={6} live />
            <span style={{ font: 'var(--type-mono-sm)', color: 'var(--text-on-dark-quiet)' }}>first sweep in 90 s, median</span>
          </div>
        </div>
      </div>
    </section>
  );
}
Object.assign(window, { Install });
