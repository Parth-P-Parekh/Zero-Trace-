import React from 'react';

/* Lucide (ISC) is a flagged substitution — ZeroTrace ships no icon set.
   Rendered as a CSS mask so the glyph always inherits currentColor, i.e. the
   ramp stop of the text it sits with. */
const BASE = 'https://unpkg.com/lucide-static@0.454.0/icons/';

export function Icon({ name, size = 16, style, ...rest }) {
  const url = `url("${BASE}${name}.svg")`;
  return (
    <span
      aria-hidden="true"
      style={{
        display: 'inline-block',
        flex: '0 0 auto',
        width: size,
        height: size,
        background: 'currentColor',
        WebkitMaskImage: url,
        maskImage: url,
        WebkitMaskRepeat: 'no-repeat',
        maskRepeat: 'no-repeat',
        WebkitMaskSize: 'contain',
        maskSize: 'contain',
        WebkitMaskPosition: 'center',
        maskPosition: 'center',
        ...style,
      }}
      {...rest}
    />
  );
}
