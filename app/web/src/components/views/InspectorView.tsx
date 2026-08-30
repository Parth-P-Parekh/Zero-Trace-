'use client';

import Link from 'next/link';
import { useState } from 'react';
import { Badge, Button, Card, Icon, PayloadView, StatusDot, Tag, Tooltip } from '@/ds';
import { GridHead, SectionLabel } from '@/components/Chrome';
import { classToken, count, legLabel, ms, risk, statusLabel } from '@/lib/format';
import { STAGE_BUDGET_MS, STAGE_LABEL } from '@/lib/types';
import type { PayloadLeg, RequestRecord, Stage } from '@/lib/types';

const FINDING_COLUMNS = '84px minmax(0,1fr) 148px 58px 62px 96px';
const HOT_PATH: Stage[] = ['S0', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6'];

export function InspectorView({
  request,
  payloads,
}: {
  request: RequestRecord;
  payloads: PayloadLeg[];
}) {
  const [leg, setLeg] = useState<'outbound' | 'inbound'>('outbound');
  const shown = payloads.find((p) => p.leg === leg) ?? payloads[0];
  const legsPresent = payloads.map((p) => p.leg);
  const classes = request.findings.map((f) => f.entityClass);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 'var(--page-max)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Link href="/traffic" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, textDecoration: 'none', color: 'var(--text-quiet)' }}>
          {/* The working icon set has no chevron-left; this is the same glyph, turned. */}
          <span style={{ display: 'inline-flex', transform: 'rotate(180deg)' }}>
            <Icon name="chevron-right" size={14} />
          </span>
          <span style={{ font: 'var(--type-body-sm)' }}>Traffic</span>
        </Link>
        <span style={{ color: 'var(--text-faint)' }}>·</span>
        <span className="zt-mono-sm" style={{ color: 'var(--text-body)' }}>{request.id}</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 24, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ font: 'var(--type-h2)', letterSpacing: 'var(--tr-heading)', margin: 0, maxWidth: '30ch' }}>
            {request.status === 'blocked'
              ? 'Blocked before dispatch'
              : request.status === 'clean'
                ? 'Clean. Nothing redacted.'
                : `${count(request.findings.length)} values redacted, dispatched`}
          </h1>
          <p style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)', margin: '8px 0 0' }}>
            {[
              request.workload,
              // A service account's label is often its workload name. Saying it twice
              // reads as a bug rather than as detail.
              request.actor.unregistered
                ? 'unregistered workload'
                : request.actor.label === request.workload
                  ? null
                  : request.actor.label,
              request.ts,
            ].filter(Boolean).join(' · ')}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {request.degraded ? (
            <Badge status="info" tone="info">{request.degraded} failed open</Badge>
          ) : null}
          <Badge status={request.status} tone={request.status}>{statusLabel(request.status)}</Badge>
        </div>
      </div>

      {/* The payload is the focal object on this screen, so it is the dark card. */}
      {shown ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {legsPresent.length > 1 ? (
            <div style={{ display: 'flex', gap: 6 }}>
              {payloads.map((p) => (
                <button
                  key={p.leg}
                  onClick={() => setLeg(p.leg)}
                  style={{
                    font: 'var(--type-label)', padding: '6px 12px', borderRadius: 'var(--r-pill)',
                    border: '1px solid', cursor: 'pointer',
                    borderColor: leg === p.leg ? 'var(--ink)' : 'var(--border-line)',
                    background: leg === p.leg ? 'var(--ink)' : 'transparent',
                    color: leg === p.leg ? 'var(--ink-inverse)' : 'var(--text-body)',
                    transition: 'var(--t-hover)',
                  }}
                >
                  {legLabel(p.leg)} leg
                </button>
              ))}
            </div>
          ) : null}
          <PayloadView
            id={request.ledgerId}
            method={shown.method}
            path={shown.path}
            model={shown.model}
            lines={shown.lines as never}
            status={shown.status}
            latency={shown.latency}
          />
        </div>
      ) : null}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,2fr) minmax(0,1fr)', gap: 12, alignItems: 'start' }}>
        <Card pad={0}>
          <div style={{ padding: '16px 16px 12px' }}>
            <SectionLabel>Findings</SectionLabel>
            <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '58ch' }}>
              Span paths, classes and offsets. The original values are not stored and are not
              recoverable from this record.
            </p>
          </div>
          <GridHead
            columns={FINDING_COLUMNS}
            cells={['Leg', 'Span path', 'Class', 'Conf.', 'Stage', 'Action']}
          />
          {request.findings.length === 0 ? (
            <div style={{ padding: '20px 16px', font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>
              Nothing matched. The payload dispatched unmodified.
            </div>
          ) : (
            request.findings.map((f) => (
              <div
                key={f.id}
                style={{
                  display: 'grid', gridTemplateColumns: FINDING_COLUMNS, gap: 12, alignItems: 'center',
                  minHeight: 'var(--row-h)', padding: '8px 16px',
                  boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
                }}
              >
                <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>{legLabel(f.leg)}</span>
                <Tooltip label={f.spanPath} mono>
                  <span
                    className="zt-mono-sm"
                    style={{ color: 'var(--text-body)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}
                  >
                    {f.spanPath}
                  </span>
                </Tooltip>
                <span><Tag mono>{classToken(f.entityClass)}</Tag></span>
                <span className="zt-mono-sm zt-nums" style={{ color: 'var(--text-quiet)' }}>{f.confidence.toFixed(2)}</span>
                <Tooltip label={STAGE_LABEL[f.stage]}>
                  <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>{f.stage}</span>
                </Tooltip>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <StatusDot state={f.action === 'block' ? 'blocked' : f.action === 'allow' ? 'clean' : 'redacted'} size={6} />
                  <span style={{ font: 'var(--type-body-sm)' }}>
                    {f.action === 'tokenize' ? 'Tokenized' : f.action === 'mask' ? 'Masked' : f.action === 'block' ? 'Blocked' : 'Allowed'}
                  </span>
                </span>
              </div>
            ))
          )}
        </Card>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Card pad={20}>
            <SectionLabel>Decision</SectionLabel>
            <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '10px 16px', font: 'var(--type-body-sm)' }}>
              <Row label="Policy">
                <span className="zt-mono-sm">v{request.policyVersion}</span>
                {request.ruleFired !== undefined ? (
                  <span style={{ color: 'var(--text-quiet)' }}> · rule {request.ruleFired}</span>
                ) : null}
              </Row>
              <Row label="Mode"><span>{request.mode === 'enforce' ? 'Enforce' : 'Shadow'}</span></Row>
              <Row label="Composite risk">
                <span className="zt-mono-sm zt-nums">{risk(request.compositeRisk)}</span>
                {(request.compositeRisk ?? 0) > 0.6 ? (
                  <span style={{ color: 'var(--text-quiet)' }}> · over threshold</span>
                ) : null}
              </Row>
              <Row label="Escalated"><span>{request.escalated ? 'Yes, to the adjudicator' : 'No'}</span></Row>
              <Row label="Ledger"><span className="zt-mono-sm">{request.ledgerId}</span></Row>
            </dl>
            {classes.length ? (
              <p style={{ margin: '16px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>
                Tokens are derived one way. There is no operation in this system that returns an
                original value.
              </p>
            ) : null}
          </Card>

          <Card pad={20}>
            <SectionLabel>Latency by stage</SectionLabel>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {HOT_PATH.map((s) => {
                const spent = request.latencyByStage[s] ?? 0;
                const budget = STAGE_BUDGET_MS[s as keyof typeof STAGE_BUDGET_MS];
                const pct = Math.min(1, spent / budget);
                const over = spent >= budget;
                return (
                  <div key={s} style={{ display: 'grid', gridTemplateColumns: '28px 1fr 56px', gap: 10, alignItems: 'center' }}>
                    <Tooltip label={STAGE_LABEL[s]}>
                      <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>{s}</span>
                    </Tooltip>
                    <span style={{ height: 4, background: 'rgba(17,17,17,0.11)', borderRadius: 'var(--r-pill)', overflow: 'hidden' }}>
                      <span
                        style={{
                          display: 'block', height: '100%', width: `${pct * 100}%`,
                          background: over ? 'var(--signal-info)' : 'rgba(17,17,17,0.52)',
                        }}
                      />
                    </span>
                    <span className="zt-mono-sm zt-nums" style={{ color: over ? 'var(--signal-info)' : 'var(--text-quiet)', textAlign: 'right' }}>
                      {spent ? ms(spent) : '-'}
                    </span>
                  </div>
                );
              })}
            </div>
            <p style={{ margin: '14px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>
              {request.degraded
                ? `${request.degraded} hit its budget and failed open. The result above is incomplete and the record says so.`
                : `Total ${ms(request.latencyMs)}, inside the p95 budget of 65 ms across both legs.`}
            </p>
          </Card>

          <Card pad={20}>
            <SectionLabel>False positive</SectionLabel>
            <p style={{ margin: '0 0 14px', font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>
              Raising one drafts a scoped exception and routes it to an approver. The person who
              raises it cannot approve it.
            </p>
            <Button variant="secondary" size="sm" icon="x" full>
              Raise a false positive
            </Button>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <dt style={{ color: 'var(--text-quiet)' }}>{label}</dt>
      <dd style={{ margin: 0, textAlign: 'right' }}>{children}</dd>
    </>
  );
}
