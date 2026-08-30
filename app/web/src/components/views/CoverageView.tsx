'use client';

/**
 * Coverage - is this all the traffic?
 *
 * The first question a security buyer asks, and the one this product cannot yet
 * answer. The gateway can prove what traversed it; proving the denominator needs
 * DNS, firewall or flow logs, and none are connected. `CoverageMonitor.snapshot()`
 * says so in three fields - `scope: gateway_observed_only`,
 * `direct_egress_visible: false`, `denominator_available: false` - and this screen
 * says the same thing in the same place instead of showing a percentage.
 *
 * So the dark card carries the absence, not a number. A coverage figure with no
 * denominator is the single most persuasive false claim this product could make,
 * and printing "98.7%" over an unmeasured base is how a security team stops
 * believing the rest of the console.
 */
import { useState } from 'react';
import { Card, SegmentedControl, StatusDot, Tag } from '@/ds';
import { BarSeries, RatioBar } from '@/components/console/Draw';
import { Caveat, Figure, Headline, Pair, Panel, Provenance } from '@/components/console/Frame';
import { run } from '@/lib/benchmark';
import { compact, exact, percent } from '@/lib/format';

const DIMENSIONS: Record<string, { label: string; note: string; mono: boolean }> = {
  harness: {
    label: 'Harness',
    note: 'Which tool made the call, from its user agent or an explicit header. “unknown” is a harness the gateway could not name, not a harness that bypassed it.',
    mono: true,
  },
  route: {
    label: 'Route',
    note: 'The provider-compatible endpoint the request arrived on.',
    mono: true,
  },
  channel: {
    label: 'Channel',
    note: 'How the caller reached the gateway. A CLI writes model output to disk, which is why tokenised values are refused there.',
    mono: true,
  },
  workload: {
    label: 'Workload',
    note: 'The application behind the call.',
    mono: false,
  },
};

