import React from 'react';

export function Tooltip({ label, children, side = 'top', mono = false, style }) {
  const [on, setOn] = React.useState(false);
  const pos = {
    top: { bottom: '100%', left: '50%', transform: 'translateX(-50%)', marginBottom: 6 },
    bottom: { top: '100%', left: '50%', transform: 'translateX(-50%)', marginTop: 6 },
    left: { right: '100%', top: '50%', transform: 'translateY(-50%)', marginRight: 6 },
    right: { left: '100%', top: '50%', transform: 'translateY(-50%)', marginLeft: 6 },
  }[side];
  return (
    <span
      style={{ position: 'relative', display: 'inline-flex', ...style }}
      onMouseEnter={() => setOn(true)}
      onMouseLeave={() => setOn(false)}
      onFocus={() => setOn(true)}
      onBlur={() => setOn(false)}
    >
      {children}
      {on ? (
        <span
          role="tooltip"
          style={{
            position: 'absolute', zIndex: 50, ...pos,
            padding: '5px 8px', borderRadius: 'var(--r-4)',
            background: 'var(--surface-dark)', color: 'var(--ink-inverse)',
            font: mono ? 'var(--type-mono-sm)' : 'var(--type-eyebrow)',
            letterSpacing: mono ? 'var(--tr-mono)' : 0,
            whiteSpace: 'nowrap', pointerEvents: 'none',
            animation: 'zt-drain var(--d-fast) var(--ease-out)',
          }}
        >
          {label}
        </span>
      ) : null}
    </span>
  );
}
