'use client';

/**
 * Inspector - why this payload got this decision.
 *
 * The console never renders a sensitive value, so this screen cannot show the
 * payload. What it shows instead is everything the product actually keeps: the
 * span path, the class, the offsets, the stage that found it, the origin it sat
 * in, and whether that origin allowed it to enforce. That is enough to defend a
 * decision to an auditor and not enough to leak anything, which is the same
 * property `Finding` has by construction.
 *
 * The masked run is drawn at the true character length from `start` and `end`,
 * because the length is a fact the product holds and the shape of the redaction
 * is what makes the decision legible.
 */
import Link from 'next/link';
import { Badge, Card, Icon, StatusDot, Tag, Tooltip } from '@/ds';
import { Column, Headline, Pair, Panel, Provenance, TableHead, columns } from '@/components/console/Frame';
import { clock, type SampleFinding, type SampleRow } from '@/lib/benchmark';
import { classToken, exact, micros } from '@/lib/format';

const COLS: Column[] = [
  { key: 'path', head: 'Span path', w: 'minmax(0,1.6fr)' },
  { key: 'class', head: 'Class', w: '164px' },
  { key: 'span', head: 'Redacted run', w: 'minmax(0,1fr)' },
  { key: 'offsets', head: 'Offsets', w: '104px' },
  { key: 'conf', head: 'Conf.', w: '58px', align: 'right' },
  { key: 'stage', head: 'Stage', w: '48px' },
  { key: 'enforce', head: 'Enforces', w: '92px' },
];

const ORIGIN_COPY: Record<string, string> = {
  user: 'user turn',
  assistant: 'assistant turn',
  system: 'developer instructions',
  tool_definition: 'tool schema',
  tool_result: 'tool result',
  metadata: 'protocol field',
};

export function InspectorView({ row }: { row: SampleRow }) {
  const enforceable = row.findings.filter((f) => !f.advisory && f.origin !== 'tool_definition');
  const classes = Array.from(new Set(enforceable.map((f) => f.class)));

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
        All traffic
      </Link>

      {/* Grid lives in `.zt-split` in globals.css, not inline: an inline
          grid-template-columns beats the media query and the two columns never
          collapsed on a narrow screen. */}
      <div className="zt-split">
        <div>
          <Headline
            sub={
              row.status === 'blocked'
                ? 'Nothing was dispatched. The caller received a provider-shaped notice naming what was found, so the tool kept working rather than erroring.'
                : row.status === 'redacted'
                  ? 'The payload was rewritten and the rewrite was verified against the bytes about to leave before anything was sent.'
                  : 'Nothing matched a rule. The payload was dispatched unmodified.'
            }
          >
            {row.status === 'blocked' ? 'Blocked at the boundary.'
              : row.status === 'redacted' ? 'Redacted, then dispatched.'
                : 'Clean. Dispatched unmodified.'}
          </Headline>

          <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap', marginTop: 26 }}>
            <Pair value={micros(row.latency_us)} of="scan time" />
            <Pair value={exact(row.findings.length)} of="findings" />
            <Pair value={String(row.cache_hits)} of={`cache hits of ${row.cache_hits + row.cache_misses} spans`} />
          </div>
        </div>

        <Card tone="dark" pad={24}>
          <Panel title="The decision" onDark>
            <dl style={{ margin: 0, display: 'flex', flexDirection: 'column', gap: 11 }}>
              {[
                ['request', row.id],
                ['action', row.action],
                ['verdict', row.verdict],
                ['rule', row.rule_index === null ? 'default' : `index ${row.rule_index}`],
                ['leg', row.leg],
                ['actor', `${row.actor.id} · ${row.actor.role}`],
                ['groups', row.actor.groups.length ? row.actor.groups.join(', ') : 'none'],
                ['channel', `${row.channel} · ${row.harness}`],
                ['route', `${row.provider} ${row.route}`],
                ['environment', row.env],
                ['degraded', row.degraded ?? 'none'],
              ].map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
                  <dt className="zt-mono-sm" style={{ color: 'rgba(242,242,240,0.36)' }}>{k}</dt>
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
            title="Findings"
            note="Span paths, classes and character offsets. There is no field on a finding that can hold the value it found, and no operation anywhere in this console that reveals one."
            right={
              row.status !== 'clean' ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <StatusDot state={row.status} size={6} />
                  <span className="zt-mono-sm">{classes.map(classToken).join(', ') || 'policy'}</span>
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
              {row.findings.map((f, i) => <FindingRow key={i} f={f} />)}
            </div>
          </div>
        ) : (
          <div style={{ padding: '8px 20px 26px' }}>
            <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>
              No findings. Every span was scanned and nothing matched.
            </p>
          </div>
        )}

        <div
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
            padding: '12px 16px', boxShadow: 'inset 0 1px 0 var(--border-hairline)',
          }}
        >
          <span className="zt-eyebrow">
            {row.readonly_skipped > 0
              ? `${exact(row.readonly_skipped)} reported, not rewritten`
              : 'All findings in rewritable origins'}
          </span>
          <span className="zt-mono-sm" style={{ color: 'var(--text-quiet)' }}>
            {clock(row.minute)} · {row.workload}
          </span>
        </div>
      </Card>

      <Provenance scope={`Payload ${row.id}`} />
    </div>
  );
}

function FindingRow({ f }: { f: SampleFinding }) {
  const readOnly = f.origin === 'tool_definition';
  const enforces = !f.advisory && !readOnly;

  return (
    <div
      className="zt-row"
      style={{
        display: 'grid', gridTemplateColumns: columns(COLS), gap: 12, alignItems: 'center',
        minHeight: 'var(--row-h)', padding: '11px 16px',
        boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
      }}
    >
      <span style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span
          className="zt-mono-sm"
          style={{ color: 'var(--text-body)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
        >
          {f.span_path}
        </span>
        <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>
          {ORIGIN_COPY[f.origin] ?? f.origin} · {f.leg}
        </span>
      </span>

      <span><Tag mono>{classToken(f.class)}</Tag></span>

      {/* The redaction at true character length. Never the value - the length is a
          fact the product holds, and the shape is what makes the decision legible. */}
      <span style={{ minWidth: 0, display: 'flex', alignItems: 'center' }}>
        <Tooltip label={`${f.length} characters`}>
          <span
            aria-label={`${classToken(f.class)}, ${f.length} characters, redacted`}
            style={{
              display: 'inline-block', height: 13,
              width: `${Math.min(f.length, 40)}ch`, maxWidth: '100%',
              background: 'rgba(17,17,17,0.11)',
              boxShadow: 'inset 0 0 0 1px rgba(17,17,17,0.22)',
              borderRadius: 'var(--r-2)',
            }}
          />
        </Tooltip>
      </span>

      <span className="zt-mono-sm zt-nums" style={{ color: 'var(--text-quiet)' }}>
        [{f.start}, {f.end})
      </span>

      <span
        className="zt-mono-sm zt-nums"
        style={{ textAlign: 'right', color: f.confidence >= 0.75 ? 'var(--ink)' : 'var(--text-faint)' }}
      >
        {f.confidence.toFixed(2)}
      </span>

      <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>{f.stage}</span>

      <span>
        {enforces ? (
          <Badge status="blocked" tone="blocked">Yes</Badge>
        ) : (
          <Tooltip label={readOnly
            ? 'Tool schemas are read-only. Reported, never rewritten.'
            : 'Advisory class. Corroborates, never enforces alone.'}>
            <span><Badge tone="neutral">{readOnly ? 'Read-only' : 'Advisory'}</Badge></span>
          </Tooltip>
        )}
      </span>
    </div>
  );
}
