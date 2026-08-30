'use client';

/**
 * Policy - did the rules hold?
 *
 * The old screen showed a YAML document and its version history, which describes
 * what policy *says*. After a five-million-record run there is a better question
 * available: what policy *did*. So the rules are shown beside the number of times
 * each one fired and the one case where it did not hold.
 *
 * The dark card is spent on the credential block rate, because credentials are the
 * one class the product promises zero tolerance on - and the run found 41,329
 * payloads where that promise was not kept. Putting that on the dark card rather
 * than in a footnote is the whole editorial position of this console.
 */
import { useState } from 'react';
import { Badge, Card, SegmentedControl } from '@/ds';
import { BarSeries, RatioBar } from '@/components/console/Draw';
import { Caveat, Column, Figure, Headline, Pair, Panel, Provenance, TableHead, columns } from '@/components/console/Frame';
import { run } from '@/lib/benchmark';
import { classToken, compact, exact, percent } from '@/lib/format';

/**
 * The rules that actually decided this run, transcribed from
 * `gateway/base/policy.py`. Not a YAML document a tenant might publish - the
 * family defaults the pipeline ran with, so the numbers beside them are the
 * numbers these lines produced.
 */
const RULES: Array<{ family: string; action: string; why: string }> = [
  { family: 'CREDENTIAL', action: 'block', why: 'Never tokenised. A tokenised key is still a key-shaped string in someone else’s logs.' },
  { family: 'INDIA_ID', action: 'tokenize', why: 'Referentially stable, one-way. The same value derives the same token across hops.' },
  { family: 'FINANCIAL', action: 'tokenize', why: 'Same derivation, same scope.' },
  { family: 'CONTACT', action: 'tokenize', why: 'Kept parseable where the far side validates the shape.' },
  { family: 'PERSON_DATA', action: 'tokenize', why: 'Needs the S2 entity model to fire. Not built.' },
  { family: 'SENSITIVE_CATEGORY', action: 'mask', why: 'Inbound clearance decides this per group, not per family.' },
  { family: 'COMPOSITE', action: 'tokenize', why: 'The set identifies the person even where no single field does.' },
  { family: 'LOW_CONFIDENCE', action: 'warn', why: 'Corroborates. Never enforces alone.' },
];

const LATTICE = ['allow', 'warn', 'tokenize', 'mask', 'block'];

const COLS: Column[] = [
  { key: 'family', head: 'Family', w: 'minmax(0,150px)' },
  { key: 'action', head: 'Action', w: '104px' },
  { key: 'why', head: 'Why', w: 'minmax(0,1fr)' },
  { key: 'fired', head: 'Findings', w: '92px', align: 'right' },
];

