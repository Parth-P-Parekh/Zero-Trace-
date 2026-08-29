import React from 'react';
import { Icon } from '../core/Icon.jsx';

export function Select({ label, hint, options = [], size = 'md', style, ...rest }) {
  const [focus, setFocus] = React.useState(false);
  const h = size === 'sm' ? 30 : 36;
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 6, ...style }}>
      {label ? <span style={{ font: 'var(--type-label)', color: 'var(--text-body)' }}>{label}</span> : null}
      <span
        style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          height: h,
          background: 'var(--white)',
          borderRadius: 'var(--r-4)',
          boxShadow: focus ? 'inset 0 0 0 1px var(--ink), var(--sh-focus)' : 'inset 0 0 0 1px var(--border-line)',
          transition: 'box-shadow var(--d-fast) var(--ease-out)',
        }}
      >
        <select
          onFocus={() => setFocus(true)}
          onBlur={() => setFocus(false)}
          style={{ flex: 1, height: '100%', padding: '0 30px 0 10px', border: 'none', outline: 'none', background: 'transparent', font: 'var(--type-body-sm)', color: 'var(--ink)', appearance: 'none', cursor: 'pointer' }}
          {...rest}
        >
          {options.map((o) => {
            const v = typeof o === 'string' ? o : o.value;
            const l = typeof o === 'string' ? o : o.label;
            return <option key={v} value={v}>{l}</option>;
          })}
        </select>
        <Icon name="chevron-down" size={14} style={{ position: 'absolute', right: 10, opacity: 0.52, pointerEvents: 'none' }} />
      </span>
      {hint ? <span style={{ font: 'var(--type-eyebrow)', color: 'var(--text-quiet)' }}>{hint}</span> : null}
    </label>
  );
}
