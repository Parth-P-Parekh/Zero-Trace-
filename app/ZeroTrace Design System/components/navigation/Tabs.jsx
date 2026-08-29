import React from 'react';

export function Tabs({ items = [], value, onChange, onDark = false, style, ...rest }) {
  return (
    <div role="tablist" style={{ display: 'flex', gap: 20, boxShadow: `inset 0 -1px 0 ${onDark ? 'var(--border-on-dark)' : 'var(--border-hairline)'}`, ...style }} {...rest}>
      {items.map((it) => {
        const v = typeof it === 'string' ? it : it.value;
        const l = typeof it === 'string' ? it : it.label;
        const count = typeof it === 'object' ? it.count : undefined;
        const on = v === value;
        return (
          <button
            key={v}
            role="tab"
            aria-selected={on}
            onClick={() => onChange && onChange(v)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '0 0 10px', border: 'none', background: 'none', cursor: 'pointer',
              font: 'var(--type-body-sm)',
              color: on ? (onDark ? 'var(--ink-inverse)' : 'var(--ink)') : onDark ? 'var(--text-on-dark-quiet)' : 'var(--text-quiet)',
              boxShadow: on ? `inset 0 -2px 0 ${onDark ? 'var(--ink-inverse)' : 'var(--ink)'}` : 'none',
              transition: 'var(--t-hover)',
            }}
          >
            {l}
            {count !== undefined ? <span style={{ font: 'var(--type-mono-sm)', opacity: 0.52 }}>({count})</span> : null}
          </button>
        );
      })}
    </div>
  );
}
