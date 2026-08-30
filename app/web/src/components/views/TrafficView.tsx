'use client';

/**
 * Traffic - what moved, and what happened to it.
 *
 * The screen answers one question in order: how much went through, what share of
 * it we touched, what it cost, and then the individual requests. The feed is last
 * because an operator arrives asking about the population and only then drills in;
 * a table at the top makes them scroll past the answer to reach the question.
 *
 * Every number here came out of the 5,000,000-record run. The dark card is spent
 * on added latency, because that is the number the product is disbelieved about -
 * a guardrail in front of every model call is assumed to be slow, and this one is
 * a quarter of a millisecond.
 */
import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Card, EmptyState, Icon, Input, SegmentedControl, StatusDot, Tabs, Tag, Tooltip } from '@/ds';
import { BarSeries, RatioBar } from '@/components/console/Draw';
import { Caveat, Column, Headline, Figure, Pair, Panel, Provenance, TableHead, columns } from '@/components/console/Frame';
import { clock, run, type SampleRow } from '@/lib/benchmark';
import { classToken, compact, exact, micros, percent } from '@/lib/format';

const COLS: Column[] = [
  { key: 'time', head: 'Time', w: '62px' },
  { key: 'workload', head: 'Workload', w: '150px' },
  { key: 'route', head: 'Route', w: 'minmax(0,1fr)' },
  // 250px, not 200: `quasi_identifier_set` is a twenty-character class name and at
  // 200 the second tag ran under the Stage column.
  { key: 'classes', head: 'Classes', w: '250px' },
  { key: 'stage', head: 'Stage', w: '52px' },
  { key: 'result', head: 'Result', w: '96px' },
  { key: 'latency', head: 'Scan', w: '74px', align: 'right' },
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
          const hay = `${r.workload} ${r.actor.id} ${r.route} ${r.harness} ${r.findings.map((f) => f.class).join(' ')}`;
          if (!hay.toLowerCase().includes(q.toLowerCase())) return false;
        }
        return true;
      }),
    [rows, tab, env, q],
  );

  const { status, outcomes, latency, latencyAsync, meta, throughput } = run;
  const touched = status.blocked + status.redacted;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 'var(--page-max)' }}>
      {/* -- what happened, in one sentence and one rule --------------------- */}
      {/* Grid lives in `.zt-split` in globals.css, not inline: an inline
          grid-template-columns beats the media query and the two columns never
          collapsed on a narrow screen. */}
      <div className="zt-split">
        <div>
          <Headline
            sub={`Across the last run the gateway inspected every payload on both legs and
                  intervened on ${percent(touched / status.total, 1)} of them. Nothing was
                  sampled: the denominator is every request that reached the gateway.`}
          >
            <Figure>{exact(status.total)}</Figure> payloads inspected,{' '}
            <Figure>{exact(touched)}</Figure> stopped or rewritten.
          </Headline>

          <div style={{ marginTop: 26 }}>
            <RatioBar
              segments={[
                { label: 'Clean', value: status.clean, stop: 0.22 },
                { label: 'Redacted', value: status.redacted, stop: 0.52 },
                { label: 'Blocked', value: status.blocked, stop: 1.0 },
              ]}
              total={status.total}
            />
          </div>
        </div>

        {/* The dark card: the number the product is disbelieved about. */}
        <Card tone="dark" pad={24}>
          <Panel title="Added latency" onDark>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 18, marginBottom: 20 }}>
              <Pair value={micros(latencyAsync.p50_us)} of="p50, full check" onDark size={33} />
              <Pair value={micros(latencyAsync.p95_us)} of="p95" onDark size={21} />
              <Pair value={micros(latencyAsync.p99_us)} of="p99" onDark size={21} />
            </div>
            {/* No ladder under these three: it drew the same three numbers a second
                time, forty pixels lower. The comparison worth drawing is against the
                thing latency is actually spent inside. */}
            <div
              style={{
                display: 'flex', alignItems: 'baseline', gap: 10, paddingTop: 20,
                boxShadow: 'inset 0 1px 0 var(--border-on-dark)',
              }}
            >
              <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)' }}>
                A cross-region model call is 300&ndash;2,000 ms.
              </span>
            </div>
            <p
              className="zt-mono-sm"
              style={{ margin: '10px 0 0', color: 'rgba(242,242,240,0.36)', lineHeight: 1.7 }}
            >
              Measured through the real{' '}
              <span style={{ color: 'var(--text-on-dark-quiet)' }}>Checker.check()</span>, worker
              thread and 50 ms watchdog included, over{' '}
              {exact(latencyAsync.records)} payloads.
            </p>
          </Panel>
        </Card>
      </div>

      {/* A volume-by-hour strip stood here and has been removed. The corpus assigns
          timestamps uniformly at random, so it drew twenty-four identical bars - a
          chart of an assumption rather than of anything the run measured. */}

      {/* -- cost and pipeline ------------------------------------------------ */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 20 }}>
        <Card pad={22}>
          <Panel title="Where findings were raised" note="Stage of the pipeline that produced each finding.">
            <BarSeries
              rows={Object.entries(run.byStage).map(([stage, n]) => ({
                label: STAGE_COPY[stage] ?? stage,
                value: n,
                note: stage,
              }))}
              format={compact}
            />
          </Panel>
        </Card>

        <Card pad={22}>
          <Panel title="Span cache" note="Chat APIs resend the conversation every turn, so most spans are seen again.">
            <div style={{ display: 'flex', gap: 26, marginBottom: 18 }}>
              <Pair value={percent(outcomes.cache_hits / (outcomes.cache_hits + outcomes.cache_misses), 1)} of="hit rate" />
              <Pair value={compact(outcomes.cache_misses)} of="scanned fresh" />
            </div>
            <RatioBar
              legend={false}
              segments={[
                { label: 'Hits', value: outcomes.cache_hits, stop: 0.72 },
                { label: 'Misses', value: outcomes.cache_misses, stop: 0.22 },
              ]}
            />
          </Panel>
        </Card>

        <Card pad={22}>
          <Panel title="Throughput" note="Single host, twenty workers, production scan engines.">
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 26 }}>
              <Pair value={exact(Math.round(meta.records_per_second))} of="payloads / second" />
              <Pair value={`${throughput.mb_per_second} MB/s`} of="scanned" />
              <Pair value={`${meta.wall_seconds.toFixed(0)} s`} of={`for ${compact(meta.records)}`} />
            </div>
          </Panel>
        </Card>
      </div>

      {/* -- the feed ---------------------------------------------------------- */}
      <Card pad={0}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '16px 16px 0', flexWrap: 'wrap' }}>
          <Tabs
            value={tab}
            onChange={setTab}
            style={{ flex: 1, minWidth: 260 }}
            items={[
              { value: 'all', label: 'All', count: rows.length },
              { value: 'blocked', label: 'Blocked', count: rows.filter((r) => r.status === 'blocked').length },
              { value: 'redacted', label: 'Redacted', count: rows.filter((r) => r.status === 'redacted').length },
              { value: 'clean', label: 'Clean', count: rows.filter((r) => r.status === 'clean').length },
            ]}
          />
          <SegmentedControl
            size="sm"
            value={env}
            onChange={setEnv}
            items={[
              { value: 'all', label: 'Both' },
              { value: 'production', label: 'Production' },
              { value: 'staging', label: 'Staging' },
            ]}
          />
          <Input
            size="sm"
            icon="search"
            placeholder="Search workloads, actors, classes"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ width: 250, paddingBottom: 10 }}
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
                title="No payloads match"
                description="Clear the search, or switch the environment back to both."
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
            {exact(filtered.length)} shown of {exact(status.total)} inspected
          </span>
          <span className="zt-mono-sm" style={{ color: 'var(--text-quiet)' }}>
            evenly sampled · 1 in {exact(Math.round(status.total / rows.length))}
          </span>
        </div>
      </Card>

      <Caveat>
        The feed is an even sample of the run, not the run. Sampling is by index,
        so it carries the population&rsquo;s mix rather than its most interesting rows -
        which is why the blocked share in the table matches the share in the rule above it.
      </Caveat>

      <Provenance />
    </div>
  );
}

