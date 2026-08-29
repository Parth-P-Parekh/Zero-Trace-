const DS = () => window.ZeroTraceDesignSystem_7f4295;

const RULE_HEAD = ['Rule', 'Pattern', 'Action', 'Hits', ''];

function PolicyRules({ rules, onToggle, onDelete }) {
  const { Wordmark, RedactionMask, Button, IconButton, Icon, Card, Badge, Tag, Metric, StatusDot, Input, Select, Checkbox, Radio, Switch, Tabs, SegmentedControl, RailItem, Dialog, Toast, Tooltip, EmptyState, PayloadView, SweepRow, RuleRow } = DS();
  const [confirm, setConfirm] = React.useState(null);
  const [toast, setToast] = React.useState(null);
  const [draft, setDraft] = React.useState(false);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 1000 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 24 }}>
        <div>
          <h1 style={{ font: 'var(--type-h1)', letterSpacing: 'var(--tr-display)' }}>Policy rules</h1>
          <p style={{ marginTop: 8, font: 'var(--type-body)', color: 'var(--text-body)', maxWidth: '52ch' }}>Rules run in order on every outbound payload. A rule with no redaction strategy blocks the request instead.</p>
        </div>
        <Button icon="plus" onClick={() => setDraft(true)}>New rule</Button>
      </div>

      <Card pad={0}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 200px 96px 80px 62px', gap: 12, padding: '12px', font: 'var(--type-eyebrow)', letterSpacing: 'var(--tr-caps)', textTransform: 'uppercase', color: 'var(--muted)', boxShadow: 'inset 0 -1px 0 var(--border-hairline)' }}>
          {RULE_HEAD.map((h, i) => <span key={i}>{h}</span>)}
        </div>
        {rules.map((r) => (
          <RuleRow key={r.name} {...r} onToggle={() => onToggle(r.name)} onEdit={() => setConfirm(r)} />
        ))}
      </Card>

      <Card tone="sunken" pad={20} style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
        <div style={{ flex: 1 }}>
          <div style={{ font: 'var(--type-h3)', letterSpacing: 'var(--tr-heading)' }}>Fail closed</div>
          <p style={{ marginTop: 4, font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '58ch' }}>If a sweep errors, the payload is not dispatched and is not stored. Turning this off dispatches unswept payloads.</p>
        </div>
        <Switch checked label="Active" />
      </Card>

      {draft ? (
        <Dialog open width={480} title="New rule" description="The pattern runs against the serialised payload body." confirmLabel="Create rule" onCancel={() => setDraft(false)} onConfirm={() => { setDraft(false); setToast('Rule saved. Active on the next payload.'); }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Input label="Rule name" placeholder="no raw card numbers" />
            <Input label="Pattern" mono placeholder="luhn:16" />
            <Select label="Action" options={['Redact and dispatch', 'Block the request', 'Log only']} />
          </div>
        </Dialog>
      ) : null}

      {confirm ? (
        <Dialog open destructive
          title={`Delete rule "${confirm.pattern}"?`}
          description="Payloads matching it will dispatch unredacted."
          confirmLabel="Delete rule"
          onCancel={() => setConfirm(null)}
          onConfirm={() => { onDelete(confirm.name); setConfirm(null); setToast('Rule deleted.'); }} />
      ) : null}

      {toast ? (
        <div style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 70 }}>
          <Toast status="clean" onDismiss={() => setToast(null)}>{toast}</Toast>
        </div>
      ) : null}
    </div>
  );
}
Object.assign(window, { PolicyRules });
