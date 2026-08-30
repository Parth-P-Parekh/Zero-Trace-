'use client';

/**
 * Detectors - can the matching be trusted?
 *
 * A detector registry that lists rules and their patterns answers "what do we
 * have". The question an operator actually has is "what does it miss", and that is
 * only answerable against a corpus where the answer was known in advance. This
 * screen is that answer: nineteen classes, planted a known number of times, and
 * the rate at which each one came back.
 *
 * The dark card is spent on the evasion matrix, because it carries the single most
 * consequential thing the run found - a credential broken up with spaces walks past
 * the scanner about nineteen times in twenty. Everything else on the page is quiet
 * so that one block can be loud.
 *
 * Rows are ordered weakest recall first. An alphabetical registry buries the row
 * that needs a decision behind eighteen that do not.
 */
import { useMemo, useState } from 'react';
import { Badge, Card, EmptyState, Input, SegmentedControl, Tag, Tooltip } from '@/ds';
import { BarSeries, EvasionMatrix, Meter } from '@/components/console/Draw';
import { Caveat, Column, Figure, Headline, Pair, Panel, Provenance, TableHead, columns } from '@/components/console/Frame';
import { run, weakestDetectors, type DetectorRow } from '@/lib/benchmark';
import { classToken, compact, exact, micros, percent, score } from '@/lib/format';

const COLS: Column[] = [
  { key: 'class', head: 'Entity class', w: 'minmax(0,1.2fr)' },
  { key: 'planted', head: 'Planted', w: '84px', align: 'right' },
  { key: 'recall', head: 'Recall', w: '116px' },
  { key: 'precision', head: 'Precision', w: '116px' },
  { key: 'fp', head: 'False pos.', w: '82px', align: 'right' },
  { key: 'runtime', head: 'Runtime', w: '78px', align: 'right' },
  { key: 'status', head: 'Status', w: '104px' },
];

export function DetectorsView() {
  const [sort, setSort] = useState('weakest');
  const [q, setQ] = useState('');

  const rows = useMemo(() => {
    const list = [...run.detectors].filter((d) =>
      !q || d.entityClass.toLowerCase().includes(q.toLowerCase()));
    if (sort === 'noisiest') {
      return list.sort((a, b) => (a.precision ?? 1) - (b.precision ?? 1));
    }
    if (sort === 'volume') return list.sort((a, b) => b.observed - a.observed);
    if (sort === 'slowest') return list.sort((a, b) => (b.runtimeUs ?? 0) - (a.runtimeUs ?? 0));
    return list.sort((a, b) => (a.recall ?? 2) - (b.recall ?? 2));
  }, [sort, q]);

  const clean = run.detectors.filter((d) => d.recall === 1 && d.precision === 1).length;
  const worst = run.evasion[0];
  const weak = weakestDetectors(4);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 'var(--page-max)' }}>
      <Headline
        sub={`Nineteen entity classes were planted a known number of times across five
              million payloads, so recall is counted rather than estimated. Precision is
              measured only against the payloads generated with nothing in them - the one
              place a finding has no defence.`}
      >
        <Figure>{clean}</Figure> of <Figure>{run.detectors.length}</Figure> classes came back
        exact. The rest are named below.
      </Headline>

      {/* -- the signature: what gets past ------------------------------------- */}
      <Card tone="dark" pad={26}>
        <Panel
          title="Evasion"
          onDark
          note="The same credentials, rewritten the way people actually paste them. Each cell is the share the detector still caught."
        >
          <EvasionMatrix rows={run.evasion} />
          <p
            style={{
              margin: '22px 0 0', maxWidth: '68ch', font: 'var(--type-body-sm)',
              color: 'var(--text-on-dark-body)',
            }}
          >
            Line wrapping and base64 are handled - the obfuscation and encoding scanners
            were built for them and they hold at 100%. Spacing is not:{' '}
            <span style={{ color: 'var(--ink-inverse)' }}>
              a key broken every six characters was caught {percent(worst.detectionRate, 1)} of
              the time
            </span>
            , and zero-width padding only slightly better. Both are one line of code for
            anyone trying, and neither is exotic - a form that truncates long values
            produces the first by accident.
          </p>
        </Panel>
      </Card>

      {/* -- the two failure shapes, side by side -------------------------------- */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: 20 }}>
        <Card pad={22}>
          <Panel title="What it misses" note="Recall below 1.0. Every one of these is at 1.0 on a plain value and drops only when the value is obfuscated.">
            <BarSeries
              rows={weak.map((d) => ({
                label: classToken(d.entityClass),
                value: d.missed,
                note: `${percent(d.recall ?? 0, 1)} recall`,
                mono: true,
              }))}
              format={exact}
            />
          </Panel>
        </Card>

        <Card pad={22}>
          <Panel title="What it over-claims" note="Enforceable findings raised on payloads generated with no leak in them.">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              <Meter
                value={run.integrity.false_positive_rate}
                label="False-positive rate, all classes"
                caption={`${exact(run.integrity.quiet_false_positive_records)} of ${exact(run.integrity.quiet_records)} clean payloads raised something`}
                invert
              />
              <BarSeries
                rows={run.detectors
                  .filter((d) => d.falsePositives > 0)
                  .sort((a, b) => b.falsePositives - a.falsePositives)
                  .map((d) => ({
                    label: classToken(d.entityClass),
                    value: d.falsePositives,
                    note: `${percent(d.precision ?? 1, 1)} precision`,
                    mono: true,
                  }))}
                format={exact}
              />
            </div>
          </Panel>
        </Card>
      </div>

      <Caveat>
        <strong style={{ fontWeight: 'var(--w-medium)', color: 'var(--text-body)' }}>
          Aadhaar precision is arithmetic, not a bug.
        </strong>{' '}
        A Verhoeff check digit rejects nine in ten random twelve-digit strings and accepts
        the tenth, so a corpus of twelve-digit order numbers produces one apparent Aadhaar
        per ten by construction. That is why the checksum is a filter and the co-occurrence
        scanner is the decision - and why{' '}
        <span className="zt-mono-sm">quasi_identifier_set</span> carries the record cases at
        1.00 precision instead.
      </Caveat>

      {/* -- the registry -------------------------------------------------------- */}
      <Card pad={0}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '16px 16px 14px', flexWrap: 'wrap' }}>
          <SegmentedControl
            size="sm"
            value={sort}
            onChange={setSort}
            style={{ flex: 1 }}
            items={[
              { value: 'weakest', label: 'Weakest recall' },
              { value: 'noisiest', label: 'Noisiest' },
              { value: 'volume', label: 'Most seen' },
              { value: 'slowest', label: 'Slowest' },
            ]}
          />
          <Input
            size="sm"
            icon="search"
            placeholder="Filter classes"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ width: 200, paddingBottom: 10 }}
          />
        </div>

        <div className="zt-table">
          <div>
            <TableHead cols={COLS} />
            {rows.length ? rows.map((d) => <DetectorLine key={d.entityClass} row={d} />) : (
              <EmptyState icon="search" title="No class matches" description="Clear the filter." />
            )}
          </div>
        </div>
      </Card>

      <Provenance scope="Detector quality" />
    </div>
  );
}

