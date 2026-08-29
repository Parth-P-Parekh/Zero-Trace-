'use client';

import { Badge, Button, Card, Icon, StatusDot, Tag, Tooltip, EmptyState } from '@/ds';
import { GridHead, PageHead, SectionLabel, StubNote } from '@/components/Chrome';
import { classToken, count, exact, percent } from '@/lib/format';
import type { CoverageReport, Counterfactual, LedgerHead, StubNotice } from '@/lib/types';

const COLUMNS = '84px minmax(0,1fr) 200px 168px';

export function CoverageView({
  report,
  counterfactual,
  ledger,
  stub,
}: {
  report: CoverageReport;
  counterfactual: Counterfactual;
  ledger: LedgerHead;
  stub: StubNotice;
}) {
  const bypass = report.events.filter((e) => e.verdict === 'direct_egress');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 'var(--page-max)' }}>
      <PageHead
        title="What reached a model without passing through"
        sub="Provider domains are denied at the network boundary, so the gateway is the only route out. Anything that tried another one is named below."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(360px,1fr))', gap: 12, alignItems: 'stretch' }}>
        {/* The coverage number is what a security buyer asks for first, so it takes the dark card. */}
        <Card tone="dark" pad={28} style={{ display: 'flex', flexDirection: 'column' }}>
          <SectionLabel onDark>Coverage · {report.windowLabel}</SectionLabel>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <span
              className="zt-nums"
              style={{
                font: 'var(--w-semibold) var(--t-72)/var(--lh-tight) var(--font-core)',
                letterSpacing: 'var(--tr-display)', color: 'var(--ink-inverse)',
              }}
            >
              {percent(report.ratio)}
            </span>
          </div>
          <p style={{ margin: '12px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)', maxWidth: '46ch' }}>
            {exact(report.viaZeroTrace)} requests traversed ZeroTrace. {count(bypass.length)} workloads
            resolved a provider domain without it, and {exact(report.blockedAtBoundary)} connections
            were refused at the boundary.
          </p>
          <div style={{ display: 'flex', gap: 20, marginTop: 'auto', paddingTop: 20, boxShadow: 'inset 0 1px 0 var(--border-on-dark)' }}>
            <DarkStat label="Via ZeroTrace" value={exact(report.viaZeroTrace)} />
            <DarkStat label="Direct egress" value={String(bypass.length)} signal="blocked" />
            <DarkStat label="Refused at boundary" value={exact(report.blockedAtBoundary)} />
          </div>
        </Card>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Card pad={20}>
            <SectionLabel>If ZeroTrace had been off</SectionLabel>
            <p style={{ margin: '0 0 16px', font: 'var(--type-body)', maxWidth: '44ch' }}>
              {exact(counterfactual.spans)} spans across {counterfactual.classes} classes would have
              left the building in the {counterfactual.windowLabel}.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {counterfactual.byClass.slice(0, 5).map((c) => {
                const share = c.spans / counterfactual.byClass[0].spans;
                return (
                  <div key={c.entityClass} style={{ display: 'grid', gridTemplateColumns: '132px 1fr 52px', gap: 10, alignItems: 'center' }}>
                    <span className="zt-mono-sm" style={{ color: 'var(--text-body)' }}>{classToken(c.entityClass)}</span>
                    <span style={{ height: 4, background: 'rgba(17,17,17,0.11)', borderRadius: 'var(--r-pill)', overflow: 'hidden' }}>
                      <span style={{ display: 'block', height: '100%', width: `${share * 100}%`, background: 'rgba(17,17,17,0.52)' }} />
                    </span>
                    <span className="zt-mono-sm zt-nums" style={{ color: 'var(--text-quiet)', textAlign: 'right' }}>{exact(c.spans)}</span>
                  </div>
                );
              })}
            </div>
          </Card>

          <Card pad={20}>
            <SectionLabel>Evidence ledger</SectionLabel>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <StatusDot state={ledger.intact ? 'clean' : 'blocked'} size={6} />
              <span style={{ font: 'var(--type-body-sm)' }}>
                {ledger.intact ? 'Chain verified unbroken' : 'Chain diverges'}
              </span>
              <span style={{ flex: 1 }} />
              <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>{ledger.verifiedAt}</span>
            </div>
            <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '8px 16px', font: 'var(--type-body-sm)' }}>
              <dt style={{ color: 'var(--text-quiet)' }}>Height</dt>
              <dd style={{ margin: 0, textAlign: 'right' }} className="zt-mono-sm zt-nums">{exact(ledger.height)}</dd>
              <dt style={{ color: 'var(--text-quiet)' }}>Head</dt>
              <dd style={{ margin: 0, textAlign: 'right' }} className="zt-mono-sm">{ledger.head}</dd>
            </dl>
            <div style={{ marginTop: 16 }}>
              <Button variant="secondary" size="sm" icon="terminal" full>
                Verify the chain yourself
              </Button>
            </div>
          </Card>
        </div>
      </div>

      <Card pad={0}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, padding: '16px 16px 12px' }}>
          <div style={{ flex: 1 }}>
            <SectionLabel>Exceptions</SectionLabel>
            <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '62ch' }}>
              Workloads that resolved a provider domain without traversing the gateway. Each one is a
              service to onboard, not an alert to clear.
            </p>
          </div>
          <Badge status={bypass.length ? 'blocked' : 'clean'} tone={bypass.length ? 'blocked' : 'clean'}>
            {bypass.length ? `${count(bypass.length)} to chase` : 'None'}
          </Badge>
        </div>

        <div className="zt-table">
        <div>
        <GridHead columns={COLUMNS} cells={['Time', 'Workload', 'Destination', 'Verdict']} />

        {report.events.length ? (
          report.events.map((e) => (
            <div
              key={e.id}
              style={{
                display: 'grid', gridTemplateColumns: COLUMNS, gap: 12, alignItems: 'center',
                minHeight: 'var(--row-h)', padding: '8px 16px',
                boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
              }}
            >
              <span className="zt-mono-sm" style={{ color: 'var(--text-quiet)' }}>{e.ts}</span>
              <span style={{ font: 'var(--type-body-sm)' }}>{e.workload}</span>
              <span className="zt-mono-sm" style={{ color: 'var(--text-body)' }}>{e.dstDomain}</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <StatusDot state={e.verdict === 'direct_egress' ? 'blocked' : e.verdict === 'blocked_at_boundary' ? 'redacted' : 'clean'} size={6} />
                <span style={{ font: 'var(--type-body-sm)' }}>
                  {e.verdict === 'direct_egress' ? 'Direct egress' : e.verdict === 'blocked_at_boundary' ? 'Refused at boundary' : 'Via ZeroTrace'}
                </span>
              </span>
            </div>
          ))
        ) : (
          <EmptyState icon="shield" title="Nothing bypassed the gateway" description="Every AI-bound flow in this window traversed ZeroTrace." />
        )}
        </div>
        </div>
      </Card>

      <StubNote capability={stub.capability} detail={stub.detail} />
    </div>
  );
}

function DarkStat({ label, value, signal }: { label: string; value: string; signal?: 'blocked' }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span className="zt-eyebrow" style={{ color: 'rgba(242,242,240,0.52)' }}>{label}</span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {signal ? <StatusDot state={signal} size={6} /> : null}
        <span className="zt-nums" style={{ font: 'var(--w-semibold) var(--t-18)/1.2 var(--font-core)', color: 'var(--ink-inverse)' }}>
          {value}
        </span>
      </span>
    </div>
  );
}
