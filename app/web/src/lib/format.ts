/**
 * Formatters that encode the design system's number and copy rules, so the rules
 * live in one place instead of being re-remembered at every call site.
 *
 * From the readme: numbers are always concrete and always unit-tagged. Counts go
 * in parentheses when they qualify a noun. Never round up for effect, and never
 * write "thousands of" or "up to".
 */
import type { Action, EntityClass, Leg } from './types';

/** `1_243_904` → `1.24M`. Two significant decimals, never rounded up for effect. */
export function compact(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${trim(n / 1000)}k`;
  if (n < 1_000_000_000) return `${trim(n / 1_000_000)}M`;
  return `${trim(n / 1_000_000_000)}B`;
}

function trim(v: number): string {
  const s = v.toFixed(2);
  return s.replace(/\.?0+$/, '');
}

/** `1243904` → `1,243,904`. Used where the exact count is the point. */
export function exact(n: number): string {
  return n.toLocaleString('en-IN');
}

/** A count qualifying a noun: `(3) values redacted`. */
export function count(n: number): string {
  return `(${exact(n)})`;
}

/** Milliseconds, always unit-tagged. */
export function ms(n: number): string {
  return `${Number.isInteger(n) ? n : n.toFixed(1)} ms`;
}

/** `0.987` → `98.7%`. One decimal, because coverage moves in tenths. */
export function percent(ratio: number, decimals = 1): string {
  return `${(ratio * 100).toFixed(decimals)}%`;
}

/** Risk reads as a bare two-decimal number - it is a score, not a percentage. */
export function risk(v: number | null): string {
  return v === null ? '-' : v.toFixed(2);
}

/** Microseconds to a readable unit-tagged string. */
export function micros(us: number): string {
  return us < 1000 ? `${us} µs` : `${(us / 1000).toFixed(2)} ms`;
}

/** `RAZORPAY_KEY` → `razorpay key`. Classes are machine constants; UI is sentence case. */
export function className(c: EntityClass | string): string {
  return String(c).toLowerCase().replace(/_/g, ' ');
}

/** Class as it appears in mono contexts - unchanged, because there it is data. */
export function classToken(c: EntityClass | string): string {
  return String(c).toLowerCase();
}

const ACTION_COPY: Record<Action, string> = {
  allow: 'Allowed',
  warn: 'Warned',
  tokenize: 'Tokenized',
  mask: 'Masked',
  block: 'Blocked',
};

export function actionLabel(a: Action): string {
  return ACTION_COPY[a];
}

/** The signal a status maps to. Every use pairs this dot with the word. */
export function statusSignal(status: 'clean' | 'redacted' | 'blocked'): 'clean' | 'redacted' | 'blocked' {
  return status;
}

const STATUS_COPY: Record<'clean' | 'redacted' | 'blocked', string> = {
  clean: 'Clean',
  redacted: 'Redacted',
  blocked: 'Blocked',
};

export function statusLabel(s: 'clean' | 'redacted' | 'blocked'): string {
  return STATUS_COPY[s];
}

export function legLabel(leg: Leg): string {
  return leg === 'outbound' ? 'Outbound' : 'Inbound';
}

/**
 * The one-line result sentence, in the product's voice.
 * `(2) values redacted - us_ssn, api_key. Dispatched.`
 */
export function resultSentence(
  status: 'clean' | 'redacted' | 'blocked',
  classes: EntityClass[],
): string {
  if (status === 'clean') return 'Clean. Nothing redacted.';
  const list = Array.from(new Set(classes.map(classToken))).join(', ');
  if (status === 'blocked') return `Blocked. ${count(classes.length)} values matched a rule with no redaction strategy - ${list}.`;
  return `${count(classes.length)} values redacted - ${list}. Dispatched.`;
}

/** A span path is machine data and is never truncated in the middle of a segment. */
export function shortPath(path: string, max = 42): string {
  if (path.length <= max) return path;
  const segments = path.split('.');
  let out = segments[segments.length - 1];
  for (let i = segments.length - 2; i >= 0; i--) {
    const next = `${segments[i]}.${out}`;
    if (next.length + 1 > max) return `…${out}`;
    out = next;
  }
  return out;
}