function DetectorLine({ row }: { row: DetectorRow }) {
  const exactBoth = row.recall === 1 && row.precision === 1;
  return (
    <div
      className="zt-row"
      style={{
        display: 'grid', gridTemplateColumns: columns(COLS), gap: 12, alignItems: 'center',
        minHeight: 'var(--row-h)', padding: '10px 16px',
        boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
      }}
    >
      <span style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span className="zt-mono-sm" style={{ color: 'var(--text-body)' }}>
          {classToken(row.entityClass)}
        </span>
        <span className="zt-mono-sm" style={{ color: 'var(--text-faint)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {row.detectors.length ? row.detectors.join(' · ') : 'composed scanner'}
        </span>
      </span>

      <span className="zt-mono-sm zt-nums" style={{ textAlign: 'right', color: 'var(--text-quiet)' }}>
        {compact(row.expected)}
      </span>

      <ScoreCell value={row.recall} />
      <ScoreCell value={row.precision} />

      <span
        className="zt-mono-sm zt-nums"
        style={{ textAlign: 'right', color: row.falsePositives ? 'var(--ink)' : 'var(--text-faint)' }}
      >
        {row.falsePositives ? exact(row.falsePositives) : '-'}
      </span>

      <span className="zt-mono-sm zt-nums" style={{ textAlign: 'right', color: 'var(--text-quiet)' }}>
        {row.runtimeUs === null ? (
          <Tooltip label="Composed of several scanners; no isolated cost">
            <span>-</span>
          </Tooltip>
        ) : micros(row.runtimeUs)}
      </span>

      <span>
        {exactBoth ? (
          <Badge status="clean" tone="clean">Exact</Badge>
        ) : (row.recall ?? 1) < 1 ? (
          <Badge status="redacted" tone="redacted">Misses</Badge>
        ) : (
          <Badge status="info" tone="info">Over-claims</Badge>
        )}
      </span>
    </div>
  );
}

/**
 * A score with a short rule under it.
 *
 * The rule is 44px and not the column width. Stretched across the cell it read as
 * an input underline - a column of them looked like a form, which is exactly the
 * "invented affordance" failure that makes an operator distrust a table.
 */
function ScoreCell({ value }: { value: number | null }) {
  if (value === null) {
    return <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>not measured</span>;
  }
  const perfect = value === 1;
  return (
    <span style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
      <span className="zt-mono-sm zt-nums" style={{ color: perfect ? 'var(--text-quiet)' : 'var(--ink)' }}>
        {score(value)}
      </span>
      <span
        aria-hidden
        style={{ width: 44, height: 2, background: 'rgba(17,17,17,0.11)', borderRadius: 1 }}
      >
        <span
          style={{
            display: 'block', height: '100%',
            // Below 0.8 the bar would be a sliver at 44px, so the scale starts there:
            // every score in this table is between 0.75 and 1, and a full-range bar
            // would make a 0.888 and a 0.9999 look identical.
            width: `${Math.max(0, (value - 0.8) / 0.2) * 100}%`,
            background: perfect ? 'rgba(17,17,17,0.22)' : 'rgba(17,17,17,0.72)',
            borderRadius: 1,
          }}
        />
      </span>
    </span>
  );
}