const STAGE_COPY: Record<string, string> = {
  S0: 'Deterministic shapes',
  S1: 'Key-name context',
  S2: 'Co-occurrence',
  S3: 'Compositional risk',
};

function TrafficRow({ row }: { row: SampleRow }) {
  const classes = Array.from(new Set(row.findings.filter((f) => !f.advisory).map((f) => f.class)));
  const shown = classes.slice(0, 2);
  const rest = classes.length - shown.length;
  const advisory = row.findings.some((f) => f.advisory);
  // A row can name a credential class and still read Clean, because the finding sat
  // in a tool schema and schemas never enforce. Without this the table looks like it
  // found a key and let it through, which is the opposite of what happened.
  const readOnly = row.findings.some((f) => f.origin === 'tool_definition' || f.origin === 'system')
    && row.status === 'clean';
  const stage = row.findings.length
    ? row.findings.map((f) => f.stage).sort()[row.findings.length - 1]
    : null;

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
            {row.actor.unregistered ? 'unregistered' : row.actor.id}
          </span>
        </span>

        <span style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
          <span
            className="zt-mono-sm"
            style={{ color: 'var(--text-body)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
          >
            {row.route}
          </span>
          <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>
            {row.harness} · {row.channel}
          </span>
        </span>

        <span style={{ display: 'flex', gap: 4, alignItems: 'center', minWidth: 0 }}>
          {shown.length === 0 ? (
            <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-faint)' }}>-</span>
          ) : (
            shown.map((c) => <Tag key={c} mono>{classToken(c)}</Tag>)
          )}
          {rest > 0 ? (
            <span className="zt-mono-sm" style={{ color: 'var(--text-quiet)' }}>+{rest}</span>
          ) : null}
          {advisory ? (
            <Tooltip label="Also carries an advisory finding, which cannot enforce on its own">
              <span style={{ display: 'inline-flex', color: 'var(--text-faint)' }}>
                <Icon name="eye-off" size={13} />
              </span>
            </Tooltip>
          ) : null}
        </span>

        <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>{stage ?? '-'}</span>

        <span style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
          <StatusDot state={row.status} size={6} />
          <span style={{ font: 'var(--type-body-sm)' }}>
            {row.status[0].toUpperCase() + row.status.slice(1)}
          </span>
          {readOnly ? (
            <Tooltip label="Found inside a tool schema or developer instructions. Reported, never rewritten.">
              <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>ro</span>
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
