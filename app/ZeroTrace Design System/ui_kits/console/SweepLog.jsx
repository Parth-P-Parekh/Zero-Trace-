const DS = () => window.ZeroTraceDesignSystem_7f4295;

const SWEEP_HEAD = ['Time', 'Path', 'Model', 'Findings', 'Result', 'Latency', ''];

function SweepLog({ rows, onOpen, activeId }) {
  const { Wordmark, RedactionMask, Button, IconButton, Icon, Card, Badge, Tag, Metric, StatusDot, Input, Select, Checkbox, Radio, Switch, Tabs, SegmentedControl, RailItem, Dialog, Toast, Tooltip, EmptyState, PayloadView, SweepRow, RuleRow } = DS();
  const [tab, setTab] = React.useState('all');
  const [range, setRange] = React.useState('24h');
  const [q, setQ] = React.useState('');

  const filtered = rows.filter((r) => {
    if (tab === 'redacted' && r.status !== 'redacted') return false;
    if (tab === 'blocked' && r.status !== 'blocked') return false;
    if (q && !(r.path + r.model + r.findings.join(' ')).includes(q)) return false;
    return true;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 1200 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 24 }}>
        <h1 style={{ font: 'var(--type-h1)', letterSpacing: 'var(--tr-display)', maxWidth: '22ch' }}>Every outbound payload, before it left</h1>
        <SegmentedControl value={range} onChange={setRange} size="sm" items={[{ value: '24h', label: 'Last 24h' }, { value: '7d', label: '7 days' }, { value: '30d', label: '30 days' }]} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
        <Card pad={18}><Metric label="Payloads swept" value="1.24M" note="last 24h" size="sm" /></Card>
        <Card pad={18}><Metric label="Values redacted" value="8,411" note="across 27 rules" size="sm" /></Card>
        <Card pad={18}><Metric label="Requests blocked" value="12" note="no redaction strategy" size="sm" /></Card>
        <Card tone="dark" pad={18}><Metric label="Added latency" value="4" unit="ms" note="p95, in-stream" size="sm" onDark /></Card>
      </div>

      <Card pad={0}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '16px 16px 0' }}>
          <Tabs value={tab} onChange={setTab} style={{ flex: 1 }} items={[
            { value: 'all', label: 'All payloads', count: rows.length },
            { value: 'redacted', label: 'Redacted', count: rows.filter((r) => r.status === 'redacted').length },
            { value: 'blocked', label: 'Blocked', count: rows.filter((r) => r.status === 'blocked').length },
          ]} />
          <Input size="sm" icon="search" placeholder="Search paths and findings" value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 240, paddingBottom: 10 }} />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '78px 1fr 96px 150px 74px 64px 20px', gap: 12, padding: '10px 12px', font: 'var(--type-eyebrow)', letterSpacing: 'var(--tr-caps)', textTransform: 'uppercase', color: 'var(--muted)', boxShadow: 'inset 0 -1px 0 var(--border-hairline)' }}>
          {SWEEP_HEAD.map((h, i) => <span key={i}>{h}</span>)}
        </div>
        {filtered.length ? filtered.map((r) => (
          <SweepRow key={r.id} {...r} active={r.id === activeId} onClick={() => onOpen(r)} />
        )) : (
          <EmptyState icon="search" title="No payloads match" description="Clear the search or widen the range." />
        )}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px' }}>
          <span style={{ font: 'var(--type-eyebrow)', color: 'var(--text-quiet)' }}>({filtered.length}) of 1,243,904 payloads</span>
          <Button size="sm" variant="ghost" iconEnd="chevron-right">Older</Button>
        </div>
      </Card>
    </div>
  );
}
Object.assign(window, { SweepLog });
