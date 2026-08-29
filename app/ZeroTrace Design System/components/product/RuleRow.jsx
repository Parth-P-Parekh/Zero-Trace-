import React from 'react';
import { Tag } from '../core/Tag.jsx';
import { Switch } from '../forms/Switch.jsx';
import { IconButton } from '../core/IconButton.jsx';

export function RuleRow({ name, pattern, action = 'Redact', hits, active = true, onToggle, onEdit, style, ...rest }) {
  const [hover, setHover] = React.useState(false);
  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'grid', gridTemplateColumns: '1fr 200px 96px 80px 62px', alignItems: 'center', gap: 12,
        minHeight: 52, padding: '0 12px',
        background: hover ? 'rgba(17,17,17,0.025)' : 'transparent',
        boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
        opacity: active ? 1 : 0.52,
        transition: 'background-color var(--d-fast) var(--ease-out), opacity var(--d-base) var(--ease-out)',
        ...style,
      }}
      {...rest}
    >
      <span style={{ font: 'var(--type-body-sm)' }}>{name}</span>
      <span><Tag mono>{pattern}</Tag></span>
      <span style={{ font: 'var(--type-eyebrow)', color: 'var(--text-quiet)' }}>{action}</span>
      <span style={{ font: 'var(--type-mono-sm)', color: 'var(--text-faint)' }}>{hits}</span>
      <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 4 }}>
        <Switch checked={active} onChange={onToggle} />
        <IconButton name="more-horizontal" label={`Actions for ${name}`} size={24} onClick={onEdit} />
      </span>
    </div>
  );
}
