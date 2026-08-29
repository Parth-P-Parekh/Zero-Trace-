import React from 'react';

const RAMP = [1, 1, 1, 1, 0.72, 0.52, 0.36, 0.22, 0.11];
const LETTERS = ['Z', 'E', 'R', 'O', 'T', 'R', 'A', 'C', 'E'];

/* Stand-in for the outlined SVGs listed in logo sheet §07, which were not supplied.
   Geometry follows the sheet: Inter Regular, all caps, +0.04em tracking. */
export function Wordmark({
  size = 24,
  tone = 'ink',
  variant = 'primary',
  descriptor,
  drain = false,
  clearspace = false,
  style,
  ...rest
}) {
  const color =
    tone === 'inverse' ? 'var(--ink-inverse)' : tone === 'current' ? 'currentColor' : 'var(--ink)';
  const mono = variant === 'mono' || size < 13;

  return (
    <span
      aria-label="ZeroTrace"
      role="img"
      style={{
        display: 'inline-flex',
        flexDirection: descriptor ? 'column' : 'row',
        alignItems: 'flex-start',
        gap: descriptor ? '0.42em' : 0,
        padding: clearspace ? '0.6em' : 0,
        fontFamily: 'var(--font-core)',
        fontWeight: 400,
        fontSize: size,
        lineHeight: 1,
        letterSpacing: '0.04em',
        color,
        whiteSpace: 'nowrap',
        ...style,
      }}
      {...rest}
    >
      <span style={{ display: 'inline-flex' }} aria-hidden="true">
        {LETTERS.map((ch, i) => (
          <span
            key={i}
            style={{
              opacity: mono ? 1 : RAMP[i],
              animation: drain && !mono ? `zt-drain var(--d-drain) var(--ease-out) both` : undefined,
              animationDelay: drain ? `${i * 34}ms` : undefined,
            }}
          >
            {ch}
          </span>
        ))}
      </span>
      {descriptor ? (
        <span
          style={{
            fontSize: '0.34em',
            letterSpacing: '0.12em',
            fontWeight: 500,
            color: 'var(--muted)',
            textTransform: 'uppercase',
          }}
        >
          {descriptor}
        </span>
      ) : null}
    </span>
  );
}
