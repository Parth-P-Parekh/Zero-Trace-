'use client';

/**
 * Traffic - what went out, and what happened to it.
 *
 * This screen used to carry six blocks: the outcome split, added latency, a
 * pipeline-stage breakdown, span-cache hit rates and sustained throughput, then the
 * feed. Four of those answer "how is it built", which is a different question from
 * the one somebody opens this screen with, and they pushed the actual answer below
 * the fold. They live on the How-it-works screen now.
 *
 * What is left is the question and its answer: five million things went out, this
 * many had something in them, it cost a quarter of a millisecond, here they are.
 */
import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Card, EmptyState, Icon, Input, SegmentedControl, StatusDot, Tabs, Tag, Tooltip } from '@/ds';
import { RatioBar } from '@/components/console/Draw';
import { Caveat, Column, Figure, Footnote, Headline, Pair, Panel, Provenance, TableHead, columns } from '@/components/console/Frame';
import { clock, run, type SampleRow } from '@/lib/benchmark';
import { exact, micros } from '@/lib/format';
import { thing } from '@/lib/words';

const COLS: Column[] = [
  { key: 'time', head: 'Time', w: '62px' },
  { key: 'workload', head: 'App', w: 'minmax(0,1fr)' },
  { key: 'found', head: 'What we found', w: 'minmax(0,1.5fr)' },
  { key: 'result', head: 'Result', w: '112px' },
  { key: 'speed', head: 'Checked in', w: '82px', align: 'right' },
  { key: 'go', head: '', w: '18px' },
];

export function TrafficView({ rows }: { rows: SampleRow[] }) {
  const [tab, setTab] = useState('all');
  const [env, setEnv] = useState('all');
  const [q, setQ] = useState('');

  const filtered = useMemo(
    () =>
      rows.filter((r) => {
        if (tab !== 'all' && r.status !== tab) return false;
        if (env !== 'all' && r.env !== env) return false;
        if (q) {
          const hay = `${r.workload} ${r.actor.id} ${r.findings.map((f) => thing(f.class)).join(' ')}`;
          if (!hay.toLowerCase().includes(q.toLowerCase())) return false;
        }
        return true;
      }),
    [rows, tab, env, q],
  );

  const { status, latencyAsync } = run;
  const touched = status.blocked + status.redacted;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 'var(--page-max)' }}>
      <div className="zt-split">
        <div>
          <Headline
            sub="Every request an app made to an AI model, checked on the way out and on the
                 way back. Nothing here is a sample - it is all of it."
          >
            <Figure>{exact(status.total)}</Figure> requests checked.{' '}
            <Figure>{exact(touched)}</Figure> had something in them.
          </Headline>

          <div style={{ marginTop: 26 }}>
            <RatioBar
              segments={[
                { label: 'Nothing found', value: status.clean, stop: 0.22 },
                { label: 'Sensitive data removed', value: status.redacted, stop: 0.52 },
                { label: 'Stopped before sending', value: status.blocked, stop: 1.0 },
              ]}
              total={status.total}
            />
          </div>
        </div>

        {/* The one number the product is disbelieved about. */}
        <Card tone="dark" pad={24}>
          <Panel title="Time added to a request" onDark>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 24, flexWrap: 'wrap' }}>
              <Pair value={micros(latencyAsync.p50_us)} of="typical" onDark size={33} />
              <Pair value={micros(latencyAsync.p95_us)} of="slowest 1 in 20" onDark />
            </div>
            <Footnote onDark measure="46ch">
              The model call it sits in front of takes between 300 and 2,000 milliseconds.
              This is about a thousandth of that, so nobody using the app notices it.
            </Footnote>
          </Panel>
        </Card>
      </div>

      {/* -- the feed ---------------------------------------------------------- */}
      <Card pad={0}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '16px 16px 0', flexWrap: 'wrap' }}>
          <Tabs
            value={tab}
            onChange={setTab}
            style={{ flex: 1, minWidth: 250 }}
            items={[
              { value: 'all', label: 'All', count: rows.length },
              { value: 'blocked', label: 'Stopped', count: rows.filter((r) => r.status === 'blocked').length },
              { value: 'redacted', label: 'Cleaned up', count: rows.filter((r) => r.status === 'redacted').length },
              { value: 'clean', label: 'Nothing found', count: rows.filter((r) => r.status === 'clean').length },
            ]}
          />
          <SegmentedControl
            size="sm"
            value={env}
            onChange={setEnv}
            items={[
              { value: 'all', label: 'Both' },
              { value: 'production', label: 'Live' },
              { value: 'staging', label: 'Test' },
            ]}
          />
          <Input
            size="sm"
            icon="search"
            placeholder="Search apps, people, what was found"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ width: 240, paddingBottom: 10 }}
          />
        </div>

        <div className="zt-table">
          <div>
            <TableHead cols={COLS} />
            {filtered.length ? (
              filtered.map((r) => <TrafficRow key={r.id} row={r} />)
            ) : (
              <EmptyState
                icon="search"
                title="Nothing matches"
                description="Clear the search, or switch back to both environments."
              />
            )}
          </div>
        </div>

        <div
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            gap: 12, padding: '12px 16px', boxShadow: 'inset 0 1px 0 var(--border-hairline)',
          }}
        >
          <span className="zt-eyebrow">
            {exact(filtered.length)} shown of {exact(status.total)} checked
          </span>
          <span className="zt-mono-sm" style={{ color: 'var(--text-quiet)' }}>
            an even sample, 1 in {exact(Math.round(status.total / rows.length))}
          </span>
        </div>
      </Card>

      <Caveat>
        The list is an even sample rather than the newest requests, so the mix in it
        matches the mix in the bar above. Open any row to see what was found and why.
      </Caveat>

      <Provenance />
    </div>
  );
}

