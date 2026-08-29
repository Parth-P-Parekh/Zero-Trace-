import React from 'react';
import { Icon } from './Icon.jsx';

export function IconButton({ name, label, size = 28, onDark = false, active = false, disabled = false, style, ...rest }) {
  const [hover, setHover] = React.useState(false);
  const wash = onDark ? 'rgba(242,242,240,0.09)' : 'rgba(17,17,17,0.05)';
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: size,
        height: size,
        border: 'none',
        borderRadius: 'var(--r-6)',
        background: active ? wash : hover ? wash : 'transparent',
        color: active ? 'currentColor' : 'inherit',
        opacity: disabled ? 0.36 : active ? 1 : hover ? 1 : 0.72,
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'var(--t-hover)',
        ...style,
      }}
      {...rest}
    >
      <Icon name={name} size={Math.round(size * 0.57)} />
    </button>
  );
}
