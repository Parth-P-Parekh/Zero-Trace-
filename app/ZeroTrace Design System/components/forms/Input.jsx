import React from 'react';
import { Icon } from '../core/Icon.jsx';

export function Input({ label, hint, error, icon, mono = false, prefix, size = 'md', style, ...rest }) {
  const [focus, setFocus] = React.useState(false);
  const h = size === 'sm' ? 30 : 36;
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 6, ...style }}>
      {label ? <span style={{ font: 'var(--type-label)', color: 'var(--text-body)' }}>{label}</span> : null}
      <span
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          height: h,
          padding: '0 10px',
          background: 'var(--white)',
          borderRadius: 'var(--r-4)',
          boxShadow: error
            ? 'inset 0 0 0 1px var(--signal-blocked)'
            : focus
            ? 'inset 0 0 0 1px var(--ink), var(--sh-focus)'
            : 'inset 0 0 0 1px var(--border-line)',
          transition: 'box-shadow var(--d-fast) var(--ease-out)',
        }}
      >
        {icon ? <Icon name={icon} size={14} style={{ opacity: 0.52 }} /> : null}
        {prefix ? <span style={{ font: 'var(--type-mono-sm)', color: 'var(--text-faint)' }}>{prefix}</span> : null}
        <input
          onFocus={() => setFocus(true)}
          onBlur={() => setFocus(false)}
          style={{
            flex: 1,
            minWidth: 0,
            border: 'none',
            outline: 'none',
            background: 'transparent',
            font: mono ? 'var(--type-mono)' : 'var(--type-body-sm)',
            letterSpacing: mono ? 'var(--tr-mono)' : 0,
            color: 'var(--ink)',
          }}
          {...rest}
        />
      </span>
      {error ? (
        <span style={{ font: 'var(--type-eyebrow)', color: 'var(--signal-blocked)' }}>{error}</span>
      ) : hint ? (
        <span style={{ font: 'var(--type-eyebrow)', color: 'var(--text-quiet)' }}>{hint}</span>
      ) : null}
    </label>
  );
}
