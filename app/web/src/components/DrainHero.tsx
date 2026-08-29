'use client';

/**
 * The signature element, and the only bold move on the site.
 *
 * A real payload line, rendered as the gateway sees it. On load the sensitive
 * runs mask in place, left to right, on the 900ms drain — the same gesture as the
 * wordmark, and the same thing the product actually does. It fires once and never
 * loops; a looping version reads as an animation rather than as an event.
 *
 * Under `prefers-reduced-motion` the masks are simply already there. Nothing
 * jumps, nothing is missed.
 */
import { useEffect, useState } from 'react';

type Part = { text: string } | { mask: string; type: string };

const LINE: Part[] = [
  { text: '{ "role": "user", "content": "Refund for ' },
  { mask: 'Priya Sharma', type: 'person' },
  { text: ', PAN ' },
  { mask: 'ABCPZ1234C', type: 'pan' },
  { text: ', key ' },
  { mask: 'rzp_live_A1b2C3d4E5f6G7', type: 'api key' },
  { text: '" }' },
];

export function DrainHero() {
  const [swept, setSwept] = useState(false);

  useEffect(() => {
    const t = window.setTimeout(() => setSwept(true), 420);
    return () => window.clearTimeout(t);
  }, []);

  let maskIndex = -1;

  return (
    <figure style={{ margin: 0 }}>
      <div
        style={{
          background: 'var(--surface-dark)', borderRadius: 'var(--r-16)', padding: '28px 28px 22px',
          boxShadow: 'var(--sh-3)', overflowX: 'auto',
        }}
      >
        <div
          className="zt-mono"
          style={{
            color: 'var(--text-on-dark-body)', whiteSpace: 'pre', lineHeight: 1.9,
            fontSize: 'clamp(11px, 1.35vw, 14px)',
          }}
        >
          {LINE.map((part, i) => {
            if ('text' in part) return <span key={i}>{part.text}</span>;
            maskIndex += 1;
            return (
              <Mask key={i} value={part.mask} type={part.type} swept={swept} order={maskIndex} />
            );
          })}
        </div>

        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 10, marginTop: 22, paddingTop: 16,
            boxShadow: 'inset 0 1px 0 var(--border-on-dark)',
          }}
        >
          <span
            style={{
              width: 6, height: 6, borderRadius: '50%', background: 'var(--signal-redacted)',
              flex: '0 0 auto',
            }}
          />
          <span className="zt-mono-sm" style={{ color: 'var(--text-on-dark-quiet)' }}>
            (3) values redacted — person, pan, api key. Dispatched in 21 ms.
          </span>
        </div>
      </div>
      <figcaption
        style={{
          font: 'var(--type-body-sm)', color: 'var(--text-quiet)', marginTop: 14, maxWidth: '58ch',
        }}
      >
        The application that sent this was not modified. It resolved the provider domain, the gateway
        answered, and the values were gone before the request left the perimeter.
      </figcaption>
    </figure>
  );
}

function Mask({
  value,
  type,
  swept,
  order,
}: {
  value: string;
  type: string;
  swept: boolean;
  order: number;
}) {
  return (
    <span
      title={`redacted: ${type}`}
      style={{ position: 'relative', display: 'inline-block', whiteSpace: 'pre' }}
    >
      <span style={{ visibility: swept ? 'hidden' : 'visible', color: 'var(--text-on-dark-quiet)' }}>
        {value}
      </span>
      {swept ? (
        <span
          aria-label={`redacted ${type}`}
          className="zt-drain-in"
          style={{
            // Sized to the character run it replaces, not to the line box — a mask
            // as tall as the leading reads as an empty field rather than as ink.
            position: 'absolute', left: 0, right: 0, top: '0.14em', bottom: '0.22em',
            background: 'rgba(242,242,240,0.11)',
            boxShadow: 'inset 0 0 0 1px rgba(242,242,240,0.36)',
            borderRadius: 'var(--r-2)',
            animationDelay: `${order * 120}ms`,
          }}
        />
      ) : null}
    </span>
  );
}
