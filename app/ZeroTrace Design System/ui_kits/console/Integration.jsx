const DS = () => window.ZeroTraceDesignSystem_7f4295;

const INTEGRATION_SNIPPET = [
  'import OpenAI from "openai";',
  '',
  'const client = new OpenAI({',
  '  baseURL: "https://proxy.zerotrace.dev/v1",',
  '  defaultHeaders: { "zt-env": "production" },',
  '});',
];

function Integration() {
  const { Wordmark, RedactionMask, Button, IconButton, Icon, Card, Badge, Tag, Metric, StatusDot, Input, Select, Checkbox, Radio, Switch, Tabs, SegmentedControl, RailItem, Dialog, Toast, Tooltip, EmptyState, PayloadView, SweepRow, RuleRow } = DS();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 1000 }}>
      <div>
        <h1 style={{ font: 'var(--type-h1)', letterSpacing: 'var(--tr-display)' }}>Integration</h1>
        <p style={{ marginTop: 8, font: 'var(--type-body)', color: 'var(--text-body)', maxWidth: '56ch' }}>Point your SDK base URL at the proxy. Nothing else changes — same routes, same responses, same keys.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.35fr 1fr', gap: 12, alignItems: 'start' }}>
        <div style={{ background: 'var(--surface-code)', borderRadius: 'var(--r-12)', boxShadow: 'var(--sh-3)', overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 12px 12px 16px', boxShadow: 'inset 0 -1px 0 var(--border-on-dark)' }}>
            <StatusDot state="clean" size={6} live />
            <span style={{ font: 'var(--type-mono-sm)', color: 'var(--text-on-dark-body)' }}>node · openai@4</span>
            <span style={{ flex: 1 }} />
            <Tooltip label="Copy snippet"><IconButton name="copy" label="Copy snippet" size={24} onDark /></Tooltip>
          </div>
          <pre style={{ margin: 0, padding: '16px', font: 'var(--type-mono)', letterSpacing: 'var(--tr-mono)', lineHeight: 1.62, color: 'var(--text-on-dark-body)' }}>{INTEGRATION_SNIPPET.join('\n')}</pre>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Card pad={18} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Input label="Proxy endpoint" mono defaultValue="proxy.zerotrace.dev/v1" prefix="https://" />
            <Input label="Environment key" mono defaultValue="zt_live_9f3a…" hint="Rotated every 90 days." />
            <Button variant="secondary" full iconEnd="external-link">Open docs</Button>
          </Card>
          <Card tone="dark" pad={18}><Metric label="Time to first sweep" value="90" unit="s" note="median, new workspace" size="sm" onDark /></Card>
        </div>
      </div>

      <Card pad={20} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ font: 'var(--type-eyebrow)', letterSpacing: 'var(--tr-caps)', textTransform: 'uppercase', color: 'var(--muted)' }}>Sweep behaviour</div>
        <Checkbox label="Sweep streaming responses" hint="Inspects server-sent chunks as they return." checked />
        <Checkbox label="Log redacted values (hashed)" hint="Stores a salted hash, never the value." checked />
        <Checkbox label="Mirror patches to SIEM" hint="Requires an outbound webhook." />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 12, boxShadow: 'inset 0 1px 0 var(--border-hairline)' }}>
          <Switch checked label="Block on sweep failure" />
          <span style={{ flex: 1 }} />
          <Tag mono>v2.8.6</Tag>
          <Badge status="clean" tone="clean">Healthy</Badge>
        </div>
      </Card>
    </div>
  );
}
Object.assign(window, { Integration });
