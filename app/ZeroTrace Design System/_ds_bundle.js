/* @ds-bundle: {"format":4,"namespace":"ZeroTraceDesignSystem_7f4295","components":[{"name":"RedactionMask","sourcePath":"components/brand/RedactionMask.jsx"},{"name":"Wordmark","sourcePath":"components/brand/Wordmark.jsx"},{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Card","sourcePath":"components/core/Card.jsx"},{"name":"Icon","sourcePath":"components/core/Icon.jsx"},{"name":"IconButton","sourcePath":"components/core/IconButton.jsx"},{"name":"Metric","sourcePath":"components/core/Metric.jsx"},{"name":"StatusDot","sourcePath":"components/core/StatusDot.jsx"},{"name":"Tag","sourcePath":"components/core/Tag.jsx"},{"name":"Dialog","sourcePath":"components/feedback/Dialog.jsx"},{"name":"EmptyState","sourcePath":"components/feedback/EmptyState.jsx"},{"name":"Toast","sourcePath":"components/feedback/Toast.jsx"},{"name":"Tooltip","sourcePath":"components/feedback/Tooltip.jsx"},{"name":"Checkbox","sourcePath":"components/forms/Checkbox.jsx"},{"name":"Input","sourcePath":"components/forms/Input.jsx"},{"name":"Radio","sourcePath":"components/forms/Radio.jsx"},{"name":"Select","sourcePath":"components/forms/Select.jsx"},{"name":"Switch","sourcePath":"components/forms/Switch.jsx"},{"name":"RailItem","sourcePath":"components/navigation/RailItem.jsx"},{"name":"SegmentedControl","sourcePath":"components/navigation/SegmentedControl.jsx"},{"name":"Tabs","sourcePath":"components/navigation/Tabs.jsx"},{"name":"PayloadView","sourcePath":"components/product/PayloadView.jsx"},{"name":"RuleRow","sourcePath":"components/product/RuleRow.jsx"},{"name":"SweepRow","sourcePath":"components/product/SweepRow.jsx"}],"sourceHashes":{"components/brand/RedactionMask.jsx":"f8a04ecd79c9","components/brand/Wordmark.jsx":"b6430a228ac9","components/core/Badge.jsx":"61a225218917","components/core/Button.jsx":"f7d1d9cf099a","components/core/Card.jsx":"bfa709e1a24b","components/core/Icon.jsx":"7c3dddeeb630","components/core/IconButton.jsx":"f472451f2771","components/core/Metric.jsx":"d54c3b187472","components/core/StatusDot.jsx":"1cc4fcf72665","components/core/Tag.jsx":"f28f1554bc9a","components/feedback/Dialog.jsx":"a343330f9221","components/feedback/EmptyState.jsx":"cad05470cfcf","components/feedback/Toast.jsx":"857919ecc4c1","components/feedback/Tooltip.jsx":"1039bfba7077","components/forms/Checkbox.jsx":"b5443901863d","components/forms/Input.jsx":"5b92d0ced497","components/forms/Radio.jsx":"93befe34a25a","components/forms/Select.jsx":"ecb912f8107e","components/forms/Switch.jsx":"7a9addb9102e","components/navigation/RailItem.jsx":"476d0ea49a66","components/navigation/SegmentedControl.jsx":"d3be0bb9afe0","components/navigation/Tabs.jsx":"e6f321a0f656","components/product/PayloadView.jsx":"bcd1cd2bf25d","components/product/RuleRow.jsx":"ebf79458323c","components/product/SweepRow.jsx":"6130c08d6d51","ui_kits/console/ConsoleShell.jsx":"1017664cd717","ui_kits/console/Inspector.jsx":"0a29ebeb3edd","ui_kits/console/Integration.jsx":"2edec38d160a","ui_kits/console/PolicyRules.jsx":"443d9bd2b406","ui_kits/console/SweepLog.jsx":"fcbfa901135e","ui_kits/console/data.js":"7ad4269a52fc","ui_kits/marketing/Hero.jsx":"2704546e4496","ui_kits/marketing/HowItWorks.jsx":"5d8bda0fa125","ui_kits/marketing/Install.jsx":"ea06f6168bd5","ui_kits/marketing/Pricing.jsx":"68ea603eb6d8","ui_kits/marketing/SiteFooter.jsx":"094487fc1080","ui_kits/marketing/SiteNav.jsx":"ddd802b6e684"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.ZeroTraceDesignSystem_7f4295 = window.ZeroTraceDesignSystem_7f4295 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/brand/RedactionMask.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* The product's core visual act: a filled block at ramp .11 with a .36 hairline
   rule, sized to the character run it replaces. Never a lock, blur or asterisk. */
function RedactionMask({
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
    return /*#__PURE__*/React.createElement("span", _extends({
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 'inherit',
        ...style
      }
    }, rest), text);
  }
  return /*#__PURE__*/React.createElement("span", _extends({
    title: type ? `redacted: ${type}` : 'redacted',
    style: {
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
      animation: animate ? 'zt-sweep var(--d-drain) var(--ease-out) both' : undefined
    }
  }, rest), '\u2588'.repeat(Math.max(1, chars)), type ? /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      inset: 0,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: '0.72em',
      letterSpacing: '0.06em',
      color: onDark ? 'rgba(242,242,240,0.52)' : 'var(--text-quiet)'
    }
  }, chars >= type.length + 4 ? type : '') : null);
}
Object.assign(__ds_scope, { RedactionMask });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/brand/RedactionMask.jsx", error: String((e && e.message) || e) }); }

// components/brand/Wordmark.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const RAMP = [1, 1, 1, 1, 0.72, 0.52, 0.36, 0.22, 0.11];
const LETTERS = ['Z', 'E', 'R', 'O', 'T', 'R', 'A', 'C', 'E'];

/* Stand-in for the outlined SVGs listed in logo sheet §07, which were not supplied.
   Geometry follows the sheet: Inter Regular, all caps, +0.04em tracking. */
function Wordmark({
  size = 24,
  tone = 'ink',
  variant = 'primary',
  descriptor,
  drain = false,
  clearspace = false,
  style,
  ...rest
}) {
  const color = tone === 'inverse' ? 'var(--ink-inverse)' : tone === 'current' ? 'currentColor' : 'var(--ink)';
  const mono = variant === 'mono' || size < 13;
  return /*#__PURE__*/React.createElement("span", _extends({
    "aria-label": "ZeroTrace",
    role: "img",
    style: {
      display: 'inline-flex',
      flexDirection: descriptor ? 'column' : 'row',
      alignItems: 'flex-start',
      gap: descriptor ? '0.42em' : 0,
      padding: clearspace ? '0.6em' : 0,
      fontFamily: 'var(--font-core)',
      fontWeight: 400,
      fontSize: size,
      lineHeight: 1,
      letterSpacing: '0.04em',
      color,
      whiteSpace: 'nowrap',
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex'
    },
    "aria-hidden": "true"
  }, LETTERS.map((ch, i) => /*#__PURE__*/React.createElement("span", {
    key: i,
    style: {
      opacity: mono ? 1 : RAMP[i],
      animation: drain && !mono ? `zt-drain var(--d-drain) var(--ease-out) both` : undefined,
      animationDelay: drain ? `${i * 34}ms` : undefined
    }
  }, ch))), descriptor ? /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: '0.34em',
      letterSpacing: '0.12em',
      fontWeight: 500,
      color: 'var(--muted)',
      textTransform: 'uppercase'
    }
  }, descriptor) : null);
}
Object.assign(__ds_scope, { Wordmark });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/brand/Wordmark.jsx", error: String((e && e.message) || e) }); }

// components/core/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Card({
  children,
  tone = 'paper',
  pad = 24,
  radius,
  interactive = false,
  style,
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const dark = tone === 'dark';
  const r = radius ?? (tone === 'shell' ? 'var(--r-20)' : 'var(--r-12)');
  const base = {
    paper: {
      background: 'var(--surface-card)',
      boxShadow: `inset 0 0 0 1px var(--border-hairline), ${hover && interactive ? 'var(--sh-3)' : 'var(--sh-2)'}`
    },
    sunken: {
      background: 'var(--surface-sunken)',
      boxShadow: 'inset 0 0 0 1px var(--border-hairline)'
    },
    dark: {
      background: 'var(--surface-card-dark)',
      color: 'var(--ink-inverse)',
      boxShadow: hover && interactive ? 'var(--sh-4)' : 'var(--sh-3)'
    },
    shell: {
      background: 'var(--surface-card)',
      boxShadow: 'var(--sh-4)'
    }
  }[tone];
  return /*#__PURE__*/React.createElement("div", _extends({
    onMouseEnter: interactive ? () => setHover(true) : undefined,
    onMouseLeave: interactive ? () => setHover(false) : undefined,
    style: {
      borderRadius: r,
      padding: pad,
      transition: 'box-shadow var(--d-base) var(--ease-out)',
      cursor: interactive ? 'pointer' : undefined,
      ...base,
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Card.jsx", error: String((e && e.message) || e) }); }

// components/core/Icon.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* Lucide (ISC) is a flagged substitution — ZeroTrace ships no icon set.
   Rendered as a CSS mask so the glyph always inherits currentColor, i.e. the
   ramp stop of the text it sits with. */
const BASE = 'https://unpkg.com/lucide-static@0.454.0/icons/';
function Icon({
  name,
  size = 16,
  style,
  ...rest
}) {
  const url = `url("${BASE}${name}.svg")`;
  return /*#__PURE__*/React.createElement("span", _extends({
    "aria-hidden": "true",
    style: {
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
      ...style
    }
  }, rest));
}
Object.assign(__ds_scope, { Icon });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Icon.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const SIZES = {
  sm: {
    h: 30,
    px: 12,
    font: 'var(--type-label)',
    gap: 6,
    r: 'var(--r-6)'
  },
  md: {
    h: 36,
    px: 16,
    font: 'var(--type-body-sm)',
    gap: 8,
    r: 'var(--r-8)'
  },
  lg: {
    h: 44,
    px: 22,
    font: 'var(--type-body)',
    gap: 8,
    r: 'var(--r-8)'
  }
};
function Button({
  children,
  variant = 'primary',
  size = 'md',
  icon,
  iconEnd,
  pill = false,
  disabled = false,
  full = false,
  onDark = false,
  style,
  ...rest
}) {
  const s = SIZES[size] || SIZES.md;
  const [hover, setHover] = React.useState(false);
  const [down, setDown] = React.useState(false);
  const v = {
    primary: {
      background: down ? 'var(--surface-dark)' : hover ? '#2A2A28' : 'var(--ink)',
      color: 'var(--ink-inverse)',
      boxShadow: 'none'
    },
    secondary: {
      background: onDark ? '#1D1D1C' : 'var(--white)',
      color: onDark ? 'var(--ink-inverse)' : 'var(--ink)',
      boxShadow: `inset 0 0 0 1px ${onDark ? 'rgba(242,242,240,0.22)' : 'rgba(17,17,17,0.22)'}${hover ? '' : ''}`,
      backgroundImage: down ? `linear-gradient(rgba(17,17,17,0.06),rgba(17,17,17,0.06))` : hover ? `linear-gradient(rgba(17,17,17,0.03),rgba(17,17,17,0.03))` : 'none'
    },
    ghost: {
      background: down ? onDark ? 'rgba(242,242,240,0.11)' : 'rgba(17,17,17,0.09)' : hover ? onDark ? 'rgba(242,242,240,0.07)' : 'rgba(17,17,17,0.05)' : 'transparent',
      color: onDark ? 'var(--ink-inverse)' : 'var(--ink)',
      boxShadow: 'none'
    },
    inverse: {
      background: down ? '#D8D8D5' : hover ? '#E8E8E6' : 'var(--ink-inverse)',
      color: 'var(--ink)',
      boxShadow: 'none'
    }
  }[variant];
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    disabled: disabled,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => {
      setHover(false);
      setDown(false);
    },
    onMouseDown: () => setDown(true),
    onMouseUp: () => setDown(false),
    style: {
      display: full ? 'flex' : 'inline-flex',
      width: full ? '100%' : undefined,
      alignItems: 'center',
      justifyContent: 'center',
      gap: s.gap,
      height: s.h,
      padding: `0 ${s.px}px`,
      font: s.font,
      letterSpacing: 0,
      border: 'none',
      borderRadius: pill ? 'var(--r-pill)' : s.r,
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.36 : 1,
      transition: 'background-color var(--d-fast) var(--ease-out), box-shadow var(--d-fast) var(--ease-out)',
      whiteSpace: 'nowrap',
      ...v,
      ...style
    }
  }, rest), icon ? /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: size === 'sm' ? 14 : 16
  }) : null, children, iconEnd ? /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: iconEnd,
    size: size === 'sm' ? 14 : 16
  }) : null);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/IconButton.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function IconButton({
  name,
  label,
  size = 28,
  onDark = false,
  active = false,
  disabled = false,
  style,
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const wash = onDark ? 'rgba(242,242,240,0.09)' : 'rgba(17,17,17,0.05)';
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    "aria-label": label,
    title: label,
    disabled: disabled,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: size,
      height: size,
      border: 'none',
      borderRadius: 'var(--r-6)',
      background: active ? wash : hover ? wash : 'transparent',
      color: active ? 'currentColor' : 'inherit',
      opacity: disabled ? 0.36 : active ? 1 : hover ? 1 : 0.72,
      cursor: disabled ? 'not-allowed' : 'pointer',
      transition: 'var(--t-hover)',
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: name,
    size: Math.round(size * 0.57)
  }));
}
Object.assign(__ds_scope, { IconButton });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/IconButton.jsx", error: String((e && e.message) || e) }); }

