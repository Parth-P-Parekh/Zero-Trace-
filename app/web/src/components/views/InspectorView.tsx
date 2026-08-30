'use client';

/**
 * One request, and why it got the answer it got.
 *
 * The console never shows a sensitive value, so this screen cannot show the request.
 * What it shows instead is everything the product actually keeps: where the thing
 * was, what kind of thing it was, how long it was, and how it was spotted. That is
 * enough to defend the decision to an auditor and not enough to leak anything.
 *
 * Character offsets, confidence scores and stage codes have gone. They were the
 * three columns that made this table look like a debugger, and none of them changes
 * what a reader would do next. The grey bar stays: drawn at the true length of the
 * original, it is the one thing that makes a decision legible without showing the
 * value.
 */
import Link from 'next/link';
import { Badge, Card, Icon, StatusDot, Tag, Tooltip } from '@/ds';
import { Column, Headline, Pair, Panel, Provenance, TableHead, columns } from '@/components/console/Frame';
import { clock, type SampleFinding, type SampleRow } from '@/lib/benchmark';
import { exact, micros } from '@/lib/format';
import { howFound, place, thing } from '@/lib/words';

const COLS: Column[] = [
  { key: 'where', head: 'Where it was', w: 'minmax(0,1.3fr)' },
  { key: 'what', head: 'What it was', w: '168px' },
  { key: 'len', head: 'How long', w: 'minmax(0,1fr)' },
  { key: 'how', head: 'How we spotted it', w: '190px' },
  { key: 'acted', head: '', w: '108px' },
];

export function InspectorView({ row }: { row: SampleRow }) {
  const acted = row.findings.filter((f) => !f.advisory && f.origin !== 'tool_definition');
  const kinds = Array.from(new Set(acted.map((f) => f.class)));
  // The length bars are scaled against this, so they compare with each other and
  // stay inside the column whatever the window is doing.
  const longest = Math.max(...row.findings.map((f) => f.length), 1);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 'var(--page-max)' }}>
      <Link
        href="/traffic"
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 6, textDecoration: 'none',
          font: 'var(--type-body-sm)', color: 'var(--text-quiet)', width: 'fit-content',
        }}
      >
        <Icon name="chevron-right" size={13} style={{ transform: 'rotate(180deg)' }} />
        All requests
      </Link>

      <div className="zt-split">
        <div>
          <Headline
            sub={
              row.status === 'blocked'
                ? 'The model never received it. The app got a normal-looking reply explaining what was found, so it kept working instead of erroring.'
                : row.status === 'redacted'
                  ? 'The sensitive parts were swapped out, and we checked they were really gone before anything was sent.'
                  : 'Nothing matched a rule, so it went on unchanged.'
            }
          >
            {row.status === 'blocked' ? 'Stopped before it was sent.'
              : row.status === 'redacted' ? 'Cleaned up, then sent.'
                : 'Nothing found. Sent as it was.'}
          </Headline>

          <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap', marginTop: 26 }}>
            <Pair value={micros(row.latency_us)} of="to check" />
            <Pair value={exact(row.findings.length)} of="things found" />
            {kinds.length ? (
              <Pair value={kinds.map(thing).join(', ')} of="acted on" size={16} />
            ) : null}
          </div>
        </div>

        <Card tone="dark" pad={24}>
          <Panel title="The details" onDark>
            <dl style={{ margin: 0, display: 'flex', flexDirection: 'column', gap: 11 }}>
              {[
                ['Reference', row.id],
                ['App', row.workload],
                ['Sent by', row.actor.unregistered ? 'nobody we recognise' : row.actor.id],
                ['Their team', row.actor.groups.length ? row.actor.groups.join(', ') : 'none'],
                ['Direction', row.leg === 'outbound' ? 'Going to the model' : 'Coming back from the model'],
                ['Environment', row.env === 'production' ? 'Live' : 'Test'],
                ['Time', clock(row.minute)],
              ].map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
                  <dt style={{ font: 'var(--type-body-sm)', color: 'rgba(242,242,240,0.52)' }}>{k}</dt>
                  <dd
                    className="zt-mono-sm"
                    style={{
                      margin: 0, color: 'var(--text-on-dark-quiet)', textAlign: 'right',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}
                  >
                    {v}
                  </dd>
                </div>
              ))}
            </dl>
          </Panel>
        </Card>
      </div>

      {/* -- the findings ---------------------------------------------------------- */}
      <Card pad={0}>
        <div style={{ padding: '18px 20px 4px' }}>
          <Panel
            title="What was found"
            // Says "in proportion to", not "at the real length" - the bars are scaled
            // against the longest finding here, so the claim has to match the drawing.
            note="Each bar is sized in proportion to how much text was removed, with the exact count beside it. The value itself is not stored anywhere in this dashboard, and there is no button that would reveal it."
            right={
              row.status !== 'clean' ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <StatusDot state={row.status} size={6} />
                  <span style={{ font: 'var(--type-body-sm)' }}>
                    {row.status === 'blocked' ? 'Stopped' : 'Cleaned up'}
                  </span>
                </div>
              ) : null
            }
          >
            <div />
          </Panel>
        </div>

        {row.findings.length ? (
          <div className="zt-table">
            <div>
              <TableHead cols={COLS} />
              {row.findings.map((f, i) => <FindingRow key={i} f={f} longest={longest} />)}
            </div>
          </div>
        ) : (
          <div style={{ padding: '8px 20px 26px' }}>
            <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>
              Nothing. Every part of the request was checked and none of it matched.
            </p>
          </div>
        )}

        {row.readonly_skipped > 0 ? (
          <div
            style={{
              padding: '12px 16px', boxShadow: 'inset 0 1px 0 var(--border-hairline)',
              font: 'var(--type-body-sm)', color: 'var(--text-quiet)',
            }}
          >
            {exact(row.readonly_skipped)} of these sat in a tool&rsquo;s own description, so
            they were reported and left alone.
          </div>
        ) : null}
      </Card>

      <Provenance />
    </div>
  );
}

