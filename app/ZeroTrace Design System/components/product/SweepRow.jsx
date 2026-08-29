import React from 'react';
import { Badge } from '../core/Badge.jsx';
import { Icon } from '../core/Icon.jsx';

const LABEL = { clean: 'Clean', redacted: 'Redacted', blocked: 'Blocked', idle: 'Pending' };

export function SweepRow({ time, path, model, findings = [], status = 'clean', latency, active = false, onClick, style, ...rest }) {
  const [hover, setHover] = React.useState(false);
  const types = findings.map((f) => (typeof f === 'string' ? f : f && f.type)).filter(Boolean);
  return (
    <div
      role="row"
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'grid',
        gridTemplateColumns: '78px 1fr 96px 150px 74px 64px 20px',
        alignItems: 'center',
        gap: 12,
        height: 40,
        padding: '0 12px',
        cursor: onClick ? 'pointer' : undefined,
        background: active ? 'rgba(17,17,17,0.05)' : hover ? 'rgba(17,17,17,0.025)' : 'transparent',
        boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
        transition: 'background-color var(--d-fast) var(--ease-out)',
        ...style,
      }}
      {...rest}
    >
      <span style={{ font: 'var(--type-mono-sm)', color: 'var(--text-faint)' }}>{time}</span>
      <span style={{ font: 'var(--type-mono-sm)', color: 'var(--text-body)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{path}</span>
      <span style={{ font: 'var(--type-eyebrow)', color: 'var(--text-quiet)' }}>{model}</span>
      <span style={{ display: 'flex', gap: 5, overflow: 'hidden' }}>
        {types.length ? (
          types.slice(0, 2).map((t, i) => <Badge key={t + i} tone="neutral">{t}</Badge>)
        ) : (
          <span style={{ font: 'var(--type-eyebrow)', color: 'var(--text-faint)' }}>—</span>
        )}
        {types.length > 2 ? <Badge tone="neutral">+{types.length - 2}</Badge> : null}
      </span>
      <Badge tone={status} status={status}>{LABEL[status] || status}</Badge>
      <span style={{ font: 'var(--type-mono-sm)', color: 'var(--text-faint)', textAlign: 'right', whiteSpace: 'nowrap' }}>{latency}</span>
      <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
        <Icon name="chevron-right" size={14} style={{ opacity: hover ? 0.52 : 0.22 }} />
      </span>
    </div>
  );
}
