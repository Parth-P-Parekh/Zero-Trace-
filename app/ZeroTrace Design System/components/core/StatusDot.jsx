import React from 'react';

const STATES = {
  clean: 'var(--signal-clean)',
  redacted: 'var(--signal-redacted)',
  blocked: 'var(--signal-blocked)',
  info: 'var(--signal-info)',
  idle: 'var(--n-4)',
  ink: 'var(--ink)',
};

export function StatusDot({ state = 'idle', size = 6, live = false, style, ...rest }) {
  return (
    <span
      style={{
        display: 'inline-block',
        flex: '0 0 auto',
        width: size,
        height: size,
        borderRadius: '50%',
        background: STATES[state] || STATES.idle,
        animation: live ? 'zt-pulse 1.6s var(--ease-in-out) infinite' : undefined,
        ...style,
      }}
      {...rest}
    />
  );
}
