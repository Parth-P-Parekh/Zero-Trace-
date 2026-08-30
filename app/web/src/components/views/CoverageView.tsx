'use client';

/**
 * Coverage - is this all of it?
 *
 * The first question a security lead asks, and the one this deployment cannot
 * answer. The dark card carries the absence rather than a number, because a
 * coverage percentage over an unmeasured base is the single most persuasive false
 * claim this product could make.
 *
 * The raw field names that used to sit in that card - `scope: gateway_observed_only`
 * and friends - said the same thing in a form only someone reading the source could
 * check. The sentence says it to everyone.
 */
import { useState } from 'react';
import { Card, SegmentedControl } from '@/ds';
import { BarSeries, RatioBar } from '@/components/console/Draw';
import { Caveat, Figure, Footnote, Headline, Panel, Provenance } from '@/components/console/Frame';
import { run } from '@/lib/benchmark';
import { compact, exact, percent } from '@/lib/format';

const DIMENSIONS: Record<string, { label: string; note: string }> = {
  workload: {
    label: 'App',
    note: 'Which application made the request.',
  },
  harness: {
    label: 'Tool',
    note: 'Which AI tool it came through. “unknown” means we could not name the tool, not that it got around us.',
  },
  channel: {
    label: 'How it connected',
    note: 'A command-line tool writes the AI’s answer to disk, which is why stand-in values are refused there.',
  },
};

/** Job titles, not system roles. */
const ROLE_COPY: Record<string, string> = {
  officer: 'Case officer',
  auditor: 'Auditor',
  director: 'Director',
  contractor: 'Outside contractor',
  support_agent: 'Support agent',
  service: 'An application, not a person',
  unregistered: 'Nobody we recognise',
  engineer: 'Engineer',
};

export function CoverageView() {
  const [dim, setDim] = useState('workload');
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
      <div className="zt-split">
        <div>
          <Headline
            sub="Everything on this dashboard is traffic that came through us. Whether that
                 is all of the organisation’s AI traffic is a separate question, and this
                 setup cannot answer it."
          >
            <Figure>{exact(status.total)}</Figure> requests came through us.
          </Headline>

          <div style={{ marginTop: 26 }}>
            <RatioBar
              segments={Object.entries(coverage.provider).map(([p, n], i) => ({
                label: p === 'anthropic' ? 'Anthropic models' : 'OpenAI models',
                value: n,
                stop: [1.0, 0.52, 0.22][i] ?? 0.11,
              }))}
            />
          </div>
        </div>

        {/* The card carries what is missing, not a percentage. */}
        <Card tone="dark" pad={24}>
          <Panel title="What share of all AI traffic" onDark>
            <div
              style={{
                font: 'var(--w-regular) 33px/1.1 var(--font-core)',
                letterSpacing: 'var(--tr-display)', color: 'rgba(242,242,240,0.36)',
              }}
            >
              We don&rsquo;t know
            </div>
            <p
              style={{
                margin: '20px 0 0', font: 'var(--type-body-sm)',
                color: 'var(--text-on-dark-body)', maxWidth: '48ch',
              }}
            >
              To say &ldquo;we cover 98% of AI traffic&rdquo; you need to know the other 2%
              exists. That means watching the network itself &ndash; which machines called
              an AI provider without coming through us &ndash; and that connection has not
              been built.
            </p>
            <Footnote onDark>
              So this screen shows what we did see, and no percentage. A number here with
              nothing underneath it would be the easiest thing on the dashboard to believe
              and the least true.
            </Footnote>
          </Panel>
        </Card>
      </div>

      {/* -- what did come through ------------------------------------------------ */}
      <Card pad={22}>
        <Panel
          title="Where it came from"
          note={`${DIMENSIONS[dim].note} The counts are close to even because this is test traffic, not a real estate.`}
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
              .map(([label, value]) => ({ label, value }))}
            format={compact}
            limit={12}
          />
        </Panel>
      </Card>

      {/* -- who was sending ------------------------------------------------------ */}
      <Card pad={22}>
        <Panel
          title="Who was sending"
          note="Right now this is taken from a header the caller sets itself, which anyone could fake. Proper sign-in checking is designed and not built."
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
                        display: 'grid', gridTemplateColumns: '200px 80px minmax(0,1fr) 96px',
                        gap: 16, alignItems: 'center', padding: '13px 4px',
                        boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
                      }}
                    >
                      <span
                        style={{
                          font: 'var(--type-body-sm)',
                          color: role === 'unregistered' ? 'var(--signal-redacted)' : 'var(--text-body)',
                        }}
                      >
                        {ROLE_COPY[role] ?? role}
                      </span>
                      <span className="zt-mono-sm zt-nums" style={{ color: 'var(--text-quiet)' }}>
                        {compact(t)}
                      </span>
                      <RatioBar
                        legend={false}
                        height={6}
                        total={t}
                        segments={[
                          { label: 'Sent as-is', value: acts.allow ?? 0, stop: 0.22 },
                          { label: 'Cleaned up', value: acts.tokenize ?? 0, stop: 0.52 },
                          { label: 'Stopped', value: acts.block ?? 0, stop: 1.0 },
                        ]}
                      />
                      <span className="zt-mono-sm zt-nums" style={{ textAlign: 'right' }}>
                        {percent(stopped / t, 0)} touched
                      </span>
                    </div>
                  );
                })}
            </div>
          </div>
        </Panel>
      </Card>

      <Caveat>
        {exact(unknown)} requests came from a tool we could not put a name to. Every one of
        them was still checked and decided like the rest &ndash; it is a labelling gap, not
        a hole. It is worth watching because a share that starts growing usually means a new
        tool has appeared in the organisation.
      </Caveat>

      <Provenance />
    </div>
  );
}