// components/core/Metric.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Metric({
  label,
  value,
  unit,
  note,
  size = 'md',
  onDark = false,
  style,
  ...rest
}) {
  const fs = size === 'lg' ? 'var(--t-42)' : size === 'sm' ? 'var(--t-21)' : 'var(--t-33)';
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-eyebrow)',
      letterSpacing: 'var(--tr-caps)',
      textTransform: 'uppercase',
      color: onDark ? 'var(--text-on-dark-quiet)' : 'var(--text-quiet)'
    }
  }, label), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: 5,
      fontFamily: 'var(--font-core)',
      fontWeight: 600,
      fontSize: fs,
      lineHeight: 1.06,
      letterSpacing: 'var(--tr-display)',
      color: onDark ? 'var(--ink-inverse)' : 'var(--ink)'
    }
  }, value, unit ? /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: '0.42em',
      fontWeight: 400,
      letterSpacing: 0,
      opacity: 0.52
    }
  }, unit) : null), note ? /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body-sm)',
      color: onDark ? 'var(--text-on-dark-quiet)' : 'var(--text-quiet)'
    }
  }, note) : null);
}
Object.assign(__ds_scope, { Metric });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Metric.jsx", error: String((e && e.message) || e) }); }

// components/core/StatusDot.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const STATES = {
  clean: 'var(--signal-clean)',
  redacted: 'var(--signal-redacted)',
  blocked: 'var(--signal-blocked)',
  info: 'var(--signal-info)',
  idle: 'var(--n-4)',
  ink: 'var(--ink)'
};
function StatusDot({
  state = 'idle',
  size = 6,
  live = false,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: 'inline-block',
      flex: '0 0 auto',
      width: size,
      height: size,
      borderRadius: '50%',
      background: STATES[state] || STATES.idle,
      animation: live ? 'zt-pulse 1.6s var(--ease-in-out) infinite' : undefined,
      ...style
    }
  }, rest));
}
Object.assign(__ds_scope, { StatusDot });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/StatusDot.jsx", error: String((e && e.message) || e) }); }

// components/core/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Badge({
  children,
  status,
  tone = 'neutral',
  onDark = false,
  style,
  ...rest
}) {
  const map = {
    neutral: {
      bg: onDark ? 'rgba(242,242,240,0.09)' : 'rgba(17,17,17,0.05)',
      fg: onDark ? 'var(--text-on-dark-body)' : 'var(--text-body)'
    },
    clean: {
      bg: 'var(--signal-clean-soft)',
      fg: 'var(--signal-clean)'
    },
    redacted: {
      bg: 'var(--signal-redacted-soft)',
      fg: 'var(--signal-redacted)'
    },
    blocked: {
      bg: 'var(--signal-blocked-soft)',
      fg: 'var(--signal-blocked)'
    },
    info: {
      bg: 'var(--signal-info-soft)',
      fg: 'var(--signal-info)'
    },
    ink: {
      bg: 'var(--ink)',
      fg: 'var(--ink-inverse)'
    }
  }[tone];
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
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
      ...style
    }
  }, rest), status ? /*#__PURE__*/React.createElement(__ds_scope.StatusDot, {
    state: status,
    size: 6
  }) : null, children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Tag.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Tag({
  children,
  mono = false,
  removable = false,
  onRemove,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      height: 24,
      padding: removable ? '0 6px 0 10px' : '0 10px',
      borderRadius: 'var(--r-pill)',
      boxShadow: 'inset 0 0 0 1px var(--border-line)',
      color: 'var(--text-body)',
      font: mono ? 'var(--type-mono-sm)' : 'var(--type-eyebrow)',
      letterSpacing: mono ? 'var(--tr-mono)' : 0,
      background: 'transparent',
      ...style
    }
  }, rest), children, removable ? /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: onRemove,
    "aria-label": "Remove",
    style: {
      display: 'inline-flex',
      width: 14,
      height: 14,
      alignItems: 'center',
      justifyContent: 'center',
      border: 'none',
      background: 'none',
      cursor: 'pointer',
      opacity: 0.52,
      padding: 0
    }
  }, "\xD7") : null);
}
Object.assign(__ds_scope, { Tag });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Tag.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Dialog.jsx
try { (() => {
function Dialog({
  open = false,
  title,
  description,
  children,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  destructive = false,
  onConfirm,
  onCancel,
  width = 440
}) {
  if (!open) return null;
  return /*#__PURE__*/React.createElement("div", {
    role: "dialog",
    "aria-modal": "true",
    style: {
      position: 'fixed',
      inset: 0,
      zIndex: 60,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'rgba(17,17,17,0.36)',
      animation: 'zt-drain var(--d-base) var(--ease-out)'
    },
    onClick: onCancel
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    style: {
      width,
      maxWidth: '92vw',
      background: 'var(--surface-card)',
      borderRadius: 'var(--r-16)',
      boxShadow: 'var(--sh-4)',
      padding: 24,
      animation: 'zt-fade-up var(--d-base) var(--ease-out)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      font: 'var(--type-h3)',
      letterSpacing: 'var(--tr-heading)'
    }
  }, title), /*#__PURE__*/React.createElement(__ds_scope.IconButton, {
    name: "x",
    label: "Close",
    size: 24,
    onClick: onCancel
  })), description ? /*#__PURE__*/React.createElement("p", {
    style: {
      marginTop: 8,
      font: 'var(--type-body-sm)',
      color: 'var(--text-body)'
    }
  }, description) : null, children ? /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 16
    }
  }, children) : null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'flex-end',
      gap: 8,
      marginTop: 24
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Button, {
    variant: "ghost",
    onClick: onCancel
  }, cancelLabel), /*#__PURE__*/React.createElement(__ds_scope.Button, {
    onClick: onConfirm,
    style: destructive ? {
      background: 'var(--signal-blocked)'
    } : undefined
  }, confirmLabel))));
}
Object.assign(__ds_scope, { Dialog });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Dialog.jsx", error: String((e && e.message) || e) }); }

// components/feedback/EmptyState.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function EmptyState({
  icon = 'scan-line',
  title,
  description,
  action,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      textAlign: 'center',
      gap: 8,
      padding: '56px 24px',
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: 22,
    style: {
      opacity: 0.22,
      marginBottom: 4
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-h3)',
      letterSpacing: 'var(--tr-heading)'
    }
  }, title), description ? /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body-sm)',
      color: 'var(--text-quiet)',
      maxWidth: '44ch'
    }
  }, description) : null, action ? /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 12
    }
  }, action) : null);
}
Object.assign(__ds_scope, { EmptyState });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/EmptyState.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Toast.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Toast({
  children,
  status = 'info',
  action,
  onAction,
  onDismiss,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("div", _extends({
    role: "status",
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 10,
      padding: '10px 10px 10px 14px',
      background: 'var(--surface-dark)',
      color: 'var(--ink-inverse)',
      borderRadius: 'var(--r-8)',
      boxShadow: 'var(--sh-4)',
      font: 'var(--type-body-sm)',
      animation: 'zt-fade-up var(--d-base) var(--ease-out)',
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement(__ds_scope.StatusDot, {
    state: status,
    size: 6
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-on-dark-body)'
    }
  }, children), action ? /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: onAction,
    style: {
      border: 'none',
      background: 'none',
      color: 'var(--ink-inverse)',
      cursor: 'pointer',
      font: 'var(--type-label)',
      textDecoration: 'underline',
      textUnderlineOffset: '0.18em'
    }
  }, action) : null, onDismiss ? /*#__PURE__*/React.createElement(__ds_scope.IconButton, {
    name: "x",
    label: "Dismiss",
    size: 22,
    onDark: true,
    onClick: onDismiss
  }) : null);
}
Object.assign(__ds_scope, { Toast });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Toast.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Tooltip.jsx
try { (() => {
function Tooltip({
  label,
  children,
  side = 'top',
  mono = false,
  style
}) {
  const [on, setOn] = React.useState(false);
  const pos = {
    top: {
      bottom: '100%',
      left: '50%',
      transform: 'translateX(-50%)',
      marginBottom: 6
    },
    bottom: {
      top: '100%',
      left: '50%',
      transform: 'translateX(-50%)',
      marginTop: 6
    },
    left: {
      right: '100%',
      top: '50%',
      transform: 'translateY(-50%)',
      marginRight: 6
    },
    right: {
      left: '100%',
      top: '50%',
      transform: 'translateY(-50%)',
      marginLeft: 6
    }
  }[side];
  return /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'relative',
      display: 'inline-flex',
      ...style
    },
    onMouseEnter: () => setOn(true),
    onMouseLeave: () => setOn(false),
    onFocus: () => setOn(true),
    onBlur: () => setOn(false)
  }, children, on ? /*#__PURE__*/React.createElement("span", {
    role: "tooltip",
    style: {
      position: 'absolute',
      zIndex: 50,
      ...pos,
      padding: '5px 8px',
      borderRadius: 'var(--r-4)',
      background: 'var(--surface-dark)',
      color: 'var(--ink-inverse)',
      font: mono ? 'var(--type-mono-sm)' : 'var(--type-eyebrow)',
      letterSpacing: mono ? 'var(--tr-mono)' : 0,
      whiteSpace: 'nowrap',
      pointerEvents: 'none',
      animation: 'zt-drain var(--d-fast) var(--ease-out)'
    }
  }, label) : null);
}
Object.assign(__ds_scope, { Tooltip });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Tooltip.jsx", error: String((e && e.message) || e) }); }

