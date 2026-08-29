import React from 'react';

export function Radio({ label, hint, checked, onChange, name, value, disabled = false, style, ...rest }) {
  return (
    <label style={{ display: 'flex', alignItems: 'flex-start', gap: 9, cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.36 : 1, ...style }}>
      <input type="radio" name={name} value={value} checked={checked} onChange={onChange} disabled={disabled} style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }} {...rest} />
      <span
        aria-hidden="true"
        style={{
          flex: '0 0 auto', width: 16, height: 16, marginTop: 1, borderRadius: '50%',
          background: 'var(--white)',
          boxShadow: checked ? 'inset 0 0 0 5px var(--ink)' : 'inset 0 0 0 1px var(--border-line)',
          transition: 'box-shadow var(--d-fast) var(--ease-out)',
        }}
      />
      <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ font: 'var(--type-body-sm)' }}>{label}</span>
        {hint ? <span style={{ font: 'var(--type-eyebrow)', color: 'var(--text-quiet)' }}>{hint}</span> : null}
      </span>
    </label>
  );
}
