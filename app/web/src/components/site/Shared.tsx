/**
 * Primitives for the pitch scroll.
 *
 * The page is one argument told in eight moves, so the parts that repeat are
 * defined once here and the sections spend their variation on composition
 * instead of on chrome. Everything resolves to a design-system token.
 */
import { Fragment } from 'react';
import type { CSSProperties, ReactNode } from 'react';

export const SHELL: CSSProperties = { maxWidth: 1120, margin: '0 auto', padding: '0 32px' };

/** Section grounds. One dark section per beat at most - it is the loudest thing available. */
export type Ground = 'paper' | 'card' | 'dark';

const GROUNDS: Record<Ground, CSSProperties> = {
  paper: {},
  card: {
    background: 'var(--surface-card)',
    boxShadow: 'inset 0 1px 0 var(--border-hairline), inset 0 -1px 0 var(--border-hairline)',
  },
  dark: { background: 'var(--surface-dark)' },
};

export function Section({
  id,
  ground = 'paper',
  children,
  tight,
}: {
  id?: string;
  ground?: Ground;
  children: ReactNode;
  tight?: boolean;
}) {
  return (
    <section id={id} style={{ ...GROUNDS[ground], scrollMarginTop: 64 }}>
      <div style={{ ...SHELL, paddingTop: tight ? 72 : 112, paddingBottom: tight ? 72 : 112 }}>
        {children}
      </div>
    </section>
  );
}

/**
 * The section marker. All-caps 12px at +0.12em is one of exactly two places the
 * system permits caps, and here it is doing wayfinding on a long scroll rather
 * than decorating a heading - the count is the point.
 */
export function SectionHead({
  step,
  title,
  lead,
  onDark,
}: {
  step: string;
  title: ReactNode;
  lead?: ReactNode;
  onDark?: boolean;
}) {
  return (
    <header style={{ marginBottom: 48 }}>
      <div
        className="zt-eyebrow"
        style={{ color: onDark ? 'rgba(242,242,240,0.52)' : 'var(--muted)', marginBottom: 20 }}
      >
        {step}
      </div>
      <h2
        style={{
          font: 'var(--w-regular) clamp(28px, 3.4vw, 42px)/var(--lh-snug) var(--font-core)',
          letterSpacing: 'var(--tr-display)', margin: 0, maxWidth: '22ch',
          color: onDark ? 'var(--ink-inverse)' : 'var(--text-strong)',
          textWrap: 'balance',
        }}
      >
        {title}
      </h2>
      {lead ? (
        <p
          style={{
            font: 'var(--type-body)', margin: '20px 0 0', maxWidth: '64ch',
            color: onDark ? 'var(--text-on-dark-body)' : 'var(--text-body)',
          }}
        >
          {lead}
        </p>
      ) : null}
    </header>
  );
}

/**
 * Inline attribution. GOVW-01's own rule: the source sits next to the number,
 * not in a footer, because a procurement officer will ask and a footnote is an
 * answer they have to go looking for.
 */
export function Source({ children, onDark }: { children: ReactNode; onDark?: boolean }) {
  return (
    <span
      className="zt-mono-sm"
      style={{ color: onDark ? 'rgba(242,242,240,0.36)' : 'var(--text-faint)' }}
    >
      {children}
    </span>
  );
}