// components/forms/Checkbox.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Checkbox({
  label,
  hint,
  checked,
  onChange,
  disabled = false,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: 9,
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.36 : 1,
      ...style
    }
  }, /*#__PURE__*/React.createElement("input", _extends({
    type: "checkbox",
    checked: checked,
    onChange: onChange,
    disabled: disabled,
    style: {
      position: 'absolute',
      opacity: 0,
      width: 0,
      height: 0
    }
  }, rest)), /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      flex: '0 0 auto',
      width: 16,
      height: 16,
      marginTop: 1,
      borderRadius: 'var(--r-4)',
      background: checked ? 'var(--ink)' : 'var(--white)',
      boxShadow: checked ? 'none' : 'inset 0 0 0 1px var(--border-line)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      transition: 'var(--t-hover)'
    }
  }, checked ? /*#__PURE__*/React.createElement("svg", {
    width: "10",
    height: "10",
    viewBox: "0 0 10 10",
    fill: "none"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M1.5 5.2 3.8 7.5 8.5 2.5",
    stroke: "var(--ink-inverse)",
    strokeWidth: "1.6",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  })) : null), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 2
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body-sm)'
    }
  }, label), hint ? /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-eyebrow)',
      color: 'var(--text-quiet)'
    }
  }, hint) : null));
}
Object.assign(__ds_scope, { Checkbox });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Checkbox.jsx", error: String((e && e.message) || e) }); }

// components/forms/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Input({
  label,
  hint,
  error,
  icon,
  mono = false,
  prefix,
  size = 'md',
  style,
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  const h = size === 'sm' ? 30 : 36;
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      ...style
    }
  }, label ? /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-label)',
      color: 'var(--text-body)'
    }
  }, label) : null, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      height: h,
      padding: '0 10px',
      background: 'var(--white)',
      borderRadius: 'var(--r-4)',
      boxShadow: error ? 'inset 0 0 0 1px var(--signal-blocked)' : focus ? 'inset 0 0 0 1px var(--ink), var(--sh-focus)' : 'inset 0 0 0 1px var(--border-line)',
      transition: 'box-shadow var(--d-fast) var(--ease-out)'
    }
  }, icon ? /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: 14,
    style: {
      opacity: 0.52
    }
  }) : null, prefix ? /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-mono-sm)',
      color: 'var(--text-faint)'
    }
  }, prefix) : null, /*#__PURE__*/React.createElement("input", _extends({
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      flex: 1,
      minWidth: 0,
      border: 'none',
      outline: 'none',
      background: 'transparent',
      font: mono ? 'var(--type-mono)' : 'var(--type-body-sm)',
      letterSpacing: mono ? 'var(--tr-mono)' : 0,
      color: 'var(--ink)'
    }
  }, rest))), error ? /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-eyebrow)',
      color: 'var(--signal-blocked)'
    }
  }, error) : hint ? /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-eyebrow)',
      color: 'var(--text-quiet)'
    }
  }, hint) : null);
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Input.jsx", error: String((e && e.message) || e) }); }

// components/forms/Radio.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Radio({
  label,
  hint,
  checked,
  onChange,
  name,
  value,
  disabled = false,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: 9,
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.36 : 1,
      ...style
    }
  }, /*#__PURE__*/React.createElement("input", _extends({
    type: "radio",
    name: name,
    value: value,
    checked: checked,
    onChange: onChange,
    disabled: disabled,
    style: {
      position: 'absolute',
      opacity: 0,
      width: 0,
      height: 0
    }
  }, rest)), /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      flex: '0 0 auto',
      width: 16,
      height: 16,
      marginTop: 1,
      borderRadius: '50%',
      background: 'var(--white)',
      boxShadow: checked ? 'inset 0 0 0 5px var(--ink)' : 'inset 0 0 0 1px var(--border-line)',
      transition: 'box-shadow var(--d-fast) var(--ease-out)'
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 2
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body-sm)'
    }
  }, label), hint ? /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-eyebrow)',
      color: 'var(--text-quiet)'
    }
  }, hint) : null));
}
Object.assign(__ds_scope, { Radio });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Radio.jsx", error: String((e && e.message) || e) }); }

// components/forms/Select.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Select({
  label,
  hint,
  options = [],
  size = 'md',
  style,
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  const h = size === 'sm' ? 30 : 36;
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      ...style
    }
  }, label ? /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-label)',
      color: 'var(--text-body)'
    }
  }, label) : null, /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'relative',
      display: 'flex',
      alignItems: 'center',
      height: h,
      background: 'var(--white)',
      borderRadius: 'var(--r-4)',
      boxShadow: focus ? 'inset 0 0 0 1px var(--ink), var(--sh-focus)' : 'inset 0 0 0 1px var(--border-line)',
      transition: 'box-shadow var(--d-fast) var(--ease-out)'
    }
  }, /*#__PURE__*/React.createElement("select", _extends({
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      flex: 1,
      height: '100%',
      padding: '0 30px 0 10px',
      border: 'none',
      outline: 'none',
      background: 'transparent',
      font: 'var(--type-body-sm)',
      color: 'var(--ink)',
      appearance: 'none',
      cursor: 'pointer'
    }
  }, rest), options.map(o => {
    const v = typeof o === 'string' ? o : o.value;
    const l = typeof o === 'string' ? o : o.label;
    return /*#__PURE__*/React.createElement("option", {
      key: v,
      value: v
    }, l);
  })), /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "chevron-down",
    size: 14,
    style: {
      position: 'absolute',
      right: 10,
      opacity: 0.52,
      pointerEvents: 'none'
    }
  })), hint ? /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-eyebrow)',
      color: 'var(--text-quiet)'
    }
  }, hint) : null);
}
Object.assign(__ds_scope, { Select });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Select.jsx", error: String((e && e.message) || e) }); }

// components/forms/Switch.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Switch({
  label,
  hint,
  checked = false,
  onChange,
  disabled = false,
  onDark = false,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.36 : 1,
      ...style
    }
  }, /*#__PURE__*/React.createElement("input", _extends({
    type: "checkbox",
    role: "switch",
    checked: checked,
    onChange: onChange,
    disabled: disabled,
    style: {
      position: 'absolute',
      opacity: 0,
      width: 0,
      height: 0
    }
  }, rest)), /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      position: 'relative',
      flex: '0 0 auto',
      width: 34,
      height: 20,
      borderRadius: 'var(--r-pill)',
      background: checked ? onDark ? 'var(--ink-inverse)' : 'var(--ink)' : onDark ? 'rgba(242,242,240,0.22)' : 'rgba(17,17,17,0.22)',
      transition: 'background-color var(--d-base) var(--ease-in-out)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      top: 3,
      left: checked ? 17 : 3,
      width: 14,
      height: 14,
      borderRadius: '50%',
      background: checked ? onDark ? 'var(--ink)' : 'var(--white)' : 'var(--white)',
      boxShadow: 'var(--sh-1)',
      transition: 'left var(--d-base) var(--ease-in-out)'
    }
  })), label || hint ? /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 2
    }
  }, label ? /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body-sm)'
    }
  }, label) : null, hint ? /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-eyebrow)',
      color: 'var(--text-quiet)'
    }
  }, hint) : null) : null);
}
Object.assign(__ds_scope, { Switch });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Switch.jsx", error: String((e && e.message) || e) }); }

// components/navigation/RailItem.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function RailItem({
  icon,
  label,
  count,
  active = false,
  onClick,
  onDark = true,
  style,
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const fg = onDark ? 'var(--ink-inverse)' : 'var(--ink)';
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      width: '100%',
      height: 34,
      padding: '0 10px',
      border: 'none',
      cursor: 'pointer',
      textAlign: 'left',
      borderRadius: 'var(--r-6)',
      background: active ? onDark ? 'rgba(242,242,240,0.09)' : 'rgba(17,17,17,0.06)' : hover ? onDark ? 'rgba(242,242,240,0.05)' : 'rgba(17,17,17,0.035)' : 'transparent',
      color: fg,
      opacity: active ? 1 : hover ? 0.86 : 0.52,
      font: 'var(--type-body-sm)',
      transition: 'var(--t-hover)',
      ...style
    }
  }, rest), icon ? /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: 16
  }) : null, /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }, label), count !== undefined ? /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-mono-sm)',
      opacity: 0.72
    }
  }, count) : null);
}
Object.assign(__ds_scope, { RailItem });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/RailItem.jsx", error: String((e && e.message) || e) }); }

// components/navigation/SegmentedControl.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* The floating pill control from the reference chrome: white capsule, hairline,
   soft lift; the selected segment is a solid ink capsule with inverse text. */
function SegmentedControl({
  items = [],
  value,
  onChange,
  size = 'md',
  floating = false,
  style,
  ...rest
}) {
  const h = size === 'sm' ? 26 : 32;
  return /*#__PURE__*/React.createElement("div", _extends({
    role: "tablist",
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 2,
      padding: 3,
      borderRadius: 'var(--r-pill)',
      background: 'var(--white)',
      boxShadow: floating ? 'inset 0 0 0 1px var(--border-hairline), var(--sh-3)' : 'inset 0 0 0 1px var(--border-hairline)',
      ...style
    }
  }, rest), items.map(it => {
    const v = typeof it === 'string' ? it : it.value;
    const l = typeof it === 'string' ? it : it.label;
    const dot = typeof it === 'object' ? it.dot : undefined;
    const on = v === value;
    return /*#__PURE__*/React.createElement("button", {
      key: v,
      role: "tab",
      "aria-selected": on,
      onClick: () => onChange && onChange(v),
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        height: h,
        padding: `0 ${size === 'sm' ? 11 : 14}px`,
        border: 'none',
        cursor: 'pointer',
        borderRadius: 'var(--r-pill)',
        background: on ? 'var(--ink)' : 'transparent',
        color: on ? 'var(--ink-inverse)' : 'var(--text-body)',
        font: size === 'sm' ? 'var(--type-eyebrow)' : 'var(--type-label)',
        letterSpacing: 0,
        transition: 'background-color var(--d-fast) var(--ease-out), color var(--d-fast) var(--ease-out)'
      }
    }, dot ? /*#__PURE__*/React.createElement(__ds_scope.StatusDot, {
      state: dot,
      size: 6
    }) : null, l);
  }));
}
Object.assign(__ds_scope, { SegmentedControl });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/SegmentedControl.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Tabs.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Tabs({
  items = [],
  value,
  onChange,
  onDark = false,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("div", _extends({
    role: "tablist",
    style: {
      display: 'flex',
      gap: 20,
      boxShadow: `inset 0 -1px 0 ${onDark ? 'var(--border-on-dark)' : 'var(--border-hairline)'}`,
      ...style
    }
  }, rest), items.map(it => {
    const v = typeof it === 'string' ? it : it.value;
    const l = typeof it === 'string' ? it : it.label;
    const count = typeof it === 'object' ? it.count : undefined;
    const on = v === value;
    return /*#__PURE__*/React.createElement("button", {
      key: v,
      role: "tab",
      "aria-selected": on,
      onClick: () => onChange && onChange(v),
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '0 0 10px',
        border: 'none',
        background: 'none',
        cursor: 'pointer',
        font: 'var(--type-body-sm)',
        color: on ? onDark ? 'var(--ink-inverse)' : 'var(--ink)' : onDark ? 'var(--text-on-dark-quiet)' : 'var(--text-quiet)',
        boxShadow: on ? `inset 0 -2px 0 ${onDark ? 'var(--ink-inverse)' : 'var(--ink)'}` : 'none',
        transition: 'var(--t-hover)'
      }
    }, l, count !== undefined ? /*#__PURE__*/React.createElement("span", {
      style: {
        font: 'var(--type-mono-sm)',
        opacity: 0.52
      }
    }, "(", count, ")") : null);
  }));
}
Object.assign(__ds_scope, { Tabs });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Tabs.jsx", error: String((e && e.message) || e) }); }

