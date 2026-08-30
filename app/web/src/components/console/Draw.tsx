/**
 * Everything the console draws, drawn with the ramp.
 *
 * There is no chart library here and there will not be one. The design system's
 * six-stop opacity ramp is the only source of tonal value in the identity, and a
 * charting library arrives with its own categorical palette - which would be a
 * second visual system sitting inside the first. So series are composed from
 * rules, blocks and one inline polyline, and every fill resolves to a ramp stop.
 *
 * These are pure renderers with no state, so they stay server components. Only
 * the views that filter or select need a client boundary.
 */
import { RAMP, rampStop } from '@/lib/benchmark';
import { exact, percent } from '@/lib/format';

const INK = 'var(--ink)';

/** Ink at a ramp stop. The one function that decides tone anywhere in the console. */
export function ink(stop: number, onDark = false): string {
  return onDark ? `rgba(242,242,240,${stop})` : `rgba(17,17,17,${stop})`;
}

// ------------------------------------------------------------------ ratio bar --

export interface Segment {
  label: string;
  value: number;
  /** Optional explicit ramp stop. Omitted, segments walk the ramp in order. */
  stop?: number;
  /** A 6px signal dot beside the label. Never the fill - the fill is always ramp. */
  signal?: 'clean' | 'redacted' | 'blocked' | 'info';
}

/**
 * One horizontal rule split by share, with the legend under it.
 *
 * Used wherever a whole divides into parts - outcomes, actions, families, stages.
 * A stacked bar rather than a pie because these are compared against each other
 * and against 100%, and because a pie in this system would need six fills that
 * are only distinguishable by area.
 */
