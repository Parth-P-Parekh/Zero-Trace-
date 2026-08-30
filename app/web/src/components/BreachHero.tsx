'use client';

/**
 * The signature element, and the only bold move on the site.
 *
 * What it shows is the product's actual behaviour: a prompt carrying a
 * credential reaches the boundary, ZeroTrace detects the breach, and the request
 * **stops there**. The model never receives it. The caller gets an error naming
 * what was found.
 *
 * The gesture is the identity's own, inverted. The wordmark drains left to right
 * and completes; here the scan sweeps left to right and **halts** at the breach.
 * The part of the payload past the halt is never revealed, because the request
 * never got that far. Nothing loops - this is an event, not an animation.
 *
 * Example data is rendered the way the product renders it: solid ink blocks at
 * the original character length, never plaintext, never asterisks.
 */
import { useEffect, useState } from 'react';

type Part =
  | { text: string }
  | { block: number; type: string; breach?: boolean };

/**
 * The sweep crosses the whole payload, because detection reads all of it. What
 * stops is the request, and the boundary it does not cross is the rule the sweep
 * arrives at - not a cut through the middle of a value.
 */
const SWEEP_END = 1;

const LINE: Part[] = [
  { text: '{ "role": "user", "content": "Refund for ' },
  { block: 12, type: 'person' },
  { text: ', PAN ' },
  { block: 10, type: 'pan', breach: true },
  { text: ', key ' },
  { block: 23, type: 'razorpay key', breach: true },
  { text: '" }' },
];

export function BreachHero() {
  const [phase, setPhase] = useState<'idle' | 'scanning' | 'stopped'>('idle');

  useEffect(() => {
    const start = window.setTimeout(() => setPhase('scanning'), 260);
    const stop = window.setTimeout(() => setPhase('stopped'), 260 + 900);
    return () => {
      window.clearTimeout(start);
      window.clearTimeout(stop);
    };
  }, []);

  const swept = phase !== 'idle';
  const stopped = phase === 'stopped';

  return (
    <figure style={{ margin: 0 }}>
      <div
        style={{
          background: 'var(--surface-dark)', borderRadius: 'var(--r-16)',
          boxShadow: 'var(--sh-3)', overflow: 'hidden',
        }}
      >
        {/* Where it was going, and what happened to it. */}
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '14px 24px',
            boxShadow: 'inset 0 -1px 0 var(--border-on-dark)',
          }}
        >
          <span className="zt-mono-sm" style={{ color: 'var(--text-on-dark-quiet)' }}>
            POST /v1/chat/completions
          </span>
          <span aria-hidden style={{ color: 'rgba(242,242,240,0.22)' }}>→</span>
          <span
            className="zt-mono-sm"
            style={{
              color: stopped ? 'rgba(242,242,240,0.22)' : 'var(--text-on-dark-quiet)',
              textDecoration: stopped ? 'line-through' : 'none',
              transition: 'color var(--d-base) var(--ease-out)',
            }}
          >
            hive-core
          </span>
          <span style={{ flex: 1 }} />
          {stopped ? (
            <span
              className="zt-enter"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}
            >
              <span
                style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: 'var(--signal-blocked)', flex: '0 0 auto',
                }}
              />
              <span className="zt-mono-sm" style={{ color: 'var(--signal-blocked)' }}>
                blocked
              </span>
            </span>
          ) : (
            <span className="zt-mono-sm" style={{ color: 'rgba(242,242,240,0.36)' }}>
              inspecting
            </span>
          )}
        </div>

        {/* The payload, and the scan that stops on it. */}
        <div style={{ position: 'relative', padding: '26px 24px 28px', overflowX: 'auto' }}>
          <div
            className="zt-mono"
            style={{
              color: 'var(--text-on-dark-body)', whiteSpace: 'pre', lineHeight: 2.1,
              fontSize: 'clamp(11px, 1.35vw, 14px)', position: 'relative', zIndex: 1,
            }}
          >
            {LINE.map((part, i) =>
              'text' in part ? (
                <span key={i}>{part.text}</span>
              ) : (
                <Block key={i} {...part} stopped={stopped} />
              ),
            )}
          </div>

          {/* The sweep: a trailing wash behind a 1px leading rule. It crosses the
              payload and arrives at the boundary, which is where the request ends. */}
          <div
            aria-hidden
            style={{
              position: 'absolute', top: 0, bottom: 0, left: 0, zIndex: 0, pointerEvents: 'none',
              width: swept ? `${SWEEP_END * 100}%` : '0%',
              background: 'linear-gradient(to right, rgba(242,242,240,0.02), rgba(242,242,240,0.06))',
              borderRight: `1px solid ${stopped ? 'var(--signal-blocked)' : 'rgba(242,242,240,0.36)'}`,
              transition: 'width var(--d-drain) var(--ease-out), border-color var(--d-base) var(--ease-out)',
            }}
          />
        </div>

        {/* What the caller gets back. Not the model's answer - an error. */}
        <div
          style={{
            padding: '18px 24px 22px',
            boxShadow: 'inset 0 1px 0 var(--border-on-dark)',
            opacity: stopped ? 1 : 0,
            transition: 'opacity var(--d-base) var(--ease-out)',
          }}
        >
          <p
            style={{
              margin: 0, font: 'var(--type-body-sm)', color: 'var(--ink-inverse)',
              maxWidth: '62ch',
            }}
          >
            Blocked at the boundary. The payload was not dispatched and was not stored.
          </p>
          <p
            className="zt-mono-sm"
            style={{ margin: '10px 0 0', color: 'var(--text-on-dark-quiet)' }}
          >
            (2) values matched a rule with no redaction strategy - pan, razorpay_key.
          </p>
          <p
            className="zt-mono-sm"
            style={{ margin: '14px 0 0', color: 'rgba(242,242,240,0.36)' }}
          >
            HTTP 403 · zt.blocked_by_policy · led_01JQ7F3M4K
          </p>
        </div>
      </div>

      <figcaption
        style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)', marginTop: 14, maxWidth: '60ch' }}
      >
        The application that sent this was not modified. It resolved the provider domain and
        ZeroTrace answered - the request stopped at the perimeter, and the caller got an error
        naming what was in it.
      </figcaption>
    </figure>
  );
}

function Block({
  block,
  type,
  breach,
  stopped,
}: {
  block: number;
  type: string;
  breach?: boolean;
  stopped: boolean;
}) {
  const flagged = Boolean(breach) && stopped;
  return (
    <span
      title={`${type}${breach ? ' - matched a blocking rule' : ''}`}
      style={{ position: 'relative', display: 'inline-block', whiteSpace: 'pre' }}
    >
      {/* Sized by character count, so the block is the length of what it stands in for. */}
      <span style={{ visibility: 'hidden' }}>{' '.repeat(block)}</span>
      <span
        aria-label={`${type}, redacted`}
        style={{
          position: 'absolute', left: 0, right: 0, top: '0.16em', bottom: '0.24em',
          background: 'rgba(242,242,240,0.11)',
          boxShadow: 'inset 0 0 0 1px rgba(242,242,240,0.36)',
          borderRadius: 'var(--r-2)',
        }}
      />
      {/* A 1px signal rule is the largest a signal colour is ever allowed to be. */}
      <span
        aria-hidden
        style={{
          position: 'absolute', left: 0, bottom: '0.02em', height: 1,
          width: flagged ? '100%' : '0%',
          background: 'var(--signal-blocked)',
          transition: 'width var(--d-base) var(--ease-out)',
        }}
      />
    </span>
  );
}
