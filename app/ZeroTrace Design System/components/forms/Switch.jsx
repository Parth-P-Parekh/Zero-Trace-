import React from 'react';

export function Switch({ label, hint, checked = false, onChange, disabled = false, onDark = false, style, ...rest }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.36 : 1, ...style }}>
      <input type="checkbox" role="switch" checked={checked} onChange={onChange} disabled={disabled} style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }} {...rest} />
      <span
        aria-hidden="true"
        style={{
          position: 'relative', flex: '0 0 auto', width: 34, height: 20,
          borderRadius: 'var(--r-pill)',
          background: checked ? (onDark ? 'var(--ink-inverse)' : 'var(--ink)') : onDark ? 'rgba(242,242,240,0.22)' : 'rgba(17,17,17,0.22)',
          transition: 'background-color var(--d-base) var(--ease-in-out)',
        }}
      >
        <span
          style={{
            position: 'absolute', top: 3, left: checked ? 17 : 3, width: 14, height: 14,
            borderRadius: '50%',
            background: checked ? (onDark ? 'var(--ink)' : 'var(--white)') : 'var(--white)',
            boxShadow: 'var(--sh-1)',
            transition: 'left var(--d-base) var(--ease-in-out)',
          }}
        />
      </span>
      {label || hint ? (
        <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {label ? <span style={{ font: 'var(--type-body-sm)' }}>{label}</span> : null}
          {hint ? <span style={{ font: 'var(--type-eyebrow)', color: 'var(--text-quiet)' }}>{hint}</span> : null}
        </span>
      ) : null}
    </label>
  );
}
