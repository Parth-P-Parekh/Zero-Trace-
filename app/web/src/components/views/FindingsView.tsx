'use client';

/**
 * Findings - what is actually in the traffic.
 *
 * Traffic counts requests; this counts the things inside them. Six blocks became
 * four: the confidence-band histogram went (it was a chart of an internal threshold,
 * meaningless without knowing the threshold) and the read-only and format-shortfall
 * blocks merged into one, because they are the same idea - things we found and
 * deliberately did not act on.
 *
 * The one block that was added is "how it was caught". It was buried on Traffic as
 * a stage breakdown labelled S0/S1/S2, and named properly it is the clearest
 * explanation of the product on any screen.
 */
import { useState } from 'react';
import { Card, SegmentedControl, Tag, Tooltip } from '@/ds';
import { BarSeries, RatioBar } from '@/components/console/Draw';
import { Caveat, Figure, Footnote, Headline, Pair, Panel, Provenance } from '@/components/console/Frame';
import { enforceableFindings, formatDegradedTotal, run } from '@/lib/benchmark';
import { compact, exact, percent } from '@/lib/format';
import { group, howFound, howFoundLong, place, thing } from '@/lib/words';

export function FindingsView() {
  const [dim, setDim] = useState('thing');
  const { outcomes, byClass, byFamily, byOrigin } = run;
  const real = enforceableFindings();
  const shortfall = formatDegradedTotal();

  const series =
    dim === 'thing'
      ? byClass.map((c) => ({ label: thing(c.entityClass), value: c.count }))
      : dim === 'group'
        ? byFamily.map((f) => ({ label: group(f.family), value: f.count }))
        : Object.entries(byOrigin).map(([o, n]) => ({ label: place(o), value: n }));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 'var(--page-max)' }}>
      <div className="zt-split">
        <div>
          <Headline
            sub="One request can carry several. A single prompt might hold a customer’s PAN,
                 their phone number and an API key all at once, which is three findings and
                 one stopped request."
          >
            <Figure>{exact(outcomes.findings_total)}</Figure> things found.{' '}
            <Figure>{exact(real)}</Figure> were worth acting on.
          </Headline>

          <div style={{ marginTop: 26 }}>
            <RatioBar
              segments={[
                { label: 'Genuinely sensitive', value: real, stop: 1.0 },
                { label: 'Only looked sensitive', value: outcomes.advisory_findings, stop: 0.22 },
              ]}
            />
          </div>
        </div>

        <Card tone="dark" pad={24}>
          <Panel
            title="Things that only look sensitive"
            onDark
            note="Long random strings that turn up constantly in normal engineering work - version stamps, file checksums, encoded blobs."
          >
            <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap' }}>
              <Pair
                value={percent(outcomes.advisory_findings / outcomes.findings_total, 0)}
                of="of everything found"
                onDark
                size={33}
              />
              <Pair value="0" of="stopped a request" onDark />
            </div>
            <Footnote onDark measure="48ch">
              Nearly a third of everything found falls in here. Blocking on it would stop
              ordinary work several times a day, and a guardrail that does that gets turned
              off in the first week - so these are counted and never acted on alone.
            </Footnote>
          </Panel>
        </Card>
      </div>

      {/* -- how it was caught, which is the product explained ------------------- */}
      <Card pad={22}>
        <Panel
          title="How it was caught"
          note="Three different ways of looking. The third is the one no ordinary scanner does."
        >
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {Object.entries(run.byStage)
              .sort((a, b) => b[1] - a[1])
              .map(([stage, n]) => (
                <div
                  key={stage}
                  style={{
                    display: 'grid', gridTemplateColumns: 'minmax(0,210px) minmax(0,1fr) 92px',
                    gap: 20, alignItems: 'baseline', padding: '15px 0',
                    boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
                  }}
                >
                  <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>
                    {howFound(stage)}
                  </span>
                  <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>
                    {howFoundLong(stage)}
                  </p>
                  <span className="zt-mono-sm zt-nums" style={{ textAlign: 'right' }}>
                    {compact(n)}
                  </span>
                </div>
              ))}
          </div>
        </Panel>
      </Card>

      {/* -- the distribution ---------------------------------------------------- */}
      <Card pad={22}>
        <Panel
          title="What turned up"
          right={
            <SegmentedControl
              size="sm"
              value={dim}
              onChange={setDim}
              items={[
                { value: 'thing', label: 'By type' },
                { value: 'group', label: 'By group' },
                { value: 'origin', label: 'By where it came from' },
              ]}
            />
          }
        >
          <BarSeries rows={series} format={compact} limit={12} />
        </Panel>
      </Card>

      {/* -- found, and deliberately not acted on -------------------------------- */}
      <Card pad={22}>
        <Panel
          title="Found, and left alone on purpose"
          note="Two cases where doing something would have been worse than doing nothing."
        >
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(290px,1fr))', gap: 28 }}>
            <div>
              <Pair
                value={exact(outcomes.readonly_findings_skipped)}
                of="inside a tool’s own description"
              />
              <p style={{ margin: '14px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '46ch' }}>
                An example key in a tool’s documentation is not a leak, and the person
                writing the prompt cannot remove it. Blocking them for it punishes the wrong
                person. Not one of these stopped a request.
              </p>
            </div>
            <div>
              <Pair value={exact(shortfall)} of="replaced with a plain stand-in" />
              <p style={{ margin: '14px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '46ch' }}>
                These were removed and the removal was checked. What they did not get is a
                replacement shaped like the original, so a system on the far side that
                validates a PAN would reject the stand-in.
              </p>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 14 }}>
                {Object.entries(run.degradedFormats).map(([cls, n]) => (
                  <Tooltip key={cls} label={`${exact(n)} values`}>
                    <span><Tag>{thing(cls)}</Tag></span>
                  </Tooltip>
                ))}
              </div>
            </div>
          </div>
        </Panel>
      </Card>

      <Caveat>
        Names, addresses and company names are missing from this list because nothing
        detects them yet - that part is designed and not built, so the test could not
        plant them and this screen does not pretend to have found them. What covers the
        personal-record case instead is the third method above, which reached{' '}
        {exact(run.byClass.find((c) => c.entityClass === 'QUASI_IDENTIFIER_SET')?.count ?? 0)}{' '}
        records by their shape rather than by naming anyone.
      </Caveat>

      <Provenance />
    </div>
  );
}