export function PolicyView() {
  const [mode, setMode] = useState('applied');
  const { integrity, outcomes, actions, verdicts, collisions } = run;
  const familyCounts = Object.fromEntries(run.byFamily.map((f) => [f.family, f.count]));
  const total = run.status.total;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 'var(--page-max)' }}>
      {/* Grid lives in `.zt-split` in globals.css, not inline: an inline
          grid-template-columns beats the media query and the two columns never
          collapsed on a narrow screen. */}
      <div className="zt-split">
        <div>
          <Headline
            sub={`Every payload got a decision and the decision was recorded before anything
                  was dispatched. The lattice below is ordered by how much of the original
                  reaches the far side; a business unit may move a rule up it, never down.`}
          >
            <Figure>{exact(total)}</Figure> decisions, from{' '}
            <Figure>{RULES.length}</Figure> family rules.
          </Headline>

          <div style={{ marginTop: 26 }}>
            <RatioBar
              segments={LATTICE.filter((a) => actions[a]).map((a, i) => ({
                label: a[0].toUpperCase() + a.slice(1),
                value: actions[a] ?? 0,
                stop: [0.22, 0.36, 0.52, 0.72, 1.0][i] ?? 0.11,
              }))}
              total={total}
            />
          </div>
        </div>

        {/* The dark card: the promise, and where it was not kept. */}
        <Card tone="dark" pad={24}>
          <Panel title="Credential enforcement" onDark>
            <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap', marginBottom: 22 }}>
              <Pair
                value={percent(integrity.credential_block_rate, 2)}
                of="of credential payloads stopped"
                onDark
                size={33}
              />
              <Pair
                value={exact(integrity.credential_not_blocked)}
                of="reached the model"
                onDark
              />
            </div>
            {/* No meter here. It drew 96.13% a second time, immediately under the
                96.13% above it - the same number twice is not a second fact. */}
            <p
              style={{
                margin: '22px 0 0', font: 'var(--type-body-sm)',
                color: 'var(--text-on-dark-body)', maxWidth: '52ch',
              }}
            >
              The rule itself never failed: every credential the detector found was blocked,
              and none was ever tokenised. The {exact(integrity.credential_not_blocked)} that
              got through were not found in the first place - all of them obfuscated, and
              all of them on the Detectors screen.
            </p>
          </Panel>
        </Card>
      </div>

      {/* -- the rules, with what they did ---------------------------------------- */}
      <Card pad={0}>
        <div style={{ padding: '18px 20px 14px' }}>
          <Panel
            title="Active rules"
            note="Transcribed from the policy client that decided this run. Findings is the number of detections each family produced, not the number of requests it stopped."
            right={
              <SegmentedControl
                size="sm"
                value={mode}
                onChange={setMode}
                items={[
                  { value: 'applied', label: 'What fired' },
                  { value: 'lattice', label: 'Lattice order' },
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
                  ? LATTICE.indexOf(b.action) - LATTICE.indexOf(a.action)
                  : (familyCounts[b.family] ?? 0) - (familyCounts[a.family] ?? 0))
              .map((r) => (
                <div
                  key={r.family}
                  className="zt-row"
                  style={{
                    display: 'grid', gridTemplateColumns: columns(COLS), gap: 12,
                    alignItems: 'center', minHeight: 'var(--row-h)', padding: '11px 16px',
                    boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
                    opacity: familyCounts[r.family] ? 1 : 0.52,
                  }}
                >
                  <span className="zt-mono-sm">{r.family.toLowerCase()}</span>
                  <span>
                    <Badge
                      status={r.action === 'block' ? 'blocked' : r.action === 'mask' || r.action === 'tokenize' ? 'redacted' : 'info'}
                      tone={r.action === 'block' ? 'blocked' : r.action === 'mask' || r.action === 'tokenize' ? 'redacted' : 'neutral'}
                    >
                      {r.action}
                    </Badge>
                  </span>
                  <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)', minWidth: 0 }}>
                    {r.why}
                  </span>
                  <span className="zt-mono-sm zt-nums" style={{ textAlign: 'right' }}>
                    {familyCounts[r.family] ? compact(familyCounts[r.family]) : '-'}
                  </span>
                </div>
              ))}
          </div>
        </div>
      </Card>

      {/* -- the two things that did not go cleanly -------------------------------- */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(320px,1fr))', gap: 20 }}>
        <Card pad={22}>
          <Panel
            title="Overlapping redactions"
            note="Two enforceable findings claiming the same characters. The planner emits one edit each and the splice refuses the pair."
          >
            <div style={{ display: 'flex', gap: 26, flexWrap: 'wrap', marginBottom: 20 }}>
              <Pair value={percent(collisions.reached_the_splice / total, 2)} of="of all payloads failed here" />
              <Pair value={exact(collisions.reached_the_splice)} of="requests" />
            </div>
            <BarSeries
              rows={Object.entries(collisions.pairs).map(([pair, n]) => ({
                label: pair.split('+').map(classToken).join('  +  '),
                value: n,
                mono: true,
              }))}
              format={compact}
              limit={6}
            />
            <p style={{ margin: '18px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '58ch' }}>
              These fail closed - nothing was dispatched. But the exception is not caught in
              the request path, so the caller gets an untyped 500 instead of a named error,
              and the ledger records no decision for a request that had one.
            </p>
          </Panel>
        </Card>

        <Card pad={22}>
          <Panel
            title="Verdicts"
            note="Amber means the checker was unsure. There is nowhere to escalate to, because the tier that would resolve it is not built."
          >
            <div style={{ display: 'flex', gap: 26, flexWrap: 'wrap', marginBottom: 20 }}>
              <Pair value={exact(verdicts.amber ?? 0)} of="amber, unresolved" />
              <Pair value={exact(run.degraded.amber_no_tier3 ?? 0)} of="marked degraded" />
            </div>
            <RatioBar
              segments={[
                { label: 'Green', value: verdicts.green ?? 0, stop: 0.22 },
                { label: 'Amber', value: verdicts.amber ?? 0, stop: 0.52 },
                { label: 'Red', value: verdicts.red ?? 0, stop: 1.0 },
              ]}
            />
            <p style={{ margin: '18px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '58ch' }}>
              Amber deliberately does not become red. &ldquo;I could not check&rdquo; and
              &ldquo;I checked and I am unsure&rdquo; are different states, and only the
              first is what a fail-closed stance is for. Every amber is reported in{' '}
              <span className="zt-mono-sm">X-ZeroTrace-Degraded</span>.
            </p>
          </Panel>
        </Card>
      </div>

      <Caveat>
        Policy versioning, business-unit inheritance, scoped exceptions and two-person
        approval are implemented in the control plane and were not exercised by this run -
        it decided every payload against one org-level rule set. The version history and
        approvals this screen used to show were fixtures, and they have been removed rather
        than re-styled.
      </Caveat>

      <Provenance scope="Policy" />
    </div>
  );
}
