'use client';

import { Badge, Button, Card, Icon, Metric, StatusDot, Tooltip } from '@/ds';
import { PageHead, SectionLabel, StubNote } from '@/components/Chrome';
import { compact, exact, percent } from '@/lib/format';
import type { Licence, StubNotice } from '@/lib/types';

export function LicenceView({ licence, stub }: { licence: Licence; stub: StubNotice }) {
  const used = licence.tokensUsed / licence.licensedTokens;
  const peak = Math.max(...licence.usage.map((d) => d.tokensOut + d.tokensIn));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 'var(--page-max)' }}>
      <PageHead
        title="Licensed by business unit, metered on both legs"
        sub="Prompt tokens on the way out and completion tokens on the way back are each scanned, and each counts."
        right={
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <Badge status="clean" tone="clean">{licence.tierLabel}</Badge>
            <Button size="sm" icon="external-link">Issue a payment link</Button>
          </div>
        }
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.2fr)', gap: 12, alignItems: 'stretch' }}>
        {/* Usage against the licensed volume is the number that decides the invoice. */}
        <Card tone="dark" pad={28}>
          <SectionLabel onDark>Tokens scanned this period</SectionLabel>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
            <span
              className="zt-nums"
              style={{
                font: 'var(--w-semibold) var(--t-54)/var(--lh-tight) var(--font-core)',
                letterSpacing: 'var(--tr-display)', color: 'var(--ink-inverse)',
              }}
            >
              {compact(licence.tokensUsed)}
            </span>
            <span className="zt-mono-sm" style={{ color: 'var(--text-on-dark-quiet)' }}>
              of {compact(licence.licensedTokens)}
            </span>
          </div>

          <div style={{ marginTop: 20, height: 6, background: 'rgba(242,242,240,0.11)', borderRadius: 'var(--r-pill)', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${used * 100}%`, background: 'rgba(242,242,240,0.72)' }} />
          </div>
          <p style={{ margin: '12px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)', maxWidth: '46ch' }}>
            {percent(used)} of the licensed volume across {licence.businessUnits} business units.
            Above it, overage is invoiced as an add-on rather than enforced as a cut-off — a firewall
            that stops inspecting when the meter runs out is not a firewall.
          </p>

          <div style={{ display: 'flex', gap: 24, marginTop: 24, paddingTop: 20, boxShadow: 'inset 0 1px 0 var(--border-on-dark)' }}>
            <div>
              <div className="zt-eyebrow" style={{ color: 'rgba(242,242,240,0.52)' }}>Outbound</div>
              <div className="zt-nums" style={{ font: 'var(--w-semibold) var(--t-18)/1.2 var(--font-core)', color: 'var(--ink-inverse)', marginTop: 4 }}>
                {compact(licence.usage.reduce((n, d) => n + d.tokensOut, 0))}
              </div>
            </div>
            <div>
              <div className="zt-eyebrow" style={{ color: 'rgba(242,242,240,0.52)' }}>Inbound</div>
              <div className="zt-nums" style={{ font: 'var(--w-semibold) var(--t-18)/1.2 var(--font-core)', color: 'var(--ink-inverse)', marginTop: 4 }}>
                {compact(licence.usage.reduce((n, d) => n + d.tokensIn, 0))}
              </div>
            </div>
            <div>
              <div className="zt-eyebrow" style={{ color: 'rgba(242,242,240,0.52)' }}>Leaks prevented</div>
              <div className="zt-nums" style={{ font: 'var(--w-semibold) var(--t-18)/1.2 var(--font-core)', color: 'var(--ink-inverse)', marginTop: 4 }}>
                {exact(licence.usage.reduce((n, d) => n + d.leaksPrevented, 0))}
              </div>
            </div>
          </div>
        </Card>

        <Card pad={24}>
          <SectionLabel>Scanned by day, both legs</SectionLabel>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, height: 148, marginTop: 8 }}>
            {licence.usage.map((d) => {
              const total = d.tokensOut + d.tokensIn;
              const h = (total / peak) * 100;
              const outShare = d.tokensOut / total;
              return (
                <Tooltip key={d.day} label={`${d.day}: ${compact(d.tokensOut)} out, ${compact(d.tokensIn)} in`}>
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                    <div
                      style={{
                        width: '100%', height: `${h}%`, minHeight: 4, display: 'flex',
                        flexDirection: 'column', justifyContent: 'flex-end',
                        borderRadius: 'var(--r-4)', overflow: 'hidden',
                      }}
                    >
                      <div style={{ height: `${outShare * 100}%`, background: 'rgba(17,17,17,0.52)' }} />
                      <div style={{ height: `${(1 - outShare) * 100}%`, background: 'rgba(17,17,17,0.22)' }} />
                    </div>
                    <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>{d.day}</span>
                  </div>
                </Tooltip>
              );
            })}
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 16 }}>
            <LegendKey tone="rgba(17,17,17,0.52)" label="Outbound" />
            <LegendKey tone="rgba(17,17,17,0.22)" label="Inbound" />
          </div>
        </Card>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,minmax(0,1fr))', gap: 12 }}>
        <Card pad={24}>
          <SectionLabel>Signed usage counter</SectionLabel>
          <p style={{ margin: '0 0 16px', font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '52ch' }}>
            Counts and hashes only, written to disk before it is transmitted, so it can be read
            before it leaves. Billing telemetry from a security product must not become a second
            egress channel.
          </p>
          <dl
            className="zt-mono-sm"
            style={{ margin: 0, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '8px 16px' }}
          >
            <dt style={{ color: 'var(--text-quiet)' }}>day</dt>
            <dd style={{ margin: 0, textAlign: 'right' }}>{licence.signedCounter.day}</dd>
            <dt style={{ color: 'var(--text-quiet)' }}>tokens_out</dt>
            <dd style={{ margin: 0, textAlign: 'right' }} className="zt-nums">{exact(licence.signedCounter.tokensOut)}</dd>
            <dt style={{ color: 'var(--text-quiet)' }}>tokens_in</dt>
            <dd style={{ margin: 0, textAlign: 'right' }} className="zt-nums">{exact(licence.signedCounter.tokensIn)}</dd>
            <dt style={{ color: 'var(--text-quiet)' }}>ledger_head</dt>
            <dd style={{ margin: 0, textAlign: 'right' }}>{licence.signedCounter.ledgerHead}</dd>
            <dt style={{ color: 'var(--text-quiet)' }}>sig</dt>
            <dd style={{ margin: 0, textAlign: 'right' }}>{licence.signedCounter.signature}</dd>
          </dl>
          <div style={{ marginTop: 16 }}>
            <Button variant="secondary" size="sm" icon="file-text" full>Read the counter before it sends</Button>
          </div>
        </Card>

        <Card pad={24}>
          <SectionLabel>Licence</SectionLabel>
          <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '10px 16px', font: 'var(--type-body-sm)' }}>
            <dt style={{ color: 'var(--text-quiet)' }}>Tier</dt>
            <dd style={{ margin: 0, textAlign: 'right' }}>{licence.tierLabel}</dd>
            <dt style={{ color: 'var(--text-quiet)' }}>Business units</dt>
            <dd style={{ margin: 0, textAlign: 'right' }} className="zt-nums">{licence.businessUnits}</dd>
            <dt style={{ color: 'var(--text-quiet)' }}>Mode</dt>
            <dd style={{ margin: 0, textAlign: 'right', display: 'flex', gap: 6, justifyContent: 'flex-end', alignItems: 'center' }}>
              <StatusDot state="clean" size={6} />
              {licence.mode === 'enforce' ? 'Enforce, org-wide' : 'Shadow'}
            </dd>
            <dt style={{ color: 'var(--text-quiet)' }}>Renews</dt>
            <dd style={{ margin: 0, textAlign: 'right' }} className="zt-mono-sm">{licence.periodEnd}</dd>
          </dl>
          <p style={{ margin: '16px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '52ch' }}>
            Paying the invoice flips every business unit under the licence from shadow to enforce in
            one event, and the event lands in the ledger.
          </p>
        </Card>
      </div>

      <StubNote capability={stub.capability} detail={stub.detail} />
    </div>
  );
}

function LegendKey({ tone, label }: { tone: string; label: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span style={{ width: 10, height: 4, borderRadius: 'var(--r-pill)', background: tone }} />
      <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>{label}</span>
    </span>
  );
}
