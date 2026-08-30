'use client';

/**
 * Policy - the rules, and whether they held.
 *
 * The green/amber/red verdict panel is gone. It charted an internal confidence state
 * that means nothing without knowing the two thresholds either side of it, and the
 * one consequence a reader actually needs from it - that an uncertain finding is
 * never treated as a certain one - is a sentence, not a chart.
 *
 * What is left is the rules themselves in plain words, the one promise the product
 * makes about credentials, and the one place the machinery broke.
 */
import { useState } from 'react';
import { Badge, Card, SegmentedControl } from '@/ds';
import { BarSeries, RatioBar } from '@/components/console/Draw';
import { Caveat, Column, Figure, Footnote, Headline, Pair, Panel, Provenance, TableHead, columns } from '@/components/console/Frame';
import { run } from '@/lib/benchmark';
import { compact, exact, percent } from '@/lib/format';
import { group, instruction, oneIn, thing } from '@/lib/words';

/**
 * The rules that decided this run, in the order a reader would ask about them.
 * Transcribed from the policy the pipeline actually ran with, so the counts beside
 * them are the counts these lines produced.
 */
const RULES: Array<{ family: string; action: string; why: string }> = [
  { family: 'CREDENTIAL', action: 'block', why: 'A key that has left cannot be un-sent. There is no safe version of sending one.' },
  { family: 'INDIA_ID', action: 'tokenize', why: 'Swapped for a stand-in that is the same every time, so the AI can still follow who is who.' },
  { family: 'FINANCIAL', action: 'tokenize', why: 'The same treatment as ID numbers.' },
  { family: 'CONTACT', action: 'tokenize', why: 'Kept in a form the far side can still read as an email or a phone number.' },
  { family: 'COMPOSITE', action: 'tokenize', why: 'A record that identifies someone even though no single field in it does.' },
  { family: 'SENSITIVE_CATEGORY', action: 'mask', why: 'Who may read these depends on which team they are in, decided per person.' },
  { family: 'PERSON_DATA', action: 'tokenize', why: 'Needs the name-detection model, which is not built yet.' },
  { family: 'LOW_CONFIDENCE', action: 'warn', why: 'Counted as supporting evidence. Never enough on its own.' },
];

const COLS: Column[] = [
  { key: 'group', head: 'Kind of data', w: 'minmax(0,180px)' },
  { key: 'action', head: 'What we do', w: '158px' },
  { key: 'why', head: 'Why', w: 'minmax(0,1fr)' },
  { key: 'count', head: 'Times seen', w: '96px', align: 'right' },
];

