import React from 'react';
import { Icon } from '../core/Icon.jsx';

export function RailItem({ icon, label, count, active = false, onClick, onDark = true, style, ...rest }) {
  const [hover, setHover] = React.useState(false);
  const fg = onDark ? 'var(--ink-inverse)' : 'var(--ink)';
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 10, width: '100%',
        height: 34, padding: '0 10px', border: 'none', cursor: 'pointer', textAlign: 'left',
        borderRadius: 'var(--r-6)',
        background: active
          ? onDark ? 'rgba(242,242,240,0.09)' : 'rgba(17,17,17,0.06)'
          : hover
          ? onDark ? 'rgba(242,242,240,0.05)' : 'rgba(17,17,17,0.035)'
          : 'transparent',
        color: fg,
        opacity: active ? 1 : hover ? 0.86 : 0.52,
        font: 'var(--type-body-sm)',
        transition: 'var(--t-hover)',
        ...style,
      }}
      {...rest}
    >
      {icon ? <Icon name={icon} size={16} /> : null}
      <span style={{ flex: 1 }}>{label}</span>
      {count !== undefined ? <span style={{ font: 'var(--type-mono-sm)', opacity: 0.72 }}>{count}</span> : null}
    </button>
  );
}
