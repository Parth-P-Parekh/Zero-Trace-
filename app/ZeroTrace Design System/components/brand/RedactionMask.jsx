import React from 'react';

/* The product's core visual act: a filled block at ramp .11 with a .36 hairline
   rule, sized to the character run it replaces. Never a lock, blur or asterisk. */
export function RedactionMask({
  children,
  length,
  type,
  revealed = false,
  animate = false,
  tone = 'ink',
  style,
  ...rest
}) {
  const text = typeof children === 'string' ? children : '';
  const chars = length ?? text.length ?? 8;
  const onDark = tone === 'inverse';

  if (revealed) {
    return (
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'inherit', ...style }} {...rest}>
        {text}
      </span>
    );
  }

  return (
    <span
      title={type ? `redacted: ${type}` : 'redacted'}
      style={{
        position: 'relative',
        display: 'inline-block',
        verticalAlign: 'baseline',
        fontFamily: 'var(--font-mono)',
        fontSize: 'inherit',
        lineHeight: 'inherit',
        color: 'transparent',
        background: onDark ? 'rgba(242,242,240,0.11)' : 'var(--redact-fill)',
        boxShadow: `inset 0 0 0 1px ${onDark ? 'rgba(242,242,240,0.36)' : 'var(--redact-rule)'}`,
        borderRadius: 2,
        padding: '0 0.1em',
        animation: animate ? 'zt-sweep var(--d-drain) var(--ease-out) both' : undefined,
      }}
      {...rest}
    >
      {'\u2588'.repeat(Math.max(1, chars))}
      {type ? (
        <span
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '0.72em',
            letterSpacing: '0.06em',
            color: onDark ? 'rgba(242,242,240,0.52)' : 'var(--text-quiet)',
          }}
        >
          {chars >= type.length + 4 ? type : ''}
        </span>
      ) : null}
    </span>
  );
}
