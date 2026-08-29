import React from 'react';
import { RedactionMask } from '../brand/RedactionMask.jsx';
import { Badge } from '../core/Badge.jsx';
import { IconButton } from '../core/IconButton.jsx';
import { StatusDot } from '../core/StatusDot.jsx';

function renderPart(part, i, animate) {
  if (typeof part === 'string') return <span key={i}>{part}</span>;
  return <RedactionMask key={i} type={part.type} length={part.length} animate={animate} tone="inverse">{part.mask}</RedactionMask>;
}

/* The console's focal surface: the outbound payload as it leaves, with a
   scanline crossing it while the sweep runs. */
export function PayloadView({ id, method = 'POST', path = '/v1/chat/completions', model, lines = [], status = 'redacted', latency, scanning = false, onCopy, style, ...rest }) {
  return (
    <div
      style={{
        background: 'var(--surface-code)', color: 'var(--ink-inverse)',
        borderRadius: 'var(--r-12)', boxShadow: 'var(--sh-3)', overflow: 'hidden', ...style,
      }}
      {...rest}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 12px 12px 16px', boxShadow: 'inset 0 -1px 0 var(--border-on-dark)' }}>
        <StatusDot state={scanning ? 'ink' : status} size={6} live={scanning} style={scanning ? { background: 'var(--ink-inverse)' } : undefined} />
        <span style={{ font: 'var(--type-mono-sm)', color: 'var(--text-on-dark-body)' }}>{method} {path}</span>
        <span style={{ flex: 1 }} />
        {model ? <Badge onDark>{model}</Badge> : null}
        {latency ? <span style={{ font: 'var(--type-mono-sm)', color: 'var(--text-on-dark-quiet)' }}>{latency}</span> : null}
        {onCopy ? <IconButton name="copy" label="Copy payload" size={24} onDark onClick={onCopy} /> : null}
      </div>
      <div style={{ position: 'relative', padding: '14px 16px 16px', font: 'var(--type-mono)', letterSpacing: 'var(--tr-mono)', lineHeight: 1.62, overflowX: 'auto' }}>
        {lines.map((line, i) => {
          const parts = Array.isArray(line) ? line : [line];
          return (
            <div key={i} style={{ whiteSpace: 'pre', color: 'var(--text-on-dark-body)' }}>
              {parts.map((p, j) => renderPart(p, j, scanning))}
            </div>
          );
        })}
        {scanning ? (
          <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none' }}>
            <div style={{ position: 'absolute', top: 0, bottom: 0, width: 120, background: 'linear-gradient(90deg,rgba(242,242,240,0),rgba(242,242,240,0.06),rgba(242,242,240,0))', animation: 'zt-scan 1.6s var(--ease-linear) infinite' }} />
          </div>
        ) : null}
        {id ? (
          <div style={{ marginTop: 12, font: 'var(--type-mono-sm)', color: 'var(--text-on-dark-quiet)' }}>{id}</div>
        ) : null}
      </div>
    </div>
  );
}
