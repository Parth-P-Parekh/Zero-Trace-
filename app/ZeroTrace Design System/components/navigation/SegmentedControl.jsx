import React from 'react';
import { StatusDot } from '../core/StatusDot.jsx';

/* The floating pill control from the reference chrome: white capsule, hairline,
   soft lift; the selected segment is a solid ink capsule with inverse text. */
export function SegmentedControl({ items = [], value, onChange, size = 'md', floating = false, style, ...rest }) {
  const h = size === 'sm' ? 26 : 32;
  return (
    <div
      role="tablist"
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 2, padding: 3,
        borderRadius: 'var(--r-pill)', background: 'var(--white)',
        boxShadow: floating ? 'inset 0 0 0 1px var(--border-hairline), var(--sh-3)' : 'inset 0 0 0 1px var(--border-hairline)',
        ...style,
      }}
      {...rest}
    >
      {items.map((it) => {
        const v = typeof it === 'string' ? it : it.value;
        const l = typeof it === 'string' ? it : it.label;
        const dot = typeof it === 'object' ? it.dot : undefined;
        const on = v === value;
        return (
          <button
            key={v}
            role="tab"
            aria-selected={on}
            onClick={() => onChange && onChange(v)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              height: h, padding: `0 ${size === 'sm' ? 11 : 14}px`,
              border: 'none', cursor: 'pointer', borderRadius: 'var(--r-pill)',
              background: on ? 'var(--ink)' : 'transparent',
              color: on ? 'var(--ink-inverse)' : 'var(--text-body)',
              font: size === 'sm' ? 'var(--type-eyebrow)' : 'var(--type-label)',
              letterSpacing: 0,
              transition: 'background-color var(--d-fast) var(--ease-out), color var(--d-fast) var(--ease-out)',
            }}
          >
            {dot ? <StatusDot state={dot} size={6} /> : null}
            {l}
          </button>
        );
      })}
    </div>
  );
}