export function RatioBar({
  segments,
  height = 10,
  onDark = false,
  legend = true,
  total: totalOverride,
}: {
  segments: Segment[];
  height?: number;
  onDark?: boolean;
  legend?: boolean;
  total?: number;
}) {
  const total = totalOverride ?? (segments.reduce((n, s) => n + s.value, 0) || 1);
  return (
    <div>
      <div
        style={{
          display: 'flex', width: '100%', height, borderRadius: 'var(--r-2)',
          overflow: 'hidden', background: ink(0.11, onDark),
        }}
      >
        {segments.map((s, i) => (
          <div
            key={s.label}
            title={`${s.label}: ${exact(s.value)}`}
            style={{
              width: `${(s.value / total) * 100}%`,
              background: ink(s.stop ?? RAMP[Math.min(i, RAMP.length - 1)], onDark),
            }}
          />
        ))}
      </div>
      {legend ? (
        <div
          style={{
            display: 'flex', flexWrap: 'wrap', gap: '6px 20px', marginTop: 12,
          }}
        >
          {segments.map((s, i) => (
            <div key={s.label} style={{ display: 'flex', alignItems: 'baseline', gap: 7 }}>
              <span
                aria-hidden
                style={{
                  width: 8, height: 8, borderRadius: 'var(--r-2)', flex: '0 0 auto',
                  alignSelf: 'center',
                  background: ink(s.stop ?? RAMP[Math.min(i, RAMP.length - 1)], onDark),
                }}
              />
              <span
                style={{
                  font: 'var(--type-body-sm)',
                  color: onDark ? 'var(--text-on-dark-body)' : 'var(--text-body)',
                }}
              >
                {s.label}
              </span>
              <span
                className="zt-mono-sm zt-nums"
                style={{ color: onDark ? 'rgba(242,242,240,0.52)' : 'var(--text-quiet)' }}
              >
                {percent(s.value / total, 2)}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

// ----------------------------------------------------------------- bar series --

export interface BarRow {
  label: string;
  value: number;
  /** Second line under the label. Kept short - this is a table, not a paragraph. */
  note?: string;
  mono?: boolean;
  href?: string;
}

/**
 * A ranked list with the bar drawn behind the row rather than beside it.
 *
 * Behind, because a separate bar column costs horizontal space the label needs and
 * makes the eye travel twice. The fill sits at ramp .11 so it reads as ground, not
 * as a second element competing with the number.
 */
export function BarSeries({
  rows,
  max: maxOverride,
  onDark = false,
  format = exact,
  limit,
}: {
  rows: BarRow[];
  max?: number;
  onDark?: boolean;
  format?: (n: number) => string;
  limit?: number;
}) {
  const shown = limit ? rows.slice(0, limit) : rows;
  const max = maxOverride ?? Math.max(...shown.map((r) => r.value), 1);
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {shown.map((r) => (
        <div
          key={r.label}
          style={{
            position: 'relative', display: 'flex', alignItems: 'baseline', gap: 12,
            padding: '9px 10px', minHeight: 34,
            boxShadow: `inset 0 -1px 0 ${onDark ? 'var(--border-on-dark)' : 'var(--border-hairline)'}`,
          }}
        >
          <div
            aria-hidden
            style={{
              position: 'absolute', inset: '0 auto 0 0', zIndex: 0,
              width: `${(r.value / max) * 100}%`,
              background: ink(0.11, onDark),
            }}
          />
          <span
            className={r.mono ? 'zt-mono-sm' : undefined}
            style={{
              position: 'relative', zIndex: 1, flex: 1, minWidth: 0,
              font: r.mono ? undefined : 'var(--type-body-sm)',
              color: onDark ? 'var(--text-on-dark-body)' : 'var(--text-body)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}
          >
            {r.label}
            {r.note ? (
              <span style={{ color: onDark ? 'rgba(242,242,240,0.36)' : 'var(--text-faint)' }}>
                {'  '}{r.note}
              </span>
            ) : null}
          </span>
          <span
            className="zt-mono-sm zt-nums"
            style={{
              position: 'relative', zIndex: 1, flex: '0 0 auto',
              color: onDark ? 'var(--ink-inverse)' : INK,
            }}
          >
            {format(r.value)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------ evasion matrix --

/**
 * The console's one bold move, and it is bold because of what it says.
 *
 * Each cell is an evasion technique, filled at the ramp stop nearest the rate at
 * which the detector still caught the credential. A full cell is a technique that
 * does not work; an almost-empty one is a technique that does. The design system's
 * identity gesture is ink draining away, and this is that gesture used as
 * evidence: the cells that have drained are the ways out of the building.
 *
 * It gets the strongest treatment on the strongest finding, and nothing else on
 * the page competes with it.
 */
export function EvasionMatrix({
  rows,
  onDark = true,
}: {
  rows: Array<{ family: string; variant: string; records: number; detectionRate: number; ramp: number }>;
  onDark?: boolean;
}) {
  return (
    <div
      style={{
        display: 'grid', gap: 1,
        gridTemplateColumns: `repeat(auto-fit, minmax(148px, 1fr))`,
        background: onDark ? 'var(--border-on-dark)' : 'var(--border-hairline)',
        border: `1px solid ${onDark ? 'var(--border-on-dark)' : 'var(--border-hairline)'}`,
        borderRadius: 'var(--r-8)', overflow: 'hidden',
      }}
    >
      {rows.map((r) => {
        const caught = r.detectionRate;
        const stop = rampStop(caught);
        // Each label is coloured by whether the fill actually reaches *it*, not by
        // the overall rate. The variant sits at the top and the number at the
        // bottom, so a 75% fill covers the number and leaves the label on the dark
        // ground - keying both off one threshold made that label invisible.
        const onFillTop = caught >= 0.88;
        const onFillBottom = caught >= 0.34;
        return (
          <div
            key={`${r.family}:${r.variant}`}
            style={{
              position: 'relative',
              background: onDark ? 'var(--surface-dark)' : 'var(--paper)',
              padding: '14px 14px 12px', minHeight: 116,
              display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
            }}
          >
            {/* The fill: how much of this technique the detector still catches. */}
            <div
              aria-hidden
              style={{
                position: 'absolute', left: 0, right: 0, bottom: 0,
                height: `${Math.max(caught * 100, 1.5)}%`,
                background: ink(stop, onDark),
              }}
            />
            <div style={{ position: 'relative', zIndex: 1 }}>
              <div
                className="zt-mono-sm"
                style={{
                  color: onFillTop
                    ? (onDark ? 'var(--surface-dark)' : 'var(--paper)')
                    : (onDark ? 'var(--text-on-dark-quiet)' : 'var(--text-quiet)'),
                }}
              >
                {r.variant.replace(/_/g, ' ')}
              </div>
            </div>
            <div style={{ position: 'relative', zIndex: 1 }}>
              <div
                className="zt-nums"
                style={{
                  font: 'var(--w-semibold) var(--t-27)/1 var(--font-core)',
                  letterSpacing: 'var(--tr-heading)',
                  color: onFillBottom
                    ? (onDark ? 'var(--surface-dark)' : 'var(--paper)')
                    : (onDark ? 'var(--ink-inverse)' : INK),
                }}
              >
                {percent(caught, caught === 1 ? 0 : 1)}
              </div>
              <div
                className="zt-mono-sm"
                style={{
                  marginTop: 3,
                  color: onFillBottom
                    ? (onDark ? 'rgba(11,11,11,0.52)' : 'rgba(232,232,230,0.6)')
                    : (onDark ? 'rgba(242,242,240,0.36)' : 'var(--text-faint)'),
                }}
              >
                caught of {exact(r.records)}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------------ hour strip --

/**
 * Twenty-four columns, one per hour, each split by what happened to the traffic.
 *
 * Column height is volume, and the blocked and redacted shares stack from the
 * bottom - so a busy hour and a dangerous hour are distinguishable at a glance,
 * which a single-series bar chart cannot do.
 */
export function HourStrip({
  hours,
  height = 92,
  onDark = false,
}: {
  hours: Array<{ hour: number; total: number; blocked: number; redacted: number; clean: number; share: number }>;
  height?: number;
  onDark?: boolean;
}) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height }}>
        {hours.map((h) => {
          const t = h.total || 1;
          return (
            <div
              key={h.hour}
              title={`${String(h.hour).padStart(2, '0')}:00 - ${exact(h.total)} payloads, ${exact(h.blocked)} blocked`}
              style={{
                flex: 1, height: `${Math.max(h.share * 100, 2)}%`,
                display: 'flex', flexDirection: 'column', justifyContent: 'flex-end',
                borderRadius: 'var(--r-2)', overflow: 'hidden',
              }}
            >
              <div style={{ height: `${(h.clean / t) * 100}%`, background: ink(0.22, onDark) }} />
              <div style={{ height: `${(h.redacted / t) * 100}%`, background: ink(0.52, onDark) }} />
              <div style={{ height: `${(h.blocked / t) * 100}%`, background: ink(0.85, onDark) }} />
            </div>
          );
        })}
      </div>
      <div
        className="zt-mono-sm"
        style={{
          display: 'flex', justifyContent: 'space-between', marginTop: 8,
          color: onDark ? 'rgba(242,242,240,0.36)' : 'var(--text-faint)',
        }}
      >
        <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span>
      </div>
    </div>
  );
}

// ------------------------------------------------------------- quantile ladder --

/**
 * The latency distribution as a ladder rather than a curve.
 *
 * A histogram of this data is a spike against a long thin tail and reads as an
 * empty box. What an operator actually asks is "what does the slow request cost",
 * and that is a set of named quantiles - so the named quantiles are the chart.
 */
export function QuantileLadder({
  points,
  max,
  onDark = false,
  format,
}: {
  points: Array<{ label: string; value: number }>;
  max?: number;
  onDark?: boolean;
  format: (n: number) => string;
}) {
  const ceiling = max ?? Math.max(...points.map((p) => p.value), 1);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {points.map((p, i) => (
        <div key={p.label} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span
            className="zt-mono-sm"
            style={{
              width: 34, flex: '0 0 auto',
              color: onDark ? 'rgba(242,242,240,0.52)' : 'var(--text-quiet)',
            }}
          >
            {p.label}
          </span>
          <div style={{ flex: 1, height: 6, background: ink(0.11, onDark), borderRadius: 'var(--r-2)' }}>
            <div
              style={{
                width: `${Math.max((p.value / ceiling) * 100, 0.6)}%`, height: '100%',
                background: ink(RAMP[Math.min(i, RAMP.length - 1)], onDark),
                borderRadius: 'var(--r-2)',
              }}
            />
          </div>
          <span
            className="zt-mono-sm zt-nums"
            style={{
              width: 78, textAlign: 'right', flex: '0 0 auto',
              color: onDark ? 'var(--ink-inverse)' : INK,
            }}
          >
            {format(p.value)}
          </span>
        </div>
      ))}
    </div>
  );
}

// --------------------------------------------------------------- meter (1 of n) --

/**
 * A single proportion with its own label. The smallest possible chart, used where
 * a number needs a shape beside it but a whole bar series would be four rows of
 * chrome for one fact.
 */
export function Meter({
  value,
  label,
  caption,
  onDark = false,
  invert = false,
}: {
  value: number;
  label: string;
  caption?: string;
  onDark?: boolean;
  /** True when a low number is the good one, so the fill draws the shortfall. */
  invert?: boolean;
}) {
  const filled = invert ? 1 - value : value;
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
        <span
          style={{
            font: 'var(--type-body-sm)',
            color: onDark ? 'var(--text-on-dark-body)' : 'var(--text-body)',
          }}
        >
          {label}
        </span>
        <span
          className="zt-nums"
          style={{
            font: 'var(--w-semibold) var(--t-16)/1 var(--font-core)',
            color: onDark ? 'var(--ink-inverse)' : INK,
          }}
        >
          {percent(value, 2)}
        </span>
      </div>
      <div
        style={{
          height: 4, marginTop: 8, background: ink(0.11, onDark),
          borderRadius: 'var(--r-2)', overflow: 'hidden',
        }}
      >
        <div style={{ width: `${filled * 100}%`, height: '100%', background: ink(0.72, onDark) }} />
      </div>
      {caption ? (
        <p
          className="zt-mono-sm"
          style={{
            margin: '8px 0 0',
            color: onDark ? 'rgba(242,242,240,0.36)' : 'var(--text-faint)',
          }}
        >
          {caption}
        </p>
      ) : null}
    </div>
  );
}
