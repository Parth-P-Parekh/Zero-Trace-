import React from 'react';
import { Button } from '../core/Button.jsx';
import { IconButton } from '../core/IconButton.jsx';

export function Dialog({ open = false, title, description, children, confirmLabel = 'Confirm', cancelLabel = 'Cancel', destructive = false, onConfirm, onCancel, width = 440 }) {
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{ position: 'fixed', inset: 0, zIndex: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(17,17,17,0.36)', animation: 'zt-drain var(--d-base) var(--ease-out)' }}
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ width, maxWidth: '92vw', background: 'var(--surface-card)', borderRadius: 'var(--r-16)', boxShadow: 'var(--sh-4)', padding: 24, animation: 'zt-fade-up var(--d-base) var(--ease-out)' }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
          <h3 style={{ font: 'var(--type-h3)', letterSpacing: 'var(--tr-heading)' }}>{title}</h3>
          <IconButton name="x" label="Close" size={24} onClick={onCancel} />
        </div>
        {description ? <p style={{ marginTop: 8, font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>{description}</p> : null}
        {children ? <div style={{ marginTop: 16 }}>{children}</div> : null}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 24 }}>
          <Button variant="ghost" onClick={onCancel}>{cancelLabel}</Button>
          <Button onClick={onConfirm} style={destructive ? { background: 'var(--signal-blocked)' } : undefined}>{confirmLabel}</Button>
        </div>
      </div>
    </div>
  );
}
