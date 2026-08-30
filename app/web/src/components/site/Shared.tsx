/**
 * Primitives for the pitch scroll.
 *
 * The page is one argument, so the parts that repeat are defined once here and
 * the sections spend their variation on composition instead of on chrome.
 * Everything resolves to a design-system token.
 *
 * Two things every primitive here carries. First, the reveal: ink arrives left
 * to right, which is the identity's own gesture rather than a second one
 * invented for the scroll. Second, attribution that is a link. A figure a
 * procurement officer cannot check is a figure they will discount, and a
 * source they have to search for is one they will not open.
 */
import type { CSSProperties, ReactNode } from 'react';
import { Reveal } from './Reveal';

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
    <section
      id={id}
      className={ground === 'dark' ? 'zt-on-dark' : undefined}
      style={{ ...GROUNDS[ground], scrollMarginTop: 64 }}
    >
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
      <Reveal
        variant="sweep"
        className="zt-eyebrow"
        style={{ color: onDark ? 'rgba(242,242,240,0.52)' : 'var(--muted)', marginBottom: 20 }}
      >
        {step}
      </Reveal>
      <Reveal
        as="h2"
        variant="sweep"
        delay={1}
        style={{
          font: 'var(--w-regular) clamp(28px, 3.4vw, 42px)/var(--lh-snug) var(--font-core)',
          letterSpacing: 'var(--tr-display)', margin: 0, maxWidth: '22ch',
          color: onDark ? 'var(--ink-inverse)' : 'var(--text-strong)',
          textWrap: 'balance',
        }}
      >
        {title}
      </Reveal>
      {lead ? (
        <Reveal
          as="p"
          delay={2}
          style={{
            font: 'var(--type-body)', margin: '20px 0 0', maxWidth: '64ch',
            color: onDark ? 'var(--text-on-dark-body)' : 'var(--text-body)',
          }}
        >
          {lead}
        </Reveal>
      ) : null}
    </header>
  );
}

/**
 * Inline attribution, and a link when there is one to give.
 *
 * The source sits next to the number rather than in a footer, because the
 * person who will ask is reading the number, not the footer. Where the source
 * is a published document, the citation is the document.
 */
export function Source({
  children,
  href,
  onDark,
}: {
  children: ReactNode;
  href?: string;
  onDark?: boolean;
}) {
  const color = onDark ? 'rgba(242,242,240,0.36)' : 'var(--text-faint)';
  if (!href) {
    return <span className="zt-mono-sm" style={{ color }}>{children}</span>;
  }
  return (
    <a
      className="zt-mono-sm zt-cite"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        color,
        textDecoration: 'underline',
        textDecorationColor: onDark ? 'rgba(242,242,240,0.22)' : 'rgba(17,17,17,0.22)',
        textUnderlineOffset: 3,
      }}
    >
      {children}
    </a>
  );
}

/** A figure that is carrying an argument, with its source attached to it. */
export function Stat({
  value,
  unit,
  body,
  source,
  href,
  onDark,
  size = 'md',
}: {
  value: string;
  unit?: string;
  body: ReactNode;
  source: string;
  href?: string;
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
      <Source href={href} onDark={onDark}>{source}</Source>
    </div>
  );
}