// components/product/PayloadView.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function renderPart(part, i, animate) {
  if (typeof part === 'string') return /*#__PURE__*/React.createElement("span", {
    key: i
  }, part);
  return /*#__PURE__*/React.createElement(__ds_scope.RedactionMask, {
    key: i,
    type: part.type,
    length: part.length,
    animate: animate,
    tone: "inverse"
  }, part.mask);
}

/* The console's focal surface: the outbound payload as it leaves, with a
   scanline crossing it while the sweep runs. */
function PayloadView({
  id,
  method = 'POST',
  path = '/v1/chat/completions',
  model,
  lines = [],
  status = 'redacted',
  latency,
  scanning = false,
  onCopy,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      background: 'var(--surface-code)',
      color: 'var(--ink-inverse)',
      borderRadius: 'var(--r-12)',
      boxShadow: 'var(--sh-3)',
      overflow: 'hidden',
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '12px 12px 12px 16px',
      boxShadow: 'inset 0 -1px 0 var(--border-on-dark)'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.StatusDot, {
    state: scanning ? 'ink' : status,
    size: 6,
    live: scanning,
    style: scanning ? {
      background: 'var(--ink-inverse)'
    } : undefined
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-mono-sm)',
      color: 'var(--text-on-dark-body)'
    }
  }, method, " ", path), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), model ? /*#__PURE__*/React.createElement(__ds_scope.Badge, {
    onDark: true
  }, model) : null, latency ? /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-mono-sm)',
      color: 'var(--text-on-dark-quiet)'
    }
  }, latency) : null, onCopy ? /*#__PURE__*/React.createElement(__ds_scope.IconButton, {
    name: "copy",
    label: "Copy payload",
    size: 24,
    onDark: true,
    onClick: onCopy
  }) : null), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      padding: '14px 16px 16px',
      font: 'var(--type-mono)',
      letterSpacing: 'var(--tr-mono)',
      lineHeight: 1.62,
      overflowX: 'auto'
    }
  }, lines.map((line, i) => {
    const parts = Array.isArray(line) ? line : [line];
    return /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        whiteSpace: 'pre',
        color: 'var(--text-on-dark-body)'
      }
    }, parts.map((p, j) => renderPart(p, j, scanning)));
  }), scanning ? /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      inset: 0,
      overflow: 'hidden',
      pointerEvents: 'none'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: 0,
      bottom: 0,
      width: 120,
      background: 'linear-gradient(90deg,rgba(242,242,240,0),rgba(242,242,240,0.06),rgba(242,242,240,0))',
      animation: 'zt-scan 1.6s var(--ease-linear) infinite'
    }
  })) : null, id ? /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 12,
      font: 'var(--type-mono-sm)',
      color: 'var(--text-on-dark-quiet)'
    }
  }, id) : null));
}
Object.assign(__ds_scope, { PayloadView });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/product/PayloadView.jsx", error: String((e && e.message) || e) }); }

// components/product/RuleRow.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function RuleRow({
  name,
  pattern,
  action = 'Redact',
  hits,
  active = true,
  onToggle,
  onEdit,
  style,
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  return /*#__PURE__*/React.createElement("div", _extends({
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 200px 96px 80px 62px',
      alignItems: 'center',
      gap: 12,
      minHeight: 52,
      padding: '0 12px',
      background: hover ? 'rgba(17,17,17,0.025)' : 'transparent',
      boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
      opacity: active ? 1 : 0.52,
      transition: 'background-color var(--d-fast) var(--ease-out), opacity var(--d-base) var(--ease-out)',
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body-sm)'
    }
  }, name), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement(__ds_scope.Tag, {
    mono: true
  }, pattern)), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-eyebrow)',
      color: 'var(--text-quiet)'
    }
  }, action), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-mono-sm)',
      color: 'var(--text-faint)'
    }
  }, hits), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'flex-end',
      gap: 4
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Switch, {
    checked: active,
    onChange: onToggle
  }), /*#__PURE__*/React.createElement(__ds_scope.IconButton, {
    name: "more-horizontal",
    label: `Actions for ${name}`,
    size: 24,
    onClick: onEdit
  })));
}
Object.assign(__ds_scope, { RuleRow });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/product/RuleRow.jsx", error: String((e && e.message) || e) }); }

// components/product/SweepRow.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const LABEL = {
  clean: 'Clean',
  redacted: 'Redacted',
  blocked: 'Blocked',
  idle: 'Pending'
};
function SweepRow({
  time,
  path,
  model,
  findings = [],
  status = 'clean',
  latency,
  active = false,
  onClick,
  style,
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const types = findings.map(f => typeof f === 'string' ? f : f && f.type).filter(Boolean);
  return /*#__PURE__*/React.createElement("div", _extends({
    role: "row",
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
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
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-mono-sm)',
      color: 'var(--text-faint)'
    }
  }, time), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-mono-sm)',
      color: 'var(--text-body)',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, path), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-eyebrow)',
      color: 'var(--text-quiet)'
    }
  }, model), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      gap: 5,
      overflow: 'hidden'
    }
  }, types.length ? types.slice(0, 2).map((t, i) => /*#__PURE__*/React.createElement(__ds_scope.Badge, {
    key: t + i,
    tone: "neutral"
  }, t)) : /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-eyebrow)',
      color: 'var(--text-faint)'
    }
  }, "\u2014"), types.length > 2 ? /*#__PURE__*/React.createElement(__ds_scope.Badge, {
    tone: "neutral"
  }, "+", types.length - 2) : null), /*#__PURE__*/React.createElement(__ds_scope.Badge, {
    tone: status,
    status: status
  }, LABEL[status] || status), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-mono-sm)',
      color: 'var(--text-faint)',
      textAlign: 'right',
      whiteSpace: 'nowrap'
    }
  }, latency), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'flex-end'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "chevron-right",
    size: 14,
    style: {
      opacity: hover ? 0.52 : 0.22
    }
  })));
}
Object.assign(__ds_scope, { SweepRow });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/product/SweepRow.jsx", error: String((e && e.message) || e) }); }

