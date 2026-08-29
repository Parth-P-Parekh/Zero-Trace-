import React from 'react';
import { Icon } from '../core/Icon.jsx';

export function EmptyState({ icon = 'scan-line', title, description, action, style, ...rest }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 8, padding: '56px 24px', ...style }} {...rest}>
      <Icon name={icon} size={22} style={{ opacity: 0.22, marginBottom: 4 }} />
      <span style={{ font: 'var(--type-h3)', letterSpacing: 'var(--tr-heading)' }}>{title}</span>
      {description ? <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '44ch' }}>{description}</span> : null}
      {action ? <div style={{ marginTop: 12 }}>{action}</div> : null}
    </div>
  );
}
