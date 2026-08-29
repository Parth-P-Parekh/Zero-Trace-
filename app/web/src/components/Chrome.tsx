'use client';

/**
 * Small shared pieces used across console routes. Each one exists because the
 * pattern repeats on three or more screens; anything used twice stays inline.
 */
import { Icon } from '@/ds';

/**
 * The page heading. Display type set large and light, measure capped so it reads
 * as drawn ink rather than a banner. No eyebrow above it — the rail and the
 * topbar already say where you are, and a third label would be decoration.
 */
export function PageHead({
  title,
  sub,
  right,
}: {
  title: string;
  sub?: string;
  right?: React.ReactNode;
}) {
  return (
    <div
      style={{
        display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
        gap: 24, flexWrap: 'wrap',
      }}
    >
      <div style={{ minWidth: 0 }}>
        <h1
          style={{
            font: 'var(--type-h1)', letterSpacing: 'var(--tr-display)',
            maxWidth: '24ch', margin: 0, textWrap: 'balance',
          }}
        >
          {title}
        </h1>
        {sub ? (
          <p
            style={{
              font: 'var(--type-body-sm)', color: 'var(--text-quiet)',
              margin: '8px 0 0', maxWidth: '62ch',
            }}
          >
            {sub}
          </p>
        ) : null}
      </div>
      {right ? <div style={{ flex: '0 0 auto' }}>{right}</div> : null}
    </div>
  );
}

/**
 * A capability that is designed but not built. Stated plainly wherever it would
 * otherwise be implied as working — overclaiming is what loses a security buyer.
 */
export function StubNote({ capability, detail }: { capability: string; detail: string }) {
  return (
    <div
      style={{
        display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 12px',
        border: '1px dashed var(--border-line)', borderRadius: 'var(--r-8)',
        background: 'transparent',
      }}
    >
      <span style={{ color: 'var(--text-faint)', marginTop: 1, flex: '0 0 auto' }}>
        <Icon name="clock" size={14} />
      </span>
      <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>
        <span style={{ color: 'var(--text-body)' }}>{capability} is not built.</span> {detail}
      </p>
    </div>
  );
}

/** A table header row. Columns are passed as a grid template so rows can match it. */
export function GridHead({ columns, cells }: { columns: string; cells: string[] }) {
  return (
    <div
      className="zt-eyebrow"
      style={{
        display: 'grid', gridTemplateColumns: columns, gap: 12, padding: '10px 16px',
        boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
      }}
    >
      {cells.map((c, i) => (
        <span key={i}>{c}</span>
      ))}
    </div>
  );
}

/** Section label inside a card. 12px caps, the system's only other all-caps use. */
export function SectionLabel({ children, onDark }: { children: React.ReactNode; onDark?: boolean }) {
  return (
    <div
      className="zt-eyebrow"
      style={{ color: onDark ? 'rgba(242,242,240,0.52)' : 'var(--muted)', marginBottom: 12 }}
    >
      {children}
    </div>
  );
}