// ui_kits/console/ConsoleShell.jsx
try { (() => {
const DS = () => window.ZeroTraceDesignSystem_7f4295;
function ConsoleShell({
  view,
  onView,
  children,
  counts
}) {
  const {
    Wordmark,
    RedactionMask,
    Button,
    IconButton,
    Icon,
    Card,
    Badge,
    Tag,
    Metric,
    StatusDot,
    Input,
    Select,
    Checkbox,
    Radio,
    Switch,
    Tabs,
    SegmentedControl,
    RailItem,
    Dialog,
    Toast,
    Tooltip,
    EmptyState,
    PayloadView,
    SweepRow,
    RuleRow
  } = DS();
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      minHeight: '100vh',
      background: 'var(--paper)'
    }
  }, /*#__PURE__*/React.createElement("aside", {
    style: {
      position: 'sticky',
      top: 0,
      alignSelf: 'flex-start',
      height: '100vh',
      width: 232,
      flex: '0 0 232px',
      background: 'var(--surface-dark)',
      display: 'flex',
      flexDirection: 'column',
      padding: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '6px 10px 20px'
    }
  }, /*#__PURE__*/React.createElement(Wordmark, {
    size: 17,
    tone: "inverse"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 2
    }
  }, /*#__PURE__*/React.createElement(RailItem, {
    icon: "scan-line",
    label: "Sweep log",
    count: counts.swept,
    active: view === 'sweep',
    onClick: () => onView('sweep')
  }), /*#__PURE__*/React.createElement(RailItem, {
    icon: "eye-off",
    label: "Findings",
    count: counts.findings,
    active: view === 'findings',
    onClick: () => onView('findings')
  }), /*#__PURE__*/React.createElement(RailItem, {
    icon: "list-filter",
    label: "Policy rules",
    count: counts.rules,
    active: view === 'rules',
    onClick: () => onView('rules')
  }), /*#__PURE__*/React.createElement(RailItem, {
    icon: "settings-2",
    label: "Integration",
    active: view === 'integration',
    onClick: () => onView('integration')
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 24,
      padding: '0 10px 8px',
      font: 'var(--type-eyebrow)',
      letterSpacing: 'var(--tr-caps)',
      textTransform: 'uppercase',
      color: 'rgba(242,242,240,0.36)'
    }
  }, "Environments"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 2
    }
  }, /*#__PURE__*/React.createElement(RailItem, {
    icon: "activity",
    label: "production",
    active: false
  }), /*#__PURE__*/React.createElement(RailItem, {
    icon: "activity",
    label: "staging",
    active: false
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '10px 10px 6px',
      boxShadow: 'inset 0 1px 0 var(--border-on-dark)'
    }
  }, /*#__PURE__*/React.createElement(StatusDot, {
    state: "clean",
    size: 6,
    live: true
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-mono-sm)',
      color: 'var(--text-on-dark-quiet)'
    }
  }, "proxy live \xB7 4 ms"))), /*#__PURE__*/React.createElement("main", {
    style: {
      flex: 1,
      minWidth: 0,
      display: 'flex',
      flexDirection: 'column'
    }
  }, /*#__PURE__*/React.createElement("header", {
    style: {
      position: 'sticky',
      top: 0,
      zIndex: 20,
      height: 56,
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '0 24px',
      background: 'rgba(232,232,230,0.82)',
      backdropFilter: 'var(--blur-panel)',
      boxShadow: 'inset 0 -1px 0 var(--border-hairline)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-eyebrow)',
      letterSpacing: 'var(--tr-caps)',
      textTransform: 'uppercase',
      color: 'var(--muted)'
    }
  }, "ZeroTrace"), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-faint)'
    }
  }, "\xB7"), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body-sm)'
    }
  }, {
    sweep: 'Sweep log',
    findings: 'Findings',
    rules: 'Policy rules',
    integration: 'Integration'
  }[view]), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(Badge, {
    status: "clean",
    tone: "clean"
  }, "Sweeping"), /*#__PURE__*/React.createElement(Tooltip, {
    label: "Docs"
  }, /*#__PURE__*/React.createElement(IconButton, {
    name: "book-open",
    label: "Docs"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      width: 26,
      height: 26,
      borderRadius: '50%',
      background: 'var(--ink)',
      color: 'var(--ink-inverse)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      font: 'var(--type-eyebrow)'
    }
  }, "AK")), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '24px 24px 64px',
      flex: 1
    }
  }, children)));
}
Object.assign(window, {
  ConsoleShell
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/console/ConsoleShell.jsx", error: String((e && e.message) || e) }); }

// ui_kits/console/Inspector.jsx
try { (() => {
const DS = () => window.ZeroTraceDesignSystem_7f4295;
function Inspector({
  row,
  onClose
}) {
  const {
    Wordmark,
    RedactionMask,
    Button,
    IconButton,
    Icon,
    Card,
    Badge,
    Tag,
    Metric,
    StatusDot,
    Input,
    Select,
    Checkbox,
    Radio,
    Switch,
    Tabs,
    SegmentedControl,
    RailItem,
    Dialog,
    Toast,
    Tooltip,
    EmptyState,
    PayloadView,
    SweepRow,
    RuleRow
  } = DS();
  const [scanning, setScanning] = React.useState(true);
  const [copied, setCopied] = React.useState(false);
  React.useEffect(() => {
    setScanning(true);
    const t = setTimeout(() => setScanning(false), 1800);
    return () => clearTimeout(t);
  }, [row.id]);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'fixed',
      inset: 0,
      zIndex: 40,
      display: 'flex',
      justifyContent: 'flex-end',
      background: 'rgba(17,17,17,0.36)'
    },
    onClick: onClose
  }, /*#__PURE__*/React.createElement("section", {
    onClick: e => e.stopPropagation(),
    style: {
      width: 620,
      maxWidth: '92vw',
      height: '100%',
      overflowY: 'auto',
      background: 'var(--surface-card)',
      boxShadow: 'var(--sh-4)',
      animation: 'zt-fade-up var(--d-base) var(--ease-out)'
    }
  }, /*#__PURE__*/React.createElement("header", {
    style: {
      position: 'sticky',
      top: 0,
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '16px 20px',
      background: 'var(--surface-card)',
      boxShadow: 'inset 0 -1px 0 var(--border-hairline)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-eyebrow)',
      letterSpacing: 'var(--tr-caps)',
      textTransform: 'uppercase',
      color: 'var(--muted)'
    }
  }, "Patch"), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-mono-sm)',
      color: 'var(--text-quiet)'
    }
  }, row.id), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(IconButton, {
    name: "x",
    label: "Close inspector",
    onClick: onClose
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 20,
      display: 'flex',
      flexDirection: 'column',
      gap: 18
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      flexWrap: 'wrap'
    }
  }, /*#__PURE__*/React.createElement(Badge, {
    tone: row.status,
    status: row.status
  }, row.status === 'clean' ? 'Clean' : row.status === 'blocked' ? 'Blocked' : `(${row.findings.length}) redacted`), /*#__PURE__*/React.createElement(Badge, null, row.model), /*#__PURE__*/React.createElement(Tag, {
    mono: true
  }, row.time), /*#__PURE__*/React.createElement(Tag, {
    mono: true
  }, row.latency)), /*#__PURE__*/React.createElement(PayloadView, {
    id: row.id,
    model: row.model,
    latency: row.latency,
    status: row.status,
    scanning: scanning,
    lines: row.payload,
    onCopy: () => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2600);
    }
  }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      font: 'var(--type-eyebrow)',
      letterSpacing: 'var(--tr-caps)',
      textTransform: 'uppercase',
      color: 'var(--muted)',
      marginBottom: 10
    }
  }, "Findings"), /*#__PURE__*/React.createElement(Card, {
    tone: "sunken",
    pad: 0
  }, row.findings.length ? row.findings.map(fd => /*#__PURE__*/React.createElement("div", {
    key: fd.type,
    style: {
      display: 'grid',
      gridTemplateColumns: '120px 1fr 90px',
      alignItems: 'center',
      gap: 12,
      padding: '10px 14px',
      boxShadow: 'inset 0 -1px 0 var(--border-hairline)'
    }
  }, /*#__PURE__*/React.createElement(Tag, {
    mono: true
  }, fd.type), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-mono-sm)'
    }
  }, /*#__PURE__*/React.createElement(RedactionMask, {
    type: fd.type,
    length: fd.length
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-eyebrow)',
      color: 'var(--text-quiet)',
      textAlign: 'right'
    }
  }, fd.action))) : /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '14px',
      font: 'var(--type-body-sm)',
      color: 'var(--text-quiet)'
    }
  }, "Clean. Nothing redacted."))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      font: 'var(--type-eyebrow)',
      letterSpacing: 'var(--tr-caps)',
      textTransform: 'uppercase',
      color: 'var(--muted)',
      marginBottom: 10
    }
  }, "Timeline"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
      font: 'var(--type-mono-sm)',
      color: 'var(--text-quiet)'
    }
  }, /*#__PURE__*/React.createElement("span", null, row.time, ".204 \u2014 payload intercepted, 1.8 KB"), /*#__PURE__*/React.createElement("span", null, row.time, ".207 \u2014 sweep started, 4 rules"), /*#__PURE__*/React.createElement("span", null, row.time, ".211 \u2014 ", row.findings.length ? `${row.findings.length} findings replaced in stream` : 'no findings'), /*#__PURE__*/React.createElement("span", null, row.time, ".", row.status === 'blocked' ? '213 — request withheld, upstream never contacted' : '244 — dispatched upstream'))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    iconEnd: "arrow-right"
  }, "Open rule"), /*#__PURE__*/React.createElement(Button, {
    variant: "ghost",
    icon: "copy",
    onClick: () => setCopied(true)
  }, "Copy patch"))), copied ? /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'fixed',
      bottom: 24,
      right: 24
    }
  }, /*#__PURE__*/React.createElement(Toast, {
    status: "info",
    onDismiss: () => setCopied(false)
  }, "Patch copied to clipboard.")) : null));
}
Object.assign(window, {
  Inspector
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/console/Inspector.jsx", error: String((e && e.message) || e) }); }

// ui_kits/console/Integration.jsx
try { (() => {
const DS = () => window.ZeroTraceDesignSystem_7f4295;
const INTEGRATION_SNIPPET = ['import OpenAI from "openai";', '', 'const client = new OpenAI({', '  baseURL: "https://proxy.zerotrace.dev/v1",', '  defaultHeaders: { "zt-env": "production" },', '});'];
function Integration() {
  const {
    Wordmark,
    RedactionMask,
    Button,
    IconButton,
    Icon,
    Card,
    Badge,
    Tag,
    Metric,
    StatusDot,
    Input,
    Select,
    Checkbox,
    Radio,
    Switch,
    Tabs,
    SegmentedControl,
    RailItem,
    Dialog,
    Toast,
    Tooltip,
    EmptyState,
    PayloadView,
    SweepRow,
    RuleRow
  } = DS();
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 20,
      maxWidth: 1000
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h1", {
    style: {
      font: 'var(--type-h1)',
      letterSpacing: 'var(--tr-display)'
    }
  }, "Integration"), /*#__PURE__*/React.createElement("p", {
    style: {
      marginTop: 8,
      font: 'var(--type-body)',
      color: 'var(--text-body)',
      maxWidth: '56ch'
    }
  }, "Point your SDK base URL at the proxy. Nothing else changes \u2014 same routes, same responses, same keys.")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1.35fr 1fr',
      gap: 12,
      alignItems: 'start'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--surface-code)',
      borderRadius: 'var(--r-12)',
      boxShadow: 'var(--sh-3)',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '12px 12px 12px 16px',
      boxShadow: 'inset 0 -1px 0 var(--border-on-dark)'
    }
  }, /*#__PURE__*/React.createElement(StatusDot, {
    state: "clean",
    size: 6,
    live: true
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-mono-sm)',
      color: 'var(--text-on-dark-body)'
    }
  }, "node \xB7 openai@4"), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(Tooltip, {
    label: "Copy snippet"
  }, /*#__PURE__*/React.createElement(IconButton, {
    name: "copy",
    label: "Copy snippet",
    size: 24,
    onDark: true
  }))), /*#__PURE__*/React.createElement("pre", {
    style: {
      margin: 0,
      padding: '16px',
      font: 'var(--type-mono)',
      letterSpacing: 'var(--tr-mono)',
      lineHeight: 1.62,
      color: 'var(--text-on-dark-body)'
    }
  }, INTEGRATION_SNIPPET.join('\n'))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(Card, {
    pad: 18,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(Input, {
    label: "Proxy endpoint",
    mono: true,
    defaultValue: "proxy.zerotrace.dev/v1",
    prefix: "https://"
  }), /*#__PURE__*/React.createElement(Input, {
    label: "Environment key",
    mono: true,
    defaultValue: "zt_live_9f3a\u2026",
    hint: "Rotated every 90 days."
  }), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    full: true,
    iconEnd: "external-link"
  }, "Open docs")), /*#__PURE__*/React.createElement(Card, {
    tone: "dark",
    pad: 18
  }, /*#__PURE__*/React.createElement(Metric, {
    label: "Time to first sweep",
    value: "90",
    unit: "s",
    note: "median, new workspace",
    size: "sm",
    onDark: true
  })))), /*#__PURE__*/React.createElement(Card, {
    pad: 20,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: 'var(--type-eyebrow)',
      letterSpacing: 'var(--tr-caps)',
      textTransform: 'uppercase',
      color: 'var(--muted)'
    }
  }, "Sweep behaviour"), /*#__PURE__*/React.createElement(Checkbox, {
    label: "Sweep streaming responses",
    hint: "Inspects server-sent chunks as they return.",
    checked: true
  }), /*#__PURE__*/React.createElement(Checkbox, {
    label: "Log redacted values (hashed)",
    hint: "Stores a salted hash, never the value.",
    checked: true
  }), /*#__PURE__*/React.createElement(Checkbox, {
    label: "Mirror patches to SIEM",
    hint: "Requires an outbound webhook."
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      paddingTop: 12,
      boxShadow: 'inset 0 1px 0 var(--border-hairline)'
    }
  }, /*#__PURE__*/React.createElement(Switch, {
    checked: true,
    label: "Block on sweep failure"
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(Tag, {
    mono: true
  }, "v2.8.6"), /*#__PURE__*/React.createElement(Badge, {
    status: "clean",
    tone: "clean"
  }, "Healthy"))));
}
Object.assign(window, {
  Integration
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/console/Integration.jsx", error: String((e && e.message) || e) }); }

// ui_kits/console/PolicyRules.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const DS = () => window.ZeroTraceDesignSystem_7f4295;
const RULE_HEAD = ['Rule', 'Pattern', 'Action', 'Hits', ''];
function PolicyRules({
  rules,
  onToggle,
  onDelete
}) {
  const {
    Wordmark,
    RedactionMask,
    Button,
    IconButton,
    Icon,
    Card,
    Badge,
    Tag,
    Metric,
    StatusDot,
    Input,
    Select,
    Checkbox,
    Radio,
    Switch,
    Tabs,
    SegmentedControl,
    RailItem,
    Dialog,
    Toast,
    Tooltip,
    EmptyState,
    PayloadView,
    SweepRow,
    RuleRow
  } = DS();
  const [confirm, setConfirm] = React.useState(null);
  const [toast, setToast] = React.useState(null);
  const [draft, setDraft] = React.useState(false);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 20,
      maxWidth: 1000
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'space-between',
      gap: 24
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h1", {
    style: {
      font: 'var(--type-h1)',
      letterSpacing: 'var(--tr-display)'
    }
  }, "Policy rules"), /*#__PURE__*/React.createElement("p", {
    style: {
      marginTop: 8,
      font: 'var(--type-body)',
      color: 'var(--text-body)',
      maxWidth: '52ch'
    }
  }, "Rules run in order on every outbound payload. A rule with no redaction strategy blocks the request instead.")), /*#__PURE__*/React.createElement(Button, {
    icon: "plus",
    onClick: () => setDraft(true)
  }, "New rule")), /*#__PURE__*/React.createElement(Card, {
    pad: 0
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 200px 96px 80px 62px',
      gap: 12,
      padding: '12px',
      font: 'var(--type-eyebrow)',
      letterSpacing: 'var(--tr-caps)',
      textTransform: 'uppercase',
      color: 'var(--muted)',
      boxShadow: 'inset 0 -1px 0 var(--border-hairline)'
    }
  }, RULE_HEAD.map((h, i) => /*#__PURE__*/React.createElement("span", {
    key: i
  }, h))), rules.map(r => /*#__PURE__*/React.createElement(RuleRow, _extends({
    key: r.name
  }, r, {
    onToggle: () => onToggle(r.name),
    onEdit: () => setConfirm(r)
  })))), /*#__PURE__*/React.createElement(Card, {
    tone: "sunken",
    pad: 20,
    style: {
      display: 'flex',
      gap: 20,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: 'var(--type-h3)',
      letterSpacing: 'var(--tr-heading)'
    }
  }, "Fail closed"), /*#__PURE__*/React.createElement("p", {
    style: {
      marginTop: 4,
      font: 'var(--type-body-sm)',
      color: 'var(--text-quiet)',
      maxWidth: '58ch'
    }
  }, "If a sweep errors, the payload is not dispatched and is not stored. Turning this off dispatches unswept payloads.")), /*#__PURE__*/React.createElement(Switch, {
    checked: true,
    label: "Active"
  })), draft ? /*#__PURE__*/React.createElement(Dialog, {
    open: true,
    width: 480,
    title: "New rule",
    description: "The pattern runs against the serialised payload body.",
    confirmLabel: "Create rule",
    onCancel: () => setDraft(false),
    onConfirm: () => {
      setDraft(false);
      setToast('Rule saved. Active on the next payload.');
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(Input, {
    label: "Rule name",
    placeholder: "no raw card numbers"
  }), /*#__PURE__*/React.createElement(Input, {
    label: "Pattern",
    mono: true,
    placeholder: "luhn:16"
  }), /*#__PURE__*/React.createElement(Select, {
    label: "Action",
    options: ['Redact and dispatch', 'Block the request', 'Log only']
  }))) : null, confirm ? /*#__PURE__*/React.createElement(Dialog, {
    open: true,
    destructive: true,
    title: `Delete rule "${confirm.pattern}"?`,
    description: "Payloads matching it will dispatch unredacted.",
    confirmLabel: "Delete rule",
    onCancel: () => setConfirm(null),
    onConfirm: () => {
      onDelete(confirm.name);
      setConfirm(null);
      setToast('Rule deleted.');
    }
  }) : null, toast ? /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'fixed',
      bottom: 24,
      right: 24,
      zIndex: 70
    }
  }, /*#__PURE__*/React.createElement(Toast, {
    status: "clean",
    onDismiss: () => setToast(null)
  }, toast)) : null);
}
Object.assign(window, {
  PolicyRules
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/console/PolicyRules.jsx", error: String((e && e.message) || e) }); }

// ui_kits/console/SweepLog.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const DS = () => window.ZeroTraceDesignSystem_7f4295;
const SWEEP_HEAD = ['Time', 'Path', 'Model', 'Findings', 'Result', 'Latency', ''];
function SweepLog({
  rows,
  onOpen,
  activeId
}) {
  const {
    Wordmark,
    RedactionMask,
    Button,
    IconButton,
    Icon,
    Card,
    Badge,
    Tag,
    Metric,
    StatusDot,
    Input,
    Select,
    Checkbox,
    Radio,
    Switch,
    Tabs,
    SegmentedControl,
    RailItem,
    Dialog,
    Toast,
    Tooltip,
    EmptyState,
    PayloadView,
    SweepRow,
    RuleRow
  } = DS();
  const [tab, setTab] = React.useState('all');
  const [range, setRange] = React.useState('24h');
  const [q, setQ] = React.useState('');
  const filtered = rows.filter(r => {
    if (tab === 'redacted' && r.status !== 'redacted') return false;
    if (tab === 'blocked' && r.status !== 'blocked') return false;
    if (q && !(r.path + r.model + r.findings.join(' ')).includes(q)) return false;
    return true;
  });
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 20,
      maxWidth: 1200
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'space-between',
      gap: 24
    }
  }, /*#__PURE__*/React.createElement("h1", {
    style: {
      font: 'var(--type-h1)',
      letterSpacing: 'var(--tr-display)',
      maxWidth: '22ch'
    }
  }, "Every outbound payload, before it left"), /*#__PURE__*/React.createElement(SegmentedControl, {
    value: range,
    onChange: setRange,
    size: "sm",
    items: [{
      value: '24h',
      label: 'Last 24h'
    }, {
      value: '7d',
      label: '7 days'
    }, {
      value: '30d',
      label: '30 days'
    }]
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(4,1fr)',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(Card, {
    pad: 18
  }, /*#__PURE__*/React.createElement(Metric, {
    label: "Payloads swept",
    value: "1.24M",
    note: "last 24h",
    size: "sm"
  })), /*#__PURE__*/React.createElement(Card, {
    pad: 18
  }, /*#__PURE__*/React.createElement(Metric, {
    label: "Values redacted",
    value: "8,411",
    note: "across 27 rules",
    size: "sm"
  })), /*#__PURE__*/React.createElement(Card, {
    pad: 18
  }, /*#__PURE__*/React.createElement(Metric, {
    label: "Requests blocked",
    value: "12",
    note: "no redaction strategy",
    size: "sm"
  })), /*#__PURE__*/React.createElement(Card, {
    tone: "dark",
    pad: 18
  }, /*#__PURE__*/React.createElement(Metric, {
    label: "Added latency",
    value: "4",
    unit: "ms",
    note: "p95, in-stream",
    size: "sm",
    onDark: true
  }))), /*#__PURE__*/React.createElement(Card, {
    pad: 0
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      padding: '16px 16px 0'
    }
  }, /*#__PURE__*/React.createElement(Tabs, {
    value: tab,
    onChange: setTab,
    style: {
      flex: 1
    },
    items: [{
      value: 'all',
      label: 'All payloads',
      count: rows.length
    }, {
      value: 'redacted',
      label: 'Redacted',
      count: rows.filter(r => r.status === 'redacted').length
    }, {
      value: 'blocked',
      label: 'Blocked',
      count: rows.filter(r => r.status === 'blocked').length
    }]
  }), /*#__PURE__*/React.createElement(Input, {
    size: "sm",
    icon: "search",
    placeholder: "Search paths and findings",
    value: q,
    onChange: e => setQ(e.target.value),
    style: {
      width: 240,
      paddingBottom: 10
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '78px 1fr 96px 150px 74px 64px 20px',
      gap: 12,
      padding: '10px 12px',
      font: 'var(--type-eyebrow)',
      letterSpacing: 'var(--tr-caps)',
      textTransform: 'uppercase',
      color: 'var(--muted)',
      boxShadow: 'inset 0 -1px 0 var(--border-hairline)'
    }
  }, SWEEP_HEAD.map((h, i) => /*#__PURE__*/React.createElement("span", {
    key: i
  }, h))), filtered.length ? filtered.map(r => /*#__PURE__*/React.createElement(SweepRow, _extends({
    key: r.id
  }, r, {
    active: r.id === activeId,
    onClick: () => onOpen(r)
  }))) : /*#__PURE__*/React.createElement(EmptyState, {
    icon: "search",
    title: "No payloads match",
    description: "Clear the search or widen the range."
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '12px 16px'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-eyebrow)',
      color: 'var(--text-quiet)'
    }
  }, "(", filtered.length, ") of 1,243,904 payloads"), /*#__PURE__*/React.createElement(Button, {
    size: "sm",
    variant: "ghost",
    iconEnd: "chevron-right"
  }, "Older"))));
}
Object.assign(window, {
  SweepLog
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/console/SweepLog.jsx", error: String((e && e.message) || e) }); }

// ui_kits/console/data.js
try { (() => {
window.ZT_ROWS = [{
  id: 'pl_8f3a21c9e04b',
  time: '14:02:11',
  path: '/v1/chat/completions',
  model: 'gpt-4o',
  status: 'redacted',
  latency: '240 ms',
  findings: [{
    type: 'us_ssn',
    length: 11,
    action: 'Redacted'
  }, {
    type: 'api_key',
    length: 16,
    action: 'Redacted'
  }],
  payload: ['{', '  "messages": [{ "role": "user", "content":', ['    "support log — customer ssn ', {
    mask: '123-45-6789',
    type: 'us_ssn'
  }, ','], ['     internal key ', {
    mask: 'sk-live-9fj2kd01',
    type: 'api_key'
  }, '"'], '  }],', '  "model": "gpt-4o"', '}']
}, {
  id: 'pl_7c1d80aa5512',
  time: '14:02:09',
  path: '/v1/embeddings',
  model: 'text-embedding-3',
  status: 'clean',
  latency: '88 ms',
  findings: [],
  payload: ['{', '  "input": "quarterly roadmap summary",', '  "model": "text-embedding-3-large"', '}']
}, {
  id: 'pl_5b90f4e21aa7',
  time: '14:01:58',
  path: '/v1/messages',
  model: 'claude-sonnet',
  status: 'blocked',
  latency: '—',
  findings: [{
    type: 'pan',
    length: 16,
    action: 'Blocked'
  }, {
    type: 'email',
    length: 14,
    action: 'Redacted'
  }, {
    type: 'phone',
    length: 12,
    action: 'Redacted'
  }],
  payload: ['{', '  "messages": [{ "role": "user", "content":', ['    "refund card ', {
    mask: '4111111111111111',
    type: 'pan'
  }, ' for ', {
    mask: 'ana@acme.io',
    type: 'email'
  }, '"'], '  }]', '}']
}, {
  id: 'pl_2ae4419bd0c3',
  time: '14:01:44',
  path: '/v1/chat/completions',
  model: 'gpt-4o-mini',
  status: 'redacted',
  latency: '132 ms',
  findings: [{
    type: 'jwt',
    length: 24,
    action: 'Redacted'
  }],
  payload: ['{', '  "messages": [{ "role": "system", "content":', ['    "auth header ', {
    mask: 'eyJhbGciOiJIUzI1NiIs',
    type: 'jwt'
  }, '"'], '  }]', '}']
}, {
  id: 'pl_9d02bb7c31fe',
  time: '14:01:30',
  path: '/v1/chat/completions',
  model: 'gpt-4o',
  status: 'clean',
  latency: '196 ms',
  findings: [],
  payload: ['{', '  "messages": [{ "role": "user", "content": "summarise ticket 8812" }]', '}']
}, {
  id: 'pl_411c7e9a6b20',
  time: '14:01:12',
  path: '/v1/responses',
  model: 'gpt-4.1',
  status: 'redacted',
  latency: '311 ms',
  findings: [{
    type: 'iban',
    length: 22,
    action: 'Redacted'
  }, {
    type: 'address',
    length: 28,
    action: 'Redacted'
  }],
  payload: ['{', ['  "input": "payout to ', {
    mask: 'GB29NWBK60161331926819',
    type: 'iban'
  }, '"'], '}']
}];
window.ZT_RULES = [{
  name: 'us social security numbers',
  pattern: '\\d{3}-\\d{2}-\\d{4}',
  action: 'Redact',
  hits: '(27)',
  active: true
}, {
  name: 'provider api keys',
  pattern: 'sk-(live|test)-\\w+',
  action: 'Redact',
  hits: '(311)',
  active: true
}, {
  name: 'bearer tokens and jwts',
  pattern: 'eyJ[\\w-]+\\.',
  action: 'Redact',
  hits: '(74)',
  active: true
}, {
  name: 'no raw card numbers',
  pattern: 'luhn:16',
  action: 'Block',
  hits: '(12)',
  active: true
}, {
  name: 'customer email addresses',
  pattern: 'detector:email',
  action: 'Redact',
  hits: '(1.2K)',
  active: false
}];
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/console/data.js", error: String((e && e.message) || e) }); }

// ui_kits/marketing/Hero.jsx
try { (() => {
const DS = () => window.ZeroTraceDesignSystem_7f4295;
function Hero() {
  const {
    Button,
    PayloadView,
    SegmentedControl,
    Metric
  } = DS();
  const [mode, setMode] = React.useState('redact');
  const [scan, setScan] = React.useState(true);
  React.useEffect(() => {
    setScan(true);
    const t = setTimeout(() => setScan(false), 2200);
    return () => clearTimeout(t);
  }, [mode]);
  const lines = mode === 'redact' ? ['{', '  "messages": [{ "role": "user", "content":', ['    "support log — ssn ', {
    mask: '123-45-6789',
    type: 'us_ssn'
  }, ','], ['     key ', {
    mask: 'sk-live-9fj2kd01',
    type: 'api_key'
  }, '"'], '  }]', '}'] : ['{', '  "messages": [{ "role": "user", "content":', '    "support log — ssn 123-45-6789,', '     key sk-live-9fj2kd01"', '  }]', '}'];
  return /*#__PURE__*/React.createElement("section", {
    style: {
      maxWidth: 1200,
      margin: '0 auto',
      padding: '48px 24px 0'
    }
  }, /*#__PURE__*/React.createElement("h1", {
    style: {
      font: 'var(--w-regular) var(--t-72)/1.06 var(--font-core)',
      letterSpacing: 'var(--tr-display)',
      maxWidth: '17ch'
    }
  }, "Your prompts leave ", /*#__PURE__*/React.createElement("span", {
    style: {
      opacity: 0.36
    }
  }, "with nothing in them")), /*#__PURE__*/React.createElement("p", {
    style: {
      marginTop: 20,
      font: 'var(--type-body)',
      color: 'var(--text-body)',
      maxWidth: '58ch'
    }
  }, "ZeroTrace inspects every outbound LLM call, redacts what shouldn't be in it, and logs the patch. Two lines of config."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 10,
      marginTop: 24,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement(Button, {
    size: "lg",
    pill: true
  }, "Start sweeping"), /*#__PURE__*/React.createElement(Button, {
    size: "lg",
    pill: true,
    variant: "secondary",
    iconEnd: "arrow-right"
  }, "Read the docs")), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      marginTop: 40,
      background: 'var(--surface-dark)',
      borderRadius: 'var(--r-20)',
      padding: '32px 32px 40px',
      boxShadow: 'var(--sh-4)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
      gap: 32,
      marginBottom: 22
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      font: 'var(--type-eyebrow)',
      letterSpacing: 'var(--tr-caps)',
      textTransform: 'uppercase',
      color: 'rgba(242,242,240,0.36)'
    }
  }, "Outbound payload"), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 8,
      font: 'var(--w-regular) var(--t-26)/1.22 var(--font-core)',
      letterSpacing: 'var(--tr-heading)',
      color: 'var(--ink-inverse)'
    }
  }, "Two values caught mid-stream")), /*#__PURE__*/React.createElement(SegmentedControl, {
    floating: true,
    value: mode,
    onChange: setMode,
    items: [{
      value: 'redact',
      label: 'With ZeroTrace'
    }, {
      value: 'raw',
      label: 'Without'
    }]
  })), /*#__PURE__*/React.createElement(PayloadView, {
    lines: lines,
    model: "gpt-4o",
    latency: mode === 'redact' ? '240 ms' : '236 ms',
    status: mode === 'redact' ? 'redacted' : 'blocked',
    scanning: scan && mode === 'redact',
    id: "pl_8f3a21c9e04b",
    style: {
      boxShadow: 'none',
      background: '#000'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(3,1fr)',
      gap: 24,
      marginTop: 28,
      paddingTop: 24,
      boxShadow: 'inset 0 1px 0 var(--border-on-dark)'
    }
  }, /*#__PURE__*/React.createElement(Metric, {
    label: "Added latency",
    value: "4",
    unit: "ms",
    note: "p95, in-stream",
    size: "sm",
    onDark: true
  }), /*#__PURE__*/React.createElement(Metric, {
    label: "Detectors",
    value: "41",
    note: "pii, secrets, financial",
    size: "sm",
    onDark: true
  }), /*#__PURE__*/React.createElement(Metric, {
    label: "Payloads swept",
    value: "1.24M",
    note: "last 24h, all workspaces",
    size: "sm",
    onDark: true
  }))));
}
Object.assign(window, {
  Hero
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/marketing/Hero.jsx", error: String((e && e.message) || e) }); }

// ui_kits/marketing/HowItWorks.jsx
try { (() => {
const DS = () => window.ZeroTraceDesignSystem_7f4295;
const HIW_STEPS = [{
  n: '01',
  t: 'Point the base URL',
  d: 'One config line. Same routes, same responses, your own provider keys — the proxy is transparent.'
}, {
  n: '02',
  t: 'Sweep in the stream',
  d: '41 detectors run on the serialised body before dispatch. Nothing is buffered to disk and nothing waits.'
}, {
  n: '03',
  t: 'Redact or block',
  d: 'Matched values are replaced in place. A rule with no redaction strategy withholds the request instead.'
}, {
  n: '04',
  t: 'Log the patch',
  d: 'Every intervention is recorded with a salted hash of the value, the rule that caught it, and the latency it cost.'
}];
function HowItWorks() {
  const {
    Card,
    Badge,
    Tag,
    Button,
    SweepRow
  } = DS();
  return /*#__PURE__*/React.createElement("section", {
    id: "how",
    style: {
      maxWidth: 1200,
      margin: '0 auto',
      padding: '128px 24px 0'
    }
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      font: 'var(--w-regular) var(--t-42)/1.14 var(--font-core)',
      letterSpacing: 'var(--tr-display)',
      maxWidth: '24ch'
    }
  }, "Four steps, none of which your application code notices"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(4,1fr)',
      gap: 12,
      marginTop: 40
    }
  }, HIW_STEPS.map(s => /*#__PURE__*/React.createElement(Card, {
    key: s.n,
    pad: 20,
    interactive: true,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
      minHeight: 200
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-mono-sm)',
      color: 'var(--text-faint)'
    }
  }, s.n), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-h3)',
      letterSpacing: 'var(--tr-heading)'
    }
  }, s.t), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body-sm)',
      color: 'var(--text-quiet)'
    }
  }, s.d)))), /*#__PURE__*/React.createElement("div", {
    id: "coverage",
    style: {
      marginTop: 128
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'space-between',
      gap: 32
    }
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      font: 'var(--w-regular) var(--t-42)/1.14 var(--font-core)',
      letterSpacing: 'var(--tr-display)',
      maxWidth: '22ch'
    }
  }, "Not just keys and social security numbers"), /*#__PURE__*/React.createElement("p", {
    style: {
      font: 'var(--type-body-sm)',
      color: 'var(--text-quiet)',
      maxWidth: '38ch'
    }
  }, "Detectors cover identifiers, secrets, financial data, health records and anything you can express as a pattern or a custom rule.")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      gap: 6,
      marginTop: 24
    }
  }, ['us_ssn', 'api_key', 'jwt', 'pan', 'iban', 'email', 'phone', 'address', 'passport', 'nhs_number', 'aws_secret', 'private_key', 'oauth_token', 'dob', 'mrn', 'plate', 'tax_id', 'custom:*'].map(t => /*#__PURE__*/React.createElement(Tag, {
    key: t,
    mono: true
  }, t))), /*#__PURE__*/React.createElement(Card, {
    pad: 0,
    style: {
      marginTop: 28
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '78px 1fr 96px 150px 74px 64px 20px',
      gap: 12,
      padding: '10px 12px',
      font: 'var(--type-eyebrow)',
      letterSpacing: 'var(--tr-caps)',
      textTransform: 'uppercase',
      color: 'var(--muted)',
      boxShadow: 'inset 0 -1px 0 var(--border-hairline)'
    }
  }, /*#__PURE__*/React.createElement("span", null, "Time"), /*#__PURE__*/React.createElement("span", null, "Path"), /*#__PURE__*/React.createElement("span", null, "Model"), /*#__PURE__*/React.createElement("span", null, "Findings"), /*#__PURE__*/React.createElement("span", null, "Result"), /*#__PURE__*/React.createElement("span", null, "Latency"), /*#__PURE__*/React.createElement("span", null)), /*#__PURE__*/React.createElement(SweepRow, {
    time: "14:02:11",
    path: "/v1/chat/completions",
    model: "gpt-4o",
    findings: ['us_ssn', 'api_key'],
    status: "redacted",
    latency: "240 ms"
  }), /*#__PURE__*/React.createElement(SweepRow, {
    time: "14:02:09",
    path: "/v1/embeddings",
    model: "text-embedding-3",
    status: "clean",
    latency: "88 ms"
  }), /*#__PURE__*/React.createElement(SweepRow, {
    time: "14:01:58",
    path: "/v1/messages",
    model: "claude-sonnet",
    findings: ['pan', 'email', 'phone'],
    status: "blocked",
    latency: "\u2014"
  }))));
}
Object.assign(window, {
  HowItWorks
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/marketing/HowItWorks.jsx", error: String((e && e.message) || e) }); }

// ui_kits/marketing/Install.jsx
try { (() => {
const DS = () => window.ZeroTraceDesignSystem_7f4295;
const INSTALL_TABS = {
  node: ['import OpenAI from "openai";', '', 'const client = new OpenAI({', '  baseURL: "https://proxy.zerotrace.dev/v1",', '});'],
  python: ['from openai import OpenAI', '', 'client = OpenAI(', '    base_url="https://proxy.zerotrace.dev/v1",', ')'],
  curl: ['curl https://proxy.zerotrace.dev/v1/chat/completions \\', '  -H "Authorization: Bearer $OPENAI_API_KEY" \\', '  -d @payload.json']
};
function Install() {
  const {
    Tabs,
    Button,
    IconButton,
    Tooltip,
    StatusDot,
    Badge
  } = DS();
  const [tab, setTab] = React.useState('node');
  return /*#__PURE__*/React.createElement("section", {
    id: "install",
    style: {
      maxWidth: 1200,
      margin: '0 auto',
      padding: '128px 24px 0'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1.15fr',
      gap: 48,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h2", {
    style: {
      font: 'var(--w-regular) var(--t-42)/1.14 var(--font-core)',
      letterSpacing: 'var(--tr-display)',
      maxWidth: '18ch'
    }
  }, "Two lines of config"), /*#__PURE__*/React.createElement("p", {
    style: {
      marginTop: 16,
      font: 'var(--type-body)',
      color: 'var(--text-body)',
      maxWidth: '46ch'
    }
  }, "Your provider keys stay with you. ZeroTrace never stores payload bodies \u2014 only the patch record and a salted hash of each finding."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 10,
      marginTop: 24
    }
  }, /*#__PURE__*/React.createElement(Button, {
    pill: true
  }, "Start sweeping"), /*#__PURE__*/React.createElement(Button, {
    pill: true,
    variant: "secondary",
    iconEnd: "arrow-up-right"
  }, "Self-host guide"))), /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--surface-code)',
      borderRadius: 'var(--r-16)',
      boxShadow: 'var(--sh-4)',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '12px 12px 0 20px'
    }
  }, /*#__PURE__*/React.createElement(Tabs, {
    onDark: true,
    value: tab,
    onChange: setTab,
    items: [{
      value: 'node',
      label: 'node'
    }, {
      value: 'python',
      label: 'python'
    }, {
      value: 'curl',
      label: 'curl'
    }],
    style: {
      flex: 1,
      boxShadow: 'none'
    }
  }), /*#__PURE__*/React.createElement(Tooltip, {
    label: "Copy"
  }, /*#__PURE__*/React.createElement(IconButton, {
    name: "copy",
    label: "Copy snippet",
    size: 26,
    onDark: true
  }))), /*#__PURE__*/React.createElement("pre", {
    style: {
      margin: 0,
      padding: '18px 20px 26px',
      font: 'var(--type-mono)',
      letterSpacing: 'var(--tr-mono)',
      lineHeight: 1.62,
      color: 'var(--text-on-dark-body)',
      overflowX: 'auto'
    }
  }, INSTALL_TABS[tab].join('\n')), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '12px 20px',
      boxShadow: 'inset 0 1px 0 var(--border-on-dark)'
    }
  }, /*#__PURE__*/React.createElement(StatusDot, {
    state: "clean",
    size: 6,
    live: true
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-mono-sm)',
      color: 'var(--text-on-dark-quiet)'
    }
  }, "first sweep in 90 s, median")))));
}
Object.assign(window, {
  Install
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/marketing/Install.jsx", error: String((e && e.message) || e) }); }

// ui_kits/marketing/Pricing.jsx
try { (() => {
const DS = () => window.ZeroTraceDesignSystem_7f4295;
const PRICING_PLANS = [{
  name: 'Solo',
  price: '$0',
  unit: '/ month',
  note: '100K payloads, 1 environment, community detectors.',
  cta: 'Start sweeping',
  variant: 'secondary'
}, {
  name: 'Team',
  price: '$390',
  unit: '/ month',
  note: '10M payloads, unlimited environments, custom rules, SIEM mirror.',
  cta: 'Start a trial',
  variant: 'primary',
  dark: true
}, {
  name: 'Self-hosted',
  price: 'Talk to us',
  unit: '',
  note: 'Runs in your VPC. Nothing leaves your network, including patch records.',
  cta: 'Contact sales',
  variant: 'secondary'
}];
function Pricing() {
  const {
    Card,
    Button,
    Badge,
    Metric
  } = DS();
  return /*#__PURE__*/React.createElement("section", {
    id: "pricing",
    style: {
      maxWidth: 1200,
      margin: '0 auto',
      padding: '128px 24px 0'
    }
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      font: 'var(--w-regular) var(--t-42)/1.14 var(--font-core)',
      letterSpacing: 'var(--tr-display)'
    }
  }, "Priced per payload swept"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(3,1fr)',
      gap: 12,
      marginTop: 40
    }
  }, PRICING_PLANS.map(p => /*#__PURE__*/React.createElement(Card, {
    key: p.name,
    tone: p.dark ? 'dark' : 'paper',
    pad: 24,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 14,
      minHeight: 260
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-eyebrow)',
      letterSpacing: 'var(--tr-caps)',
      textTransform: 'uppercase',
      color: p.dark ? 'rgba(242,242,240,0.52)' : 'var(--muted)'
    }
  }, p.name), p.dark ? /*#__PURE__*/React.createElement(Badge, {
    onDark: true
  }, "most common") : null), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--w-semibold) var(--t-33)/1.06 var(--font-core)',
      letterSpacing: 'var(--tr-display)',
      color: p.dark ? 'var(--ink-inverse)' : 'var(--ink)'
    }
  }, p.price), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body-sm)',
      color: p.dark ? 'rgba(242,242,240,0.52)' : 'var(--text-quiet)'
    }
  }, p.unit)), /*#__PURE__*/React.createElement("p", {
    style: {
      font: 'var(--type-body-sm)',
      color: p.dark ? 'rgba(242,242,240,0.72)' : 'var(--text-quiet)',
      flex: 1
    }
  }, p.note), /*#__PURE__*/React.createElement(Button, {
    full: true,
    pill: true,
    variant: p.dark ? 'inverse' : 'secondary'
  }, p.cta)))));
}
Object.assign(window, {
  Pricing
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/marketing/Pricing.jsx", error: String((e && e.message) || e) }); }

// ui_kits/marketing/SiteFooter.jsx
try { (() => {
const DS = () => window.ZeroTraceDesignSystem_7f4295;
const FOOTER_COLS = [{
  h: 'Product',
  l: ['How it works', 'Coverage', 'Install', 'Pricing', 'Changelog']
}, {
  h: 'Developers',
  l: ['Docs', 'Detector reference', 'Self-host guide', 'Status', 'SDKs']
}, {
  h: 'Company',
  l: ['Security', 'Trust centre', 'Privacy', 'Terms', 'Contact']
}];
function SiteFooter() {
  const {
    Wordmark,
    Button,
    Input,
    StatusDot
  } = DS();
  const link = {
    font: 'var(--type-body-sm)',
    color: 'var(--text-on-dark-body)',
    textDecoration: 'none'
  };
  return /*#__PURE__*/React.createElement("footer", {
    style: {
      marginTop: 128,
      background: 'var(--surface-dark)',
      color: 'var(--ink-inverse)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 1200,
      margin: '0 auto',
      padding: '64px 24px 32px',
      display: 'grid',
      gridTemplateColumns: '1.4fr repeat(3,1fr)',
      gap: 40
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 16,
      alignItems: 'flex-start'
    }
  }, /*#__PURE__*/React.createElement(Wordmark, {
    size: 22,
    tone: "inverse",
    descriptor: "payload sweeper"
  }), /*#__PURE__*/React.createElement("p", {
    style: {
      font: 'var(--type-body-sm)',
      color: 'var(--text-on-dark-quiet)',
      maxWidth: '30ch'
    }
  }, "The guardrail between your application and the model."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(StatusDot, {
    state: "clean",
    size: 6,
    live: true
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-mono-sm)',
      color: 'var(--text-on-dark-quiet)'
    }
  }, "all systems sweeping"))), FOOTER_COLS.map(c => /*#__PURE__*/React.createElement("div", {
    key: c.h,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-eyebrow)',
      letterSpacing: 'var(--tr-caps)',
      textTransform: 'uppercase',
      color: 'rgba(242,242,240,0.36)'
    }
  }, c.h), c.l.map(l => /*#__PURE__*/React.createElement("a", {
    key: l,
    href: "#",
    style: link
  }, l))))), /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 1200,
      margin: '0 auto',
      padding: '20px 24px 40px',
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      boxShadow: 'inset 0 1px 0 var(--border-on-dark)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-mono-sm)',
      color: 'rgba(242,242,240,0.36)'
    }
  }, "\xA9 2026 ZeroTrace \xB7 SOC 2 Type II"), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(Button, {
    size: "sm",
    pill: true,
    variant: "ghost",
    onDark: true,
    iconEnd: "arrow-up-right"
  }, "Trust centre")));
}
Object.assign(window, {
  SiteFooter
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/marketing/SiteFooter.jsx", error: String((e && e.message) || e) }); }

// ui_kits/marketing/SiteNav.jsx
try { (() => {
const DS = () => window.ZeroTraceDesignSystem_7f4295;
function SiteNav() {
  const {
    Wordmark,
    Button
  } = DS();
  const [scrolled, setScrolled] = React.useState(false);
  React.useEffect(() => {
    const el = document.scrollingElement || document.documentElement;
    const on = () => setScrolled(el.scrollTop > 8);
    window.addEventListener('scroll', on, {
      passive: true
    });
    return () => window.removeEventListener('scroll', on);
  }, []);
  const link = {
    font: 'var(--type-body-sm)',
    color: 'var(--text-body)',
    textDecoration: 'none'
  };
  return /*#__PURE__*/React.createElement("header", {
    style: {
      position: 'sticky',
      top: 0,
      zIndex: 30,
      background: scrolled ? 'rgba(232,232,230,0.72)' : 'transparent',
      backdropFilter: scrolled ? 'var(--blur-panel)' : 'none',
      boxShadow: scrolled ? 'inset 0 -1px 0 var(--border-hairline)' : 'none',
      transition: 'background-color var(--d-base) var(--ease-out), box-shadow var(--d-base) var(--ease-out)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 1200,
      margin: '0 auto',
      height: 64,
      display: 'flex',
      alignItems: 'center',
      gap: 28,
      padding: '0 24px'
    }
  }, /*#__PURE__*/React.createElement(Wordmark, {
    size: 16
  }), /*#__PURE__*/React.createElement("nav", {
    style: {
      display: 'flex',
      gap: 22,
      marginLeft: 14
    }
  }, /*#__PURE__*/React.createElement("a", {
    href: "#how",
    style: link
  }, "How it works"), /*#__PURE__*/React.createElement("a", {
    href: "#coverage",
    style: link
  }, "Coverage"), /*#__PURE__*/React.createElement("a", {
    href: "#install",
    style: link
  }, "Install"), /*#__PURE__*/React.createElement("a", {
    href: "#pricing",
    style: link
  }, "Pricing")), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("a", {
    href: "#",
    style: {
      ...link,
      color: 'var(--text-strong)'
    }
  }, "Log in"), /*#__PURE__*/React.createElement(Button, {
    size: "sm",
    pill: true
  }, "Start sweeping")));
}
Object.assign(window, {
  SiteNav
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/marketing/SiteNav.jsx", error: String((e && e.message) || e) }); }

__ds_ns.RedactionMask = __ds_scope.RedactionMask;

__ds_ns.Wordmark = __ds_scope.Wordmark;

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.Icon = __ds_scope.Icon;

__ds_ns.IconButton = __ds_scope.IconButton;

__ds_ns.Metric = __ds_scope.Metric;

__ds_ns.StatusDot = __ds_scope.StatusDot;

__ds_ns.Tag = __ds_scope.Tag;

__ds_ns.Dialog = __ds_scope.Dialog;

__ds_ns.EmptyState = __ds_scope.EmptyState;

__ds_ns.Toast = __ds_scope.Toast;

__ds_ns.Tooltip = __ds_scope.Tooltip;

__ds_ns.Checkbox = __ds_scope.Checkbox;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.Radio = __ds_scope.Radio;

__ds_ns.Select = __ds_scope.Select;

__ds_ns.Switch = __ds_scope.Switch;

__ds_ns.RailItem = __ds_scope.RailItem;

__ds_ns.SegmentedControl = __ds_scope.SegmentedControl;

__ds_ns.Tabs = __ds_scope.Tabs;

__ds_ns.PayloadView = __ds_scope.PayloadView;

__ds_ns.RuleRow = __ds_scope.RuleRow;

__ds_ns.SweepRow = __ds_scope.SweepRow;

})();
