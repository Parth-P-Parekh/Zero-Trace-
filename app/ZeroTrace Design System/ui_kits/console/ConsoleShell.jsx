const DS = () => window.ZeroTraceDesignSystem_7f4295;

function ConsoleShell({ view, onView, children, counts }) {
  const { Wordmark, RedactionMask, Button, IconButton, Icon, Card, Badge, Tag, Metric, StatusDot, Input, Select, Checkbox, Radio, Switch, Tabs, SegmentedControl, RailItem, Dialog, Toast, Tooltip, EmptyState, PayloadView, SweepRow, RuleRow } = DS();
  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--paper)' }}>
      <aside style={{ position: 'sticky', top: 0, alignSelf: 'flex-start', height: '100vh', width: 232, flex: '0 0 232px', background: 'var(--surface-dark)', display: 'flex', flexDirection: 'column', padding: 12 }}>
        <div style={{ padding: '6px 10px 20px' }}><Wordmark size={17} tone="inverse" /></div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <RailItem icon="scan-line" label="Sweep log" count={counts.swept} active={view === 'sweep'} onClick={() => onView('sweep')} />
          <RailItem icon="eye-off" label="Findings" count={counts.findings} active={view === 'findings'} onClick={() => onView('findings')} />
          <RailItem icon="list-filter" label="Policy rules" count={counts.rules} active={view === 'rules'} onClick={() => onView('rules')} />
          <RailItem icon="settings-2" label="Integration" active={view === 'integration'} onClick={() => onView('integration')} />
        </div>
        <div style={{ marginTop: 24, padding: '0 10px 8px', font: 'var(--type-eyebrow)', letterSpacing: 'var(--tr-caps)', textTransform: 'uppercase', color: 'rgba(242,242,240,0.36)' }}>Environments</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <RailItem icon="activity" label="production" active={false} />
          <RailItem icon="activity" label="staging" active={false} />
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 10px 6px', boxShadow: 'inset 0 1px 0 var(--border-on-dark)' }}>
          <StatusDot state="clean" size={6} live />
          <span style={{ font: 'var(--type-mono-sm)', color: 'var(--text-on-dark-quiet)' }}>proxy live · 4 ms</span>
        </div>
      </aside>

      <main style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <header style={{ position: 'sticky', top: 0, zIndex: 20, height: 56, display: 'flex', alignItems: 'center', gap: 12, padding: '0 24px', background: 'rgba(232,232,230,0.82)', backdropFilter: 'var(--blur-panel)', boxShadow: 'inset 0 -1px 0 var(--border-hairline)' }}>
          <span style={{ font: 'var(--type-eyebrow)', letterSpacing: 'var(--tr-caps)', textTransform: 'uppercase', color: 'var(--muted)' }}>ZeroTrace</span>
          <span style={{ color: 'var(--text-faint)' }}>·</span>
          <span style={{ font: 'var(--type-body-sm)' }}>{{ sweep: 'Sweep log', findings: 'Findings', rules: 'Policy rules', integration: 'Integration' }[view]}</span>
          <span style={{ flex: 1 }} />
          <Badge status="clean" tone="clean">Sweeping</Badge>
          <Tooltip label="Docs"><IconButton name="book-open" label="Docs" /></Tooltip>
          <div style={{ width: 26, height: 26, borderRadius: '50%', background: 'var(--ink)', color: 'var(--ink-inverse)', display: 'flex', alignItems: 'center', justifyContent: 'center', font: 'var(--type-eyebrow)' }}>AK</div>
        </header>
        <div style={{ padding: '24px 24px 64px', flex: 1 }}>{children}</div>
      </main>
    </div>
  );
}
Object.assign(window, { ConsoleShell });
