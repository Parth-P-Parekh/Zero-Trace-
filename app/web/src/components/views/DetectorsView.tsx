'use client';

/**
 * Detectors - what it catches, and what gets past it.
 *
 * The old version of this screen was correct and unreadable: `recall`, `precision`,
 * `false positives on quiet`, runtime in microseconds, and nineteen rows of
 * SCREAMING_SNAKE class names. Every one of those is the right word for an engineer
 * and the wrong word for the person who has to decide whether to trust the thing.
 *
 * So the columns say what they mean - we planted this many, it found this share,
 * it cried wolf this many times - and the runtime column is gone entirely, because
 * nobody choosing whether to deploy a guardrail is deciding on 78 microseconds.
 *
 * The evasion grid stays exactly as it was. It is the most important thing on the
 * screen and it was already legible without a glossary.
 */
import { useMemo, useState } from 'react';
import { Badge, Card, EmptyState, Input, SegmentedControl } from '@/ds';
import { BarSeries, EvasionMatrix } from '@/components/console/Draw';
import { Caveat, Column, Figure, Headline, Pair, Panel, Provenance, TableHead, columns } from '@/components/console/Frame';
import { run, type DetectorRow } from '@/lib/benchmark';
import { compact, exact, percent } from '@/lib/format';
import { thing } from '@/lib/words';

const COLS: Column[] = [
  { key: 'thing', head: 'What it looks for', w: 'minmax(0,1.3fr)' },
  { key: 'tested', head: 'Times planted', w: '104px', align: 'right' },
  { key: 'found', head: 'Share it found', w: '132px' },
  { key: 'wrong', head: 'False alarms', w: '110px', align: 'right' },
  { key: 'verdict', head: '', w: '124px' },
];

export function DetectorsView() {
  const [sort, setSort] = useState('weakest');
  const [q, setQ] = useState('');

  const rows = useMemo(() => {
    const list = run.detectors.filter((d) =>
      !q || thing(d.entityClass).toLowerCase().includes(q.toLowerCase()));
    if (sort === 'noisiest') return [...list].sort((a, b) => b.falsePositives - a.falsePositives);
    if (sort === 'volume') return [...list].sort((a, b) => b.observed - a.observed);
    return [...list].sort((a, b) => (a.recall ?? 2) - (b.recall ?? 2));
  }, [sort, q]);

  const perfect = run.detectors.filter((d) => d.recall === 1 && d.precision === 1).length;
  const worst = run.evasion[0];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 'var(--page-max)' }}>
      <Headline
        sub="We hid a known number of keys, ID numbers and personal records in the test
             traffic, then counted how many came back. Nothing here is estimated."
      >
        It found <Figure>{perfect}</Figure> of <Figure>{run.detectors.length}</Figure> kinds
        of sensitive data every single time.
      </Headline>

      {/* -- the signature: what gets past ------------------------------------- */}
      <Card tone="dark" pad={26}>
        <Panel
          title="Ways around it"
          onDark
          note="The same keys, retyped the way people actually paste them. Each block is how often it still caught them."
        >
          <EvasionMatrix rows={run.evasion} />
          <p
            style={{
              margin: '22px 0 0', maxWidth: '66ch', font: 'var(--type-body-sm)',
              color: 'var(--text-on-dark-body)',
            }}
          >
            Keys split across lines, or scrambled the way a config file stores them, are
            caught every time. Keys typed with spaces in them are not:{' '}
            <span style={{ color: 'var(--ink-inverse)' }}>
              a key broken up every few characters slipped through{' '}
              {percent(1 - worst.detectionRate, 0)} of the time
            </span>
            . That is not an exotic attack - a form that cuts off long values produces it
            by accident.
          </p>
        </Panel>
      </Card>

      {/* -- the two ways it can be wrong, in one block ------------------------- */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(320px,1fr))', gap: 20 }}>
        <Card pad={22}>
          <Panel
            title="What it missed"
            note="Every one of these is caught every time when the value is typed normally. They only slip when the value is broken up."
          >
            <BarSeries
              rows={run.detectors
                .filter((d) => d.recall !== null && d.recall < 1)
                .slice(0, 5)
                .map((d) => ({
                  label: thing(d.entityClass),
                  value: d.missed,
                  note: `missed ${percent(1 - (d.recall ?? 1), 1)}`,
                }))}
              format={exact}
            />
          </Panel>
        </Card>

        <Card pad={22}>
          <Panel
            title="When it cried wolf"
            note="Alerts raised on test traffic that had nothing sensitive in it at all."
          >
            <div style={{ marginBottom: 18 }}>
              <Pair
                value={percent(run.integrity.false_positive_rate, 1)}
                of={`of clean requests raised something - ${exact(run.integrity.quiet_false_positive_records)} of ${exact(run.integrity.quiet_records)}`}
                size={27}
              />
            </div>
            <BarSeries
              rows={run.detectors
                .filter((d) => d.falsePositives > 0)
                .sort((a, b) => b.falsePositives - a.falsePositives)
                .map((d) => ({ label: thing(d.entityClass), value: d.falsePositives }))}
              format={exact}
            />
          </Panel>
        </Card>
      </div>

      <Caveat>
        Almost all the false alarms are Aadhaar numbers, and that is arithmetic rather
        than a fault. An Aadhaar has a built-in check digit that roughly one in ten
        random twelve-digit numbers passes by chance - so a batch of order numbers
        produces false matches no matter how good the rule is. It is why a twelve-digit
        number on its own is only ever a hint, and why the check that actually decides
        is the one that reads what surrounds it.
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
              { value: 'weakest', label: 'Missed most' },
              { value: 'noisiest', label: 'Most false alarms' },
              { value: 'volume', label: 'Seen most' },
            ]}
          />
          <Input
            size="sm"
            icon="search"
            placeholder="Filter"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ width: 190, paddingBottom: 10 }}
          />
        </div>

        <div className="zt-table">
          <div>
            <TableHead cols={COLS} />
            {rows.length ? rows.map((d) => <DetectorLine key={d.entityClass} row={d} />) : (
              <EmptyState icon="search" title="Nothing matches" description="Clear the filter." />
            )}
          </div>
        </div>
      </Card>

      <Provenance />
    </div>
  );
}

