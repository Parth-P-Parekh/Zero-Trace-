import React from 'react';
import { StatusDot } from './StatusDot.jsx';

export function Badge({ children, status, tone = 'neutral', onDark = false, style, ...rest }) {
  const map = {
    neutral: { bg: onDark ? 'rgba(242,242,240,0.09)' : 'rgba(17,17,17,0.05)', fg: onDark ? 'var(--text-on-dark-body)' : 'var(--text-body)' },
    clean: { bg: 'var(--signal-clean-soft)', fg: 'var(--signal-clean)' },
    redacted: { bg: 'var(--signal-redacted-soft)', fg: 'var(--signal-redacted)' },
    blocked: { bg: 'var(--signal-blocked-soft)', fg: 'var(--signal-blocked)' },
    info: { bg: 'var(--signal-info-soft)', fg: 'var(--signal-info)' },
    ink: { bg: 'var(--ink)', fg: 'var(--ink-inverse)' },
  }[tone];
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        height: 22,
        padding: '0 9px',
        borderRadius: 'var(--r-pill)',
        background: map.bg,
        color: map.fg,
        font: 'var(--type-eyebrow)',
        letterSpacing: 0,
        whiteSpace: 'nowrap',
        ...style,
      }}
      {...rest}
    >
      {status ? <StatusDot state={status} size={6} /> : null}
      {children}
    </span>
  );
}
