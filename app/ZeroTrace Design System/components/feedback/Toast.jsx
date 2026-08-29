import React from 'react';
import { StatusDot } from '../core/StatusDot.jsx';
import { IconButton } from '../core/IconButton.jsx';

export function Toast({ children, status = 'info', action, onAction, onDismiss, style, ...rest }) {
  return (
    <div
      role="status"
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 10,
        padding: '10px 10px 10px 14px',
        background: 'var(--surface-dark)', color: 'var(--ink-inverse)',
        borderRadius: 'var(--r-8)', boxShadow: 'var(--sh-4)',
        font: 'var(--type-body-sm)',
        animation: 'zt-fade-up var(--d-base) var(--ease-out)',
        ...style,
      }}
      {...rest}
    >
      <StatusDot state={status} size={6} />
      <span style={{ color: 'var(--text-on-dark-body)' }}>{children}</span>
      {action ? (
        <button type="button" onClick={onAction} style={{ border: 'none', background: 'none', color: 'var(--ink-inverse)', cursor: 'pointer', font: 'var(--type-label)', textDecoration: 'underline', textUnderlineOffset: '0.18em' }}>{action}</button>
      ) : null}
      {onDismiss ? <IconButton name="x" label="Dismiss" size={22} onDark onClick={onDismiss} /> : null}
    </div>
  );
}