/** A figure that is carrying an argument, with its source attached to it. */
export function Stat({
  value,
  unit,
  body,
  detail,
  source,
  onDark,
  size = 'md',
}: {
  value: string;
  unit?: string;
  body: ReactNode;
  /** Optional working, shown under the figure. Lines of [label, value]. */
  detail?: Array<[string, string]>;
  source: string;
  onDark?: boolean;
  size?: 'md' | 'lg';
}) {
  const px = size === 'lg' ? 'clamp(34px, 4.4vw, 54px)' : 'clamp(26px, 2.8vw, 33px)';
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span
          className="zt-nums"
          style={{
            font: `var(--w-semibold) ${px}/var(--lh-tight) var(--font-core)`,
            letterSpacing: 'var(--tr-display)',
            color: onDark ? 'var(--ink-inverse)' : 'var(--text-strong)',
          }}
        >
          {value}
        </span>
        {unit ? (
          <span
            className="zt-mono-sm"
            style={{ color: onDark ? 'var(--text-on-dark-quiet)' : 'var(--text-quiet)' }}
          >
            {unit}
          </span>
        ) : null}
      </div>
      <p
        style={{
          margin: 0, font: 'var(--type-body-sm)', maxWidth: '34ch',
          color: onDark ? 'var(--text-on-dark-body)' : 'var(--text-body)',
        }}
      >
        {body}
      </p>
      {detail ? (
        <div
          className="zt-mono-sm"
          style={{
            display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto', gap: '4px 16px',
            paddingTop: 12, maxWidth: '34ch',
            boxShadow: `inset 0 1px 0 ${onDark ? 'var(--border-on-dark)' : 'var(--border-hairline)'}`,
            color: onDark ? 'var(--text-on-dark-quiet)' : 'var(--text-quiet)',
          }}
        >
          {detail.map(([label, val]) => (
            <Fragment key={label}>
              <span>{label}</span>
              <span style={{ textAlign: 'right', color: onDark ? 'var(--ink-inverse)' : 'var(--ink)' }}>
                {val}
              </span>
            </Fragment>
          ))}
        </div>
      ) : null}
      <Source onDark={onDark}>{source}</Source>
    </div>
  );
}

/**
 * A pull statement. The scroll's punctuation - used where a sentence is doing
 * more work than a paragraph would.
 */
export function Pull({
  children,
  sub,
  onDark,
}: {
  children: ReactNode;
  sub?: ReactNode;
  onDark?: boolean;
}) {
  return (
    <div
      style={{
        paddingTop: 28, marginTop: 8,
        boxShadow: `inset 0 1px 0 ${onDark ? 'var(--border-on-dark)' : 'var(--border-hairline)'}`,
      }}
    >
      <p
        style={{
          font: 'var(--w-regular) clamp(21px, 2.2vw, 26px)/var(--lh-snug) var(--font-core)',
          letterSpacing: 'var(--tr-heading)', margin: 0, maxWidth: '30ch',
          color: onDark ? 'var(--ink-inverse)' : 'var(--text-strong)',
        }}
      >
        {children}
      </p>
      {sub ? (
        <p
          style={{
            font: 'var(--type-body-sm)', margin: '14px 0 0', maxWidth: '58ch',
            color: onDark ? 'var(--text-on-dark-body)' : 'var(--text-quiet)',
          }}
        >
          {sub}
        </p>
      ) : null}
    </div>
  );
}

/** A dense row list. Cards would be the lazy container for content this uniform. */
export function Rows({ children }: { children: ReactNode }) {
  return <div style={{ display: 'flex', flexDirection: 'column' }}>{children}</div>;
}

export function Row({
  lead,
  children,
  meta,
  onDark,
}: {
  lead: ReactNode;
  children: ReactNode;
  meta?: ReactNode;
  onDark?: boolean;
}) {
  return (
    <div
      style={{
        display: 'grid', gridTemplateColumns: 'minmax(160px,240px) minmax(0,1fr) auto',
        gap: 24, padding: '18px 0', alignItems: 'baseline',
        boxShadow: `inset 0 -1px 0 ${onDark ? 'var(--border-on-dark)' : 'var(--border-hairline)'}`,
      }}
    >
      <div
        style={{
          font: 'var(--type-label)',
          color: onDark ? 'var(--ink-inverse)' : 'var(--text-strong)',
        }}
      >
        {lead}
      </div>
      <div
        style={{
          font: 'var(--type-body-sm)',
          color: onDark ? 'var(--text-on-dark-body)' : 'var(--text-body)',
        }}
      >
        {children}
      </div>
      <div style={{ textAlign: 'right' }}>{meta}</div>
    </div>
  );
}
