/**
 * The furniture every console screen is built from.
 *
 * One idea holds these together. Every number on these screens came out of a run
 * that can be named, and the ones that did not come out of it are absent rather
 * than estimated. So provenance is a component - `Provenance` - and it sits under
 * the screens that carry measurements, in the same place, saying the same thing.
 * A console that shows a security team a number without saying where it came from
 * is asking to be believed; this one shows its working.
 */
import Link from 'next/link';
import { Icon } from '@/ds';
import { run } from '@/lib/benchmark';
import { compact, exact } from '@/lib/format';

// --------------------------------------------------------------------- panel --

/**
 * A titled region. Not a Card - a card inside a card is banned by the design
 * system and most of these sit inside one already. A hairline and a label do the
 * same job for a fraction of the visual weight.
 */
export function Panel({
  title,
  note,
  right,
  onDark = false,
  children,
  style,
}: {
  title: string;
  note?: string;
  right?: React.ReactNode;
  onDark?: boolean;
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <section style={style}>
      <div
        style={{
          display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
          gap: 16, marginBottom: note ? 6 : 14,
        }}
      >
        <h2
          className="zt-eyebrow"
          style={{ margin: 0, color: onDark ? 'rgba(242,242,240,0.52)' : 'var(--muted)' }}
        >
          {title}
        </h2>
        {right ? <div style={{ flex: '0 0 auto' }}>{right}</div> : null}
      </div>
      {note ? (
        <p
          style={{
            margin: '0 0 16px', font: 'var(--type-body-sm)', maxWidth: '74ch',
            color: onDark ? 'var(--text-on-dark-body)' : 'var(--text-quiet)',
          }}
        >
          {note}
        </p>
      ) : null}
      {children}
    </section>
  );
}

// ----------------------------------------------------------------- headline --

/**
 * The one sentence a screen is about, with the number it turns on.
 *
 * Deliberately not the big-number-plus-small-label template: the number sits
 * inside the sentence, because on every one of these screens the number means
 * nothing without the clause that qualifies it. "96.13%" is a statistic;
 * "96.13% of credential-bearing payloads were stopped" is a finding.
 */
export function Headline({
  children,
  sub,
  onDark = false,
}: {
  children: React.ReactNode;
  sub?: React.ReactNode;
  onDark?: boolean;
}) {
  return (
    <div>
      <p
        style={{
          margin: 0, maxWidth: '30ch', textWrap: 'balance',
          font: 'var(--w-regular) clamp(24px, 2.4vw, 33px)/var(--lh-snug) var(--font-core)',
          letterSpacing: 'var(--tr-display)',
          color: onDark ? 'var(--ink-inverse)' : 'var(--ink)',
        }}
      >
        {children}
      </p>
      {sub ? (
        <p
          style={{
            margin: '14px 0 0', maxWidth: '58ch', font: 'var(--type-body-sm)',
            color: onDark ? 'var(--text-on-dark-body)' : 'var(--text-quiet)',
          }}
        >
          {sub}
        </p>
      ) : null}
    </div>
  );
}

/** A number set at the ramp's quietest useful weight, for inline use in a Headline. */
export function Figure({ children }: { children: React.ReactNode }) {
  return (
    <span className="zt-nums" style={{ font: 'inherit', fontWeight: 'var(--w-semibold)' }}>
      {children}
    </span>
  );
}

// -------------------------------------------------------------------- notes --

/**
 * A limit on what the number above it proves.
 *
 * Every measurement on these screens has an edge, and the edge is written next to
 * the measurement rather than in a footnote nobody reaches. Dashed, so it never
 * reads as a result.
 */
export function Caveat({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 12px',
        border: '1px dashed var(--border-line)', borderRadius: 'var(--r-8)',
      }}
    >
      <span style={{ color: 'var(--text-faint)', marginTop: 1, flex: '0 0 auto' }}>
        <Icon name="clock" size={14} />
      </span>
      <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>
        {children}
      </p>
    </div>
  );
}

/**
 * Where the numbers on this screen came from.
 *
 * The same line on every measured screen, because the answer is the same on every
 * measured screen and an operator should stop reading it after the first time.
 */
export function Provenance({ scope }: { scope?: string }) {
  const { records, spans_scanned, wall_seconds, engines, corpus_seed } = run.meta;
  return (
    <p
      className="zt-mono-sm"
      style={{
        margin: 0, color: 'var(--text-faint)', paddingTop: 18,
        boxShadow: 'inset 0 1px 0 var(--border-hairline)', lineHeight: 1.7,
      }}
    >
      {scope ? `${scope} · ` : ''}
      {exact(records)} synthetic payloads · {compact(spans_scanned)} spans ·{' '}
      {wall_seconds.toFixed(0)}s · engines {engines} · seed {corpus_seed} ·{' '}
      <Link href="/method" style={{ color: 'var(--text-quiet)' }}>how this was measured</Link>
    </p>
  );
}

// -------------------------------------------------------------------- table --

/** A column definition. `w` is a grid track, so rows and head cannot drift apart. */
export interface Column {
  key: string;
  head: string;
  w: string;
  align?: 'left' | 'right';
}

export function columns(cols: Column[]): string {
  return cols.map((c) => c.w).join(' ');
}

export function TableHead({ cols, onDark = false }: { cols: Column[]; onDark?: boolean }) {
  return (
    <div
      className="zt-eyebrow"
      style={{
        display: 'grid', gridTemplateColumns: columns(cols), gap: 12,
        padding: '10px 16px',
        color: onDark ? 'rgba(242,242,240,0.52)' : undefined,
        boxShadow: `inset 0 -1px 0 ${onDark ? 'var(--border-on-dark)' : 'var(--border-hairline)'}`,
      }}
    >
      {cols.map((c) => (
        <span key={c.key} style={{ textAlign: c.align ?? 'left' }}>{c.head}</span>
      ))}
    </div>
  );
}

/** Two numbers where the second qualifies the first: `96.13%` over `of 1,067,161`. */
export function Pair({
  value,
  of,
  onDark = false,
  size = 21,
}: {
  value: string;
  of: string;
  onDark?: boolean;
  size?: number;
}) {
  return (
    <div>
      <div
        className="zt-nums"
        style={{
          font: `var(--w-semibold) ${size}px/1.1 var(--font-core)`,
          letterSpacing: 'var(--tr-heading)',
          color: onDark ? 'var(--ink-inverse)' : 'var(--ink)',
        }}
      >
        {value}
      </div>
      <div
        className="zt-mono-sm"
        style={{
          marginTop: 5,
          color: onDark ? 'rgba(242,242,240,0.52)' : 'var(--text-quiet)',
        }}
      >
        {of}
      </div>
    </div>
  );
}