export function PolicyView() {
  const [mode, setMode] = useState('applied');
  const { integrity, actions, collisions } = run;
  const counts = Object.fromEntries(run.byFamily.map((f) => [f.family, f.count]));
  const total = run.status.total;
  const strictness = ['allow', 'warn', 'tokenize', 'mask', 'block'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 'var(--page-max)' }}>
      <div className="zt-split">
        <div>
          <Headline
            sub="Eight rules, one per kind of data. A team can make a rule stricter for
                 itself but never looser, and every decision is written down before
                 anything is sent."
          >
            <Figure>{exact(total)}</Figure> requests, each measured against the same rules.
          </Headline>

          <div style={{ marginTop: 26 }}>
            <RatioBar
              segments={strictness.filter((a) => actions[a]).map((a, i) => ({
                label: instruction(a),
                value: actions[a] ?? 0,
                stop: [0.22, 0.36, 0.52, 0.72, 1.0][i] ?? 0.11,
              }))}
              total={total}
            />
          </div>
        </div>

        {/* The promise, and where it was not kept. */}
        <Card tone="dark" pad={24}>
          <Panel title="The one promise" onDark>
            <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap' }}>
              <Pair
                value={percent(integrity.credential_block_rate, 1)}
                of="of requests carrying a key were stopped"
                onDark
                size={33}
              />
              <Pair value={exact(integrity.credential_not_blocked)} of="got through" onDark />
            </div>
            <Footnote onDark measure="50ch">
              The rule never failed. Every key it found was stopped, and no key was ever
              swapped for a stand-in instead. The ones that got through were never found in
              the first place - all of them typed with spaces or padding, and all of them on
              the previous screen.
            </Footnote>
          </Panel>
        </Card>
      </div>

      {/* -- the rules ----------------------------------------------------------- */}
      <Card pad={0}>
        <div style={{ padding: '18px 20px 12px' }}>
          <Panel
            title="The rules"
            right={
              <SegmentedControl
                size="sm"
                value={mode}
                onChange={setMode}
                items={[
                  { value: 'applied', label: 'Most used' },
                  { value: 'lattice', label: 'Strictest first' },
                ]}
              />
            }
          >
            <div />
          </Panel>
        </div>
        <div className="zt-table">
          <div>
            <TableHead cols={COLS} />
            {[...RULES]
              .sort((a, b) =>
                mode === 'lattice'
                  ? strictness.indexOf(b.action) - strictness.indexOf(a.action)
                  : (counts[b.family] ?? 0) - (counts[a.family] ?? 0))
              .map((r) => (
                <div
                  key={r.family}
                  className="zt-row"
                  style={{
                    display: 'grid', gridTemplateColumns: columns(COLS), gap: 12,
                    alignItems: 'center', minHeight: 'var(--row-h)', padding: '12px 16px',
                    boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
                    opacity: counts[r.family] ? 1 : 0.52,
                  }}
                >
                  <span style={{ font: 'var(--type-body-sm)' }}>{group(r.family)}</span>
                  <span>
                    <Badge
                      status={r.action === 'block' ? 'blocked'
                        : r.action === 'mask' || r.action === 'tokenize' ? 'redacted' : 'info'}
                      tone={r.action === 'block' ? 'blocked'
                        : r.action === 'mask' || r.action === 'tokenize' ? 'redacted' : 'neutral'}
                    >
                      {instruction(r.action)}
                    </Badge>
                  </span>
                  <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)', minWidth: 0 }}>
                    {r.why}
                  </span>
                  <span className="zt-mono-sm zt-nums" style={{ textAlign: 'right' }}>
                    {counts[r.family] ? compact(counts[r.family]) : 'never'}
                  </span>
                </div>
              ))}
          </div>
        </div>
      </Card>

      {/* -- the one place the machinery broke ------------------------------------ */}
      <Card pad={22}>
        <Panel
          title="Where it broke"
          note="When two rules both want to change the same characters, the request fails instead of being cleaned up."
        >
          <div style={{ display: 'flex', gap: 30, flexWrap: 'wrap', marginBottom: 22 }}>
            <Pair
              value={oneIn(collisions.reached_the_splice / total)}
              of="requests hit this"
              size={27}
            />
            <Pair value={exact(collisions.reached_the_splice)} of="in this run" size={27} />
          </div>
          <BarSeries
            rows={Object.entries(collisions.pairs).map(([pair, n]) => ({
              label: pair.split('+').map(thing).join('  and  '),
              value: n,
            }))}
            format={compact}
            limit={6}
          />
          <p style={{ margin: '20px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '72ch' }}>
            Nothing leaked - the request is abandoned rather than sent. But the app gets a
            generic server error instead of a clear explanation, and no record of the
            decision is kept, so an auditor looking later sees a gap where a decision
            should be. It is the clearest thing on this dashboard to fix next.
          </p>
        </Panel>
      </Card>

      <Caveat>
        Rule versions, per-team overrides, approvals and time-limited exceptions all exist
        in the product but were not used in this test - it ran every request against one
        set of rules. The version history this screen used to show was invented, so it has
        been removed rather than restyled.
      </Caveat>

      <Provenance />
    </div>
  );
}