function TrafficRow({ row }: { row: SampleRow }) {
  const found = Array.from(new Set(row.findings.filter((f) => !f.advisory).map((f) => f.class)));
  const shown = found.slice(0, 2);
  const rest = found.length - shown.length;
  // A row can name a key and still say the request was sent, because the key was in
  // a tool's own description rather than in anything a person wrote. Without a word
  // for that, the table looks like it found a key and let it through.
  const notOurs = row.status === 'clean'
    && row.findings.some((f) => f.origin === 'tool_definition' || f.origin === 'system');

  return (
    <Link href={`/traffic/${row.id}`} style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}>
      <div
        className="zt-row"
        style={{
          display: 'grid', gridTemplateColumns: columns(COLS), gap: 12, alignItems: 'center',
          minHeight: 'var(--row-h)', padding: '0 16px',
          boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
          transition: 'background-color var(--d-fast) var(--ease-out)',
        }}
      >
        <span className="zt-mono-sm" style={{ color: 'var(--text-quiet)' }}>{clock(row.minute)}</span>

        <span style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
          <span style={{ font: 'var(--type-body-sm)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {row.workload}
          </span>
          <span
            className="zt-mono-sm"
            style={{ color: row.actor.unregistered ? 'var(--signal-redacted)' : 'var(--text-faint)' }}
          >
            {row.actor.unregistered ? 'nobody we recognise' : row.actor.id}
          </span>
        </span>

        <span style={{ display: 'flex', gap: 5, alignItems: 'center', minWidth: 0, flexWrap: 'wrap' }}>
          {shown.length === 0 ? (
            <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-faint)' }}>Nothing</span>
          ) : (
            shown.map((c) => <Tag key={c}>{thing(c)}</Tag>)
          )}
          {rest > 0 ? (
            <span className="zt-mono-sm" style={{ color: 'var(--text-quiet)' }}>+{rest}</span>
          ) : null}
        </span>

        <span style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
          <StatusDot state={row.status} size={6} />
          <span style={{ font: 'var(--type-body-sm)' }}>
            {row.status === 'blocked' ? 'Stopped'
              : row.status === 'redacted' ? 'Cleaned up' : 'Sent'}
          </span>
          {notOurs ? (
            <Tooltip label="Found in a tool's own description, which the person writing the prompt cannot change. Reported, never blocked.">
              <span style={{ display: 'inline-flex', color: 'var(--text-faint)' }}>
                <Icon name="eye-off" size={13} />
              </span>
            </Tooltip>
          ) : null}
        </span>

        <span className="zt-mono-sm zt-nums" style={{ color: 'var(--text-quiet)', textAlign: 'right' }}>
          {micros(row.latency_us)}
        </span>

        <span style={{ color: 'var(--text-faint)', display: 'inline-flex' }}>
          <Icon name="chevron-right" size={14} />
        </span>
      </div>
    </Link>
  );
}
