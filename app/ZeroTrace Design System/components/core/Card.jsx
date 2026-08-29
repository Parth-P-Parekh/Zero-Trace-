import React from 'react';

export function Card({ children, tone = 'paper', pad = 24, radius, interactive = false, style, ...rest }) {
  const [hover, setHover] = React.useState(false);
  const dark = tone === 'dark';
  const r = radius ?? (tone === 'shell' ? 'var(--r-20)' : 'var(--r-12)');
  const base = {
    paper: { background: 'var(--surface-card)', boxShadow: `inset 0 0 0 1px var(--border-hairline), ${hover && interactive ? 'var(--sh-3)' : 'var(--sh-2)'}` },
    sunken: { background: 'var(--surface-sunken)', boxShadow: 'inset 0 0 0 1px var(--border-hairline)' },
    dark: { background: 'var(--surface-card-dark)', color: 'var(--ink-inverse)', boxShadow: hover && interactive ? 'var(--sh-4)' : 'var(--sh-3)' },
    shell: { background: 'var(--surface-card)', boxShadow: 'var(--sh-4)' },
  }[tone];
  return (
    <div
      onMouseEnter={interactive ? () => setHover(true) : undefined}
      onMouseLeave={interactive ? () => setHover(false) : undefined}
      style={{
        borderRadius: r,
        padding: pad,
        transition: 'box-shadow var(--d-base) var(--ease-out)',
        cursor: interactive ? 'pointer' : undefined,
        ...base,
        ...style,
      }}
      {...rest}
    >
      {children}
    </div>
  );
}
