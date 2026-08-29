import React from 'react';

export function Metric({ label, value, unit, note, size = 'md', onDark = false, style, ...rest }) {
  const fs = size === 'lg' ? 'var(--t-42)' : size === 'sm' ? 'var(--t-21)' : 'var(--t-33)';
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, ...style }} {...rest}>
      <span style={{ font: 'var(--type-eyebrow)', letterSpacing: 'var(--tr-caps)', textTransform: 'uppercase', color: onDark ? 'var(--text-on-dark-quiet)' : 'var(--text-quiet)' }}>{label}</span>
      <span style={{ display: 'flex', alignItems: 'baseline', gap: 5, fontFamily: 'var(--font-core)', fontWeight: 600, fontSize: fs, lineHeight: 1.06, letterSpacing: 'var(--tr-display)', color: onDark ? 'var(--ink-inverse)' : 'var(--ink)' }}>
        {value}
        {unit ? <span style={{ fontSize: '0.42em', fontWeight: 400, letterSpacing: 0, opacity: 0.52 }}>{unit}</span> : null}
      </span>
      {note ? <span style={{ font: 'var(--type-body-sm)', color: onDark ? 'var(--text-on-dark-quiet)' : 'var(--text-quiet)' }}>{note}</span> : null}
    </div>
  );
}
