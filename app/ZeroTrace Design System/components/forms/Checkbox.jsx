import React from 'react';

export function Checkbox({ label, hint, checked, onChange, disabled = false, style, ...rest }) {
  return (
    <label style={{ display: 'flex', alignItems: 'flex-start', gap: 9, cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.36 : 1, ...style }}>
      <input type="checkbox" checked={checked} onChange={onChange} disabled={disabled} style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }} {...rest} />
      <span
        aria-hidden="true"
        style={{
          flex: '0 0 auto',
          width: 16,
          height: 16,
          marginTop: 1,
          borderRadius: 'var(--r-4)',
          background: checked ? 'var(--ink)' : 'var(--white)',
          boxShadow: checked ? 'none' : 'inset 0 0 0 1px var(--border-line)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'var(--t-hover)',
        }}
      >
        {checked ? (
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M1.5 5.2 3.8 7.5 8.5 2.5" stroke="var(--ink-inverse)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>
        ) : null}
      </span>
      <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ font: 'var(--type-body-sm)' }}>{label}</span>
        {hint ? <span style={{ font: 'var(--type-eyebrow)', color: 'var(--text-quiet)' }}>{hint}</span> : null}
      </span>
    </label>
  );
}