function FindingRow({ f, longest }: { f: SampleFinding; longest: number }) {
  const toolText = f.origin === 'tool_definition';
  const acted = !f.advisory && !toolText;

  return (
    <div
      className="zt-row"
      style={{
        display: 'grid', gridTemplateColumns: columns(COLS), gap: 12, alignItems: 'center',
        minHeight: 'var(--row-h)', padding: '12px 16px',
        boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
      }}
    >
      <span style={{ minWidth: 0, font: 'var(--type-body-sm)' }}>{place(f.origin)}</span>

      <span><Tag>{thing(f.class)}</Tag></span>

      {/* The bar is a share of this column, scaled against the longest finding in
          this request - never an absolute `ch` measure.

          It used to be `width: min(length, 32)ch` with `maxWidth: 100%`, and both
          halves of that were wrong. The max-width resolved against the tooltip's
          wrapper rather than the column, so it never constrained anything; and that
          wrapper is a flex item with no `min-width: 0`, so it would not shrink while
          the column did. 58% of findings are 32 characters or longer, so most rows
          drew a ~256px bar into a ~250px cell and pushed the character count on top
          of the next column.

          A percentage of the track cannot overflow at any width, and scaling within
          the request is the comparison this column is actually for. */}
      <span style={{ minWidth: 0, display: 'flex', alignItems: 'center', gap: 10, overflow: 'hidden' }}>
        <span
          title={`${f.length} characters`}
          aria-label={`${thing(f.class)}, ${f.length} characters, removed`}
          style={{ flex: '1 1 auto', minWidth: 0, height: 13, display: 'block' }}
        >
          <span
            style={{
              display: 'block', height: '100%',
              width: `${Math.max((f.length / longest) * 100, 6)}%`,
              background: 'rgba(17,17,17,0.11)',
              boxShadow: 'inset 0 0 0 1px rgba(17,17,17,0.22)',
              borderRadius: 'var(--r-2)',
            }}
          />
        </span>
        {/* Fixed width and right-aligned, so a column of these reads as a column
            rather than as numbers wandering with the bar in front of them. */}
        <span
          className="zt-mono-sm zt-nums"
          style={{ color: 'var(--text-faint)', flex: '0 0 auto', width: 32, textAlign: 'right' }}
        >
          {f.length}
        </span>
      </span>

      <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)', minWidth: 0 }}>
        {howFound(f.stage)}
      </span>

      <span>
        {acted ? (
          <Badge status="blocked" tone="blocked">Acted on</Badge>
        ) : (
          <Tooltip
            label={toolText
              ? 'Part of a tool’s own description. Nobody writing a prompt can change it, so it is never blocked.'
              : 'Random-looking text. Counted as supporting evidence, never enough on its own.'}
          >
            <span><Badge tone="neutral">{toolText ? 'Not ours' : 'Noted only'}</Badge></span>
          </Tooltip>
        )}
      </span>
    </div>
  );
}
