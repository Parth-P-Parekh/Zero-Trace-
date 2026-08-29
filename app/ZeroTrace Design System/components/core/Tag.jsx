import React from 'react';

export function Tag({ children, mono = false, removable = false, onRemove, style, ...rest }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        height: 24,
        padding: removable ? '0 6px 0 10px' : '0 10px',
        borderRadius: 'var(--r-pill)',
        boxShadow: 'inset 0 0 0 1px var(--border-line)',
        color: 'var(--text-body)',
        font: mono ? 'var(--type-mono-sm)' : 'var(--type-eyebrow)',
        letterSpacing: mono ? 'var(--tr-mono)' : 0,
        background: 'transparent',
        ...style,
      }}
      {...rest}
    >
      {children}
      {removable ? (
        <button
          type="button"
          onClick={onRemove}
          aria-label="Remove"
          style={{ display: 'inline-flex', width: 14, height: 14, alignItems: 'center', justifyContent: 'center', border: 'none', background: 'none', cursor: 'pointer', opacity: 0.52, padding: 0 }}
        >
          ×
        </button>
      ) : null}
    </span>
  );
}
