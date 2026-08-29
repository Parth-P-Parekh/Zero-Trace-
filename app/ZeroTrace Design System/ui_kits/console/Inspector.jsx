const DS = () => window.ZeroTraceDesignSystem_7f4295;

function Inspector({ row, onClose }) {
  const { Wordmark, RedactionMask, Button, IconButton, Icon, Card, Badge, Tag, Metric, StatusDot, Input, Select, Checkbox, Radio, Switch, Tabs, SegmentedControl, RailItem, Dialog, Toast, Tooltip, EmptyState, PayloadView, SweepRow, RuleRow } = DS();
  const [scanning, setScanning] = React.useState(true);
  const [copied, setCopied] = React.useState(false);
  React.useEffect(() => {
    setScanning(true);
    const t = setTimeout(() => setScanning(false), 1800);
    return () => clearTimeout(t);
  }, [row.id]);

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 40, display: 'flex', justifyContent: 'flex-end', background: 'rgba(17,17,17,0.36)' }} onClick={onClose}>
      <section
        onClick={(e) => e.stopPropagation()}
        style={{ width: 620, maxWidth: '92vw', height: '100%', overflowY: 'auto', background: 'var(--surface-card)', boxShadow: 'var(--sh-4)', animation: 'zt-fade-up var(--d-base) var(--ease-out)' }}
      >
        <header style={{ position: 'sticky', top: 0, display: 'flex', alignItems: 'center', gap: 10, padding: '16px 20px', background: 'var(--surface-card)', boxShadow: 'inset 0 -1px 0 var(--border-hairline)' }}>
          <span style={{ font: 'var(--type-eyebrow)', letterSpacing: 'var(--tr-caps)', textTransform: 'uppercase', color: 'var(--muted)' }}>Patch</span>
          <span style={{ font: 'var(--type-mono-sm)', color: 'var(--text-quiet)' }}>{row.id}</span>
          <span style={{ flex: 1 }} />
          <IconButton name="x" label="Close inspector" onClick={onClose} />
        </header>

        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <Badge tone={row.status} status={row.status}>{row.status === 'clean' ? 'Clean' : row.status === 'blocked' ? 'Blocked' : `(${row.findings.length}) redacted`}</Badge>
            <Badge>{row.model}</Badge>
            <Tag mono>{row.time}</Tag>
            <Tag mono>{row.latency}</Tag>
          </div>

          <PayloadView
            id={row.id}
            model={row.model}
            latency={row.latency}
            status={row.status}
            scanning={scanning}
            lines={row.payload}
            onCopy={() => { setCopied(true); setTimeout(() => setCopied(false), 2600); }}
          />

          <div>
            <div style={{ font: 'var(--type-eyebrow)', letterSpacing: 'var(--tr-caps)', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 10 }}>Findings</div>
            <Card tone="sunken" pad={0}>
              {row.findings.length ? row.findings.map((fd) => (
                <div key={fd.type} style={{ display: 'grid', gridTemplateColumns: '120px 1fr 90px', alignItems: 'center', gap: 12, padding: '10px 14px', boxShadow: 'inset 0 -1px 0 var(--border-hairline)' }}>
                  <Tag mono>{fd.type}</Tag>
                  <span style={{ font: 'var(--type-mono-sm)' }}><RedactionMask type={fd.type} length={fd.length} /></span>
                  <span style={{ font: 'var(--type-eyebrow)', color: 'var(--text-quiet)', textAlign: 'right' }}>{fd.action}</span>
                </div>
              )) : (
                <div style={{ padding: '14px', font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>Clean. Nothing redacted.</div>
              )}
            </Card>
          </div>

          <div>
            <div style={{ font: 'var(--type-eyebrow)', letterSpacing: 'var(--tr-caps)', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 10 }}>Timeline</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, font: 'var(--type-mono-sm)', color: 'var(--text-quiet)' }}>
              <span>{row.time}.204 — payload intercepted, 1.8 KB</span>
              <span>{row.time}.207 — sweep started, 4 rules</span>
              <span>{row.time}.211 — {row.findings.length ? `${row.findings.length} findings replaced in stream` : 'no findings'}</span>
              <span>{row.time}.{row.status === 'blocked' ? '213 — request withheld, upstream never contacted' : '244 — dispatched upstream'}</span>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <Button variant="secondary" iconEnd="arrow-right">Open rule</Button>
            <Button variant="ghost" icon="copy" onClick={() => setCopied(true)}>Copy patch</Button>
          </div>
        </div>

        {copied ? (
          <div style={{ position: 'fixed', bottom: 24, right: 24 }}>
            <Toast status="info" onDismiss={() => setCopied(false)}>Patch copied to clipboard.</Toast>
          </div>
        ) : null}
      </section>
    </div>
  );
}
Object.assign(window, { Inspector });