export function CoverageView() {
  const [dim, setDim] = useState('harness');
  const { coverage, status, byActorRole } = run;
  const table = coverage[dim as keyof typeof coverage] as Record<string, number>;
  const unknown = coverage.harness.unknown ?? 0;

  const roles = Object.entries(byActorRole).reduce<Record<string, Record<string, number>>>(
    (acc, [key, n]) => {
      const [role, action] = key.split(':');
      acc[role] = acc[role] ?? {};
      acc[role][action] = n;
      return acc;
    },
    {},
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 'var(--page-max)' }}>
      {/* Grid lives in `.zt-split` in globals.css, not inline: an inline
          grid-template-columns beats the media query and the two columns never
          collapsed on a narrow screen. */}
      <div className="zt-split">
        <div>
          <Headline
            sub={`Everything below is traffic that reached the gateway. What share of the
                  organisation’s AI traffic that represents is a different number, and this
                  deployment cannot compute it.`}
          >
            <Figure>{exact(status.total)}</Figure> payloads traversed the gateway.
          </Headline>

          <div style={{ marginTop: 26 }}>
            <RatioBar
              segments={Object.entries(coverage.provider).map(([p, n], i) => ({
                label: p,
                value: n,
                stop: [1.0, 0.52, 0.22][i] ?? 0.11,
              }))}
            />
          </div>
        </div>

        {/* The dark card carries what is missing, not a percentage. */}
        <Card tone="dark" pad={24}>
          <Panel title="Coverage ratio" onDark>
            <div
              style={{
                font: 'var(--w-regular) 33px/1.1 var(--font-core)',
                letterSpacing: 'var(--tr-display)', color: 'rgba(242,242,240,0.36)',
              }}
            >
              Not available
            </div>
            <p
              style={{
                margin: '16px 0 0', font: 'var(--type-body-sm)',
                color: 'var(--text-on-dark-body)', maxWidth: '48ch',
              }}
            >
              A coverage percentage is gateway traversals over all AI egress. The numerator
              is known exactly. The denominator needs DNS resolutions, firewall logs or VPC
              flow logs, and no connector is built - so the fraction has no bottom half and
              is not shown.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 24 }}>
              {[
                ['scope', 'gateway_observed_only'],
                ['direct_egress_visible', 'false'],
                ['denominator_available', 'false'],
              ].map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                  <span className="zt-mono-sm" style={{ color: 'rgba(242,242,240,0.36)' }}>{k}</span>
                  <span className="zt-mono-sm" style={{ color: 'var(--text-on-dark-quiet)' }}>{v}</span>
                </div>
              ))}
            </div>
            <p className="zt-mono-sm" style={{ margin: '20px 0 0', color: 'rgba(242,242,240,0.36)' }}>
              GET /v1/coverage
            </p>
          </Panel>
        </Card>
      </div>

      {/* -- what did traverse ---------------------------------------------------- */}
      <Card pad={22}>
        <Panel
          title="Observed traffic"
          // The uniformity is said out loud. These counts are near-identical because
          // the corpus picks a harness at random, and a reader who took the ranking
          // for a real estate profile would be reading an artefact of the generator.
          note={`${DIMENSIONS[dim].note} Counts are close to even because the corpus assigns this attribute at random; the ranking is not a measurement of any real estate.`}
          right={
            <SegmentedControl
              size="sm"
              value={dim}
              onChange={setDim}
              items={Object.entries(DIMENSIONS).map(([value, d]) => ({ value, label: d.label }))}
            />
          }
        >
          <BarSeries
            rows={Object.entries(table)
              .sort((a, b) => b[1] - a[1])
              .map(([label, value]) => ({
                label,
                value,
                mono: DIMENSIONS[dim].mono,
                note: dim === 'harness' && label === 'unknown' ? 'unclassified' : undefined,
              }))}
            format={compact}
            limit={12}
          />
        </Panel>
      </Card>

      {/* -- who was calling ------------------------------------------------------ */}
      <Card pad={22}>
        <Panel
          title="By actor role"
          note="Resolved from the request headers, which are trivially spoofable on this path. Real identity is mTLS and OIDC, and neither is wired."
        >
          <div className="zt-table">
            <div>
              {Object.entries(roles)
                .sort((a, b) =>
                  Object.values(b[1]).reduce((x, y) => x + y, 0)
                  - Object.values(a[1]).reduce((x, y) => x + y, 0))
                .map(([role, acts]) => {
                  const t = Object.values(acts).reduce((x, y) => x + y, 0);
                  const stopped = (acts.block ?? 0) + (acts.tokenize ?? 0) + (acts.mask ?? 0);
                  return (
                    <div
                      key={role}
                      style={{
                        display: 'grid', gridTemplateColumns: '160px 88px minmax(0,1fr) 84px',
                        gap: 16, alignItems: 'center', padding: '12px 4px',
                        boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
                      }}
                    >
                      <span className="zt-mono-sm" style={{ color: role === 'unregistered' ? 'var(--signal-redacted)' : 'var(--text-body)' }}>
                        {role}
                      </span>
                      <span className="zt-mono-sm zt-nums" style={{ color: 'var(--text-quiet)' }}>
                        {compact(t)}
                      </span>
                      <RatioBar
                        legend={false}
                        height={6}
                        total={t}
                        segments={[
                          { label: 'Allowed', value: acts.allow ?? 0, stop: 0.22 },
                          { label: 'Tokenized', value: acts.tokenize ?? 0, stop: 0.52 },
                          { label: 'Blocked', value: acts.block ?? 0, stop: 1.0 },
                        ]}
                      />
                      <span className="zt-mono-sm zt-nums" style={{ textAlign: 'right' }}>
                        {percent(stopped / t, 1)}
                      </span>
                    </div>
                  );
                })}
            </div>
          </div>
        </Panel>
      </Card>

      <Caveat>
        <strong style={{ fontWeight: 'var(--w-medium)', color: 'var(--text-body)' }}>
          {exact(unknown)} payloads arrived from a harness the gateway could not name.
        </strong>{' '}
        That is a labelling gap, not an enforcement gap - every one of them was inspected
        and decided like the rest. It is reported because an unclassified share that grows
        is the first sign a new tool has appeared in the estate.
      </Caveat>

      <Provenance scope="Coverage" />
    </div>
  );
}