function DetectorLine({ row }: { row: DetectorRow }) {
  const flawless = row.recall === 1 && row.precision === 1;
  return (
    <div
      className="zt-row"
      style={{
        display: 'grid', gridTemplateColumns: columns(COLS), gap: 12, alignItems: 'center',
        minHeight: 'var(--row-h)', padding: '11px 16px',
        boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
      }}
    >
      <span style={{ font: 'var(--type-body-sm)', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {thing(row.entityClass)}
      </span>

      <span className="zt-mono-sm zt-nums" style={{ textAlign: 'right', color: 'var(--text-quiet)' }}>
        {compact(row.expected)}
      </span>

      <ScoreCell value={row.recall} />

      <span
        className="zt-mono-sm zt-nums"
        style={{ textAlign: 'right', color: row.falsePositives ? 'var(--ink)' : 'var(--text-faint)' }}
      >
        {row.falsePositives ? exact(row.falsePositives) : 'none'}
      </span>

      <span>
        {flawless ? (
          <Badge status="clean" tone="clean">Caught every one</Badge>
        ) : (row.recall ?? 1) < 1 ? (
          <Badge status="redacted" tone="redacted">Missed some</Badge>
        ) : (
          <Badge status="info" tone="info">Some false alarms</Badge>
        )}
      </span>
    </div>
  );
}

/**
 * A share, with a short rule under it.
 *
 * The rule is 44px and not the column width - stretched across the cell it read as
 * an input underline, and a column of them looked like a form. The scale starts at
 * 80% because every value in this table sits between 0.88 and 1, and a full-range
 * bar would make 88% and 99.99% look identical.
 */
function ScoreCell({ value }: { value: number | null }) {
  if (value === null) {
    return <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>not tested</span>;
  }
  const whole = value === 1;
  // 0.999994 rounds to "100.0%", which then sat next to a badge saying it missed
  // something - the table contradicting itself in two adjacent columns. A share that
  // is not all of them never reads as all of them.
  const label = whole ? 'all of them'
    : value >= 0.9995 ? 'all but a few'
      : percent(value, 1);
  return (
    <span style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
      <span className="zt-mono-sm zt-nums" style={{ color: whole ? 'var(--text-quiet)' : 'var(--ink)' }}>
        {label}
      </span>
      <span aria-hidden style={{ width: 44, height: 2, background: 'rgba(17,17,17,0.11)', borderRadius: 1 }}>
        <span
          style={{
            display: 'block', height: '100%',
            width: `${Math.max(0, (value - 0.8) / 0.2) * 100}%`,
            background: whole ? 'rgba(17,17,17,0.22)' : 'rgba(17,17,17,0.72)',
            borderRadius: 1,
          }}
        />
      </span>
    </span>
  );
}
