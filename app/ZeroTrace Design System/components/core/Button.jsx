import React from 'react';
import { Icon } from './Icon.jsx';

const SIZES = {
  sm: { h: 30, px: 12, font: 'var(--type-label)', gap: 6, r: 'var(--r-6)' },
  md: { h: 36, px: 16, font: 'var(--type-body-sm)', gap: 8, r: 'var(--r-8)' },
  lg: { h: 44, px: 22, font: 'var(--type-body)', gap: 8, r: 'var(--r-8)' },
};

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  icon,
  iconEnd,
  pill = false,
  disabled = false,
  full = false,
  onDark = false,
  style,
  ...rest
}) {
  const s = SIZES[size] || SIZES.md;
  const [hover, setHover] = React.useState(false);
  const [down, setDown] = React.useState(false);

  const v = {
    primary: {
      background: down ? 'var(--surface-dark)' : hover ? '#2A2A28' : 'var(--ink)',
      color: 'var(--ink-inverse)',
      boxShadow: 'none',
    },
    secondary: {
      background: onDark ? '#1D1D1C' : 'var(--white)',
      color: onDark ? 'var(--ink-inverse)' : 'var(--ink)',
      boxShadow: `inset 0 0 0 1px ${onDark ? 'rgba(242,242,240,0.22)' : 'rgba(17,17,17,0.22)'}${hover ? '' : ''}`,
      backgroundImage: down
        ? `linear-gradient(rgba(17,17,17,0.06),rgba(17,17,17,0.06))`
        : hover
        ? `linear-gradient(rgba(17,17,17,0.03),rgba(17,17,17,0.03))`
        : 'none',
    },
    ghost: {
      background: down
        ? onDark ? 'rgba(242,242,240,0.11)' : 'rgba(17,17,17,0.09)'
        : hover
        ? onDark ? 'rgba(242,242,240,0.07)' : 'rgba(17,17,17,0.05)'
        : 'transparent',
      color: onDark ? 'var(--ink-inverse)' : 'var(--ink)',
      boxShadow: 'none',
    },
    inverse: {
      background: down ? '#D8D8D5' : hover ? '#E8E8E6' : 'var(--ink-inverse)',
      color: 'var(--ink)',
      boxShadow: 'none',
    },
  }[variant];

  return (
    <button
      type="button"
      disabled={disabled}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => { setHover(false); setDown(false); }}
      onMouseDown={() => setDown(true)}
      onMouseUp={() => setDown(false)}
      style={{
        display: full ? 'flex' : 'inline-flex',
        width: full ? '100%' : undefined,
        alignItems: 'center',
        justifyContent: 'center',
        gap: s.gap,
        height: s.h,
        padding: `0 ${s.px}px`,
        font: s.font,
        letterSpacing: 0,
        border: 'none',
        borderRadius: pill ? 'var(--r-pill)' : s.r,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.36 : 1,
        transition: 'background-color var(--d-fast) var(--ease-out), box-shadow var(--d-fast) var(--ease-out)',
        whiteSpace: 'nowrap',
        ...v,
        ...style,
      }}
      {...rest}
    >
      {icon ? <Icon name={icon} size={size === 'sm' ? 14 : 16} /> : null}
      {children}
      {iconEnd ? <Icon name={iconEnd} size={size === 'sm' ? 14 : 16} /> : null}
    </button>
  );
}
