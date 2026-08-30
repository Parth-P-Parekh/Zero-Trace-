'use client';

import { useState } from 'react';
import { Badge, Button, Card, Icon, Metric, StatusDot, Switch, Tabs, Tag, Tooltip, EmptyState } from '@/ds';
import { EscalationCurve } from '@/components/EscalationCurve';
import { GridHead, PageHead, SectionLabel } from '@/components/Chrome';
import { classToken, count, micros, percent } from '@/lib/format';
import type { Detector, EscalationPoint } from '@/lib/types';

// The class column carries a mono tag, so it needs real width - at 84px the tag
// overflowed into precision.
const COLUMNS = 'minmax(200px,1fr) minmax(150px,190px) 128px 78px 68px 78px 96px';

export function DetectorsView({
  detectors,
  curve,
}: {
  detectors: Detector[];
  curve: EscalationPoint[];
}) {
  const [tab, setTab] = useState('active');

  const rows = detectors.filter((d) =>
    tab === 'active' ? d.status === 'active'
      : tab === 'synthesized' ? d.source === 'synthesized'
        : d.status === 'quarantined' || d.status === 'rejected',
  );

  const synthesized = detectors.filter((d) => d.source === 'synthesized' && d.status === 'active');
  const last = curve[curve.length - 1];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 'var(--page-max)' }}>
      <PageHead
        title="Detectors the firewall wrote for itself"
        sub="The adjudicator is a teacher, not the runtime. When it catches what the deterministic rules missed, a detector is written, validated against the full corpus, and promoted to the hot path."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(340px,1fr))', gap: 12, alignItems: 'start' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,minmax(0,1fr))', gap: 12 }}>
          <Card pad={18}>
            <Metric label="Active detectors" value={detectors.filter((d) => d.status === 'active').length} note="on the hot path" size="sm" />
          </Card>
          <Card pad={18}>
            <Metric label="Written by ZeroTrace" value={synthesized.length} note="promoted after validation" size="sm" />
          </Card>
          <Card pad={18}>
            <Metric label="Escalation rate" value={percent(last.escalationRate)} note={`down from ${percent(curve[0].escalationRate)}`} size="sm" />
          </Card>
          <Card pad={18}>
            <Metric label="Cost per 1M tokens" value={`₹${(last.costPaisePerMillion / 100).toFixed(2)}`} note="falls as escalation falls" size="sm" />
          </Card>
        </div>

        {/* The curve is the argument, so it takes this screen's one dark card. */}
        <Card tone="dark" pad={24}>
          <SectionLabel onDark>Escalation rate, runs 1 to 3</SectionLabel>
          <EscalationCurve points={curve} />
        </Card>
      </div>

      <Card pad={0}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '16px 16px 0' }}>
          <Tabs
            value={tab}
            onChange={setTab}
            style={{ flex: 1 }}
            items={[
              { value: 'active', label: 'Active', count: detectors.filter((d) => d.status === 'active').length },
              { value: 'synthesized', label: 'Written by ZeroTrace', count: detectors.filter((d) => d.source === 'synthesized').length },
              { value: 'held', label: 'Quarantined and rejected', count: detectors.filter((d) => d.status === 'quarantined' || d.status === 'rejected').length },
            ]}
          />
        </div>

        <div className="zt-table">
          <div>
            <GridHead
              columns={COLUMNS}
              cells={['Detector', 'Pattern', 'Class', 'Precision', 'Recall', 'Runtime', 'Status']}
            />
            {rows.length ? (
              rows.map((d) => <DetectorRow key={d.id} detector={d} />)
            ) : (
              <EmptyState
                icon="list-filter"
                title="Nothing here yet"
                description="Detectors appear once the validator has run a candidate against the corpus."
              />
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}

function DetectorRow({ detector: d }: { detector: Detector }) {
  const [live, setLive] = useState(d.status === 'active');
  const synthesized = d.source === 'synthesized';

  return (
    <div
      style={{
        display: 'grid', gridTemplateColumns: COLUMNS, gap: 12, alignItems: 'center',
        minHeight: 'var(--row-h)', padding: '10px 16px',
        boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
      }}
    >
      <span style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ font: 'var(--type-body-sm)' }}>{d.name}</span>
        {synthesized ? (
          // Provenance is the thing being bought on this screen, so it is stated in
          // full rather than hidden behind a hover.
          <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>
            written by ZeroTrace{d.writtenAt ? ` at ${new Date(d.writtenAt).toISOString().slice(11, 16)}` : ''}
            {d.originFindingId ? ` from finding ${d.originFindingId}` : ''}
          </span>
        ) : (
          <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>seed pack</span>
        )}
      </span>

      <Tooltip label={d.pattern} mono>
        <span
          className="zt-mono-sm"
          style={{ color: 'var(--text-body)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}
        >
          {d.pattern}
        </span>
      </Tooltip>

      <span style={{ minWidth: 0, overflow: 'hidden' }}><Tag mono>{classToken(d.entityClass)}</Tag></span>
      <span className="zt-mono-sm zt-nums" style={{ color: 'var(--text-body)' }}>{d.precision.toFixed(2)}</span>
      <span className="zt-mono-sm zt-nums" style={{ color: 'var(--text-body)' }}>{d.recall.toFixed(2)}</span>
      <span className="zt-mono-sm zt-nums" style={{ color: d.runtimeUs > 1500 ? 'var(--signal-blocked)' : 'var(--text-quiet)' }}>
        {micros(d.runtimeUs)}
      </span>

      <span style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'flex-end' }}>
        {d.status === 'active' ? (
          <Switch checked={live} onChange={() => setLive((v) => !v)} aria-label={`${d.name} on the hot path`} />
        ) : (
          <Tooltip label={d.reason ?? 'Held by the validator'}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <StatusDot state={d.status === 'rejected' ? 'blocked' : 'redacted'} size={6} />
              <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>
                {d.status === 'rejected' ? 'Rejected' : 'Quarantined'}
              </span>
            </span>
          </Tooltip>
        )}
      </span>
    </div>
  );
}
