'use client';

/**
 * The signature element, and the only bold move on the site.
 *
 * It runs the product end to end rather than showing one frame of it. A request
 * reaches the boundary, deterministic detectors read every span, policy resolves
 * an action per class, the outbound leg either goes or does not, and a ledger
 * entry is written either way. Five stages, in the order the gateway actually
 * runs them, with the stage rail naming where the payload is at any moment.
 *
 * Two scenarios, because "nothing sensitive leaves, everything still works" is
 * two claims and only one of them is a block. The default run is the ordinary
 * one - values tokenised, request dispatched, work continues. The second is the
 * credential case, where the request stops at the boundary and the caller gets
 * an error naming what was found.
 *
 * The gesture is the identity's own. The wordmark drains left to right; here
 * the scan crosses the payload left to right and arrives at a decision. Nothing
 * loops on its own - it plays once when it is reached, and replays only when
 * asked.
 *
 * Example data renders the way the product renders it: solid blocks at the
 * original character length, never plaintext, never asterisks. The console
 * cannot show a sensitive value and neither can its marketing.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

/* -------------------------------------------------------------------------- */
/* The run                                                                     */
/* -------------------------------------------------------------------------- */

/** Where the payload is. The rail names these; the body reacts to them. */
type Stage = 'idle' | 'receive' | 'inspect' | 'decide' | 'act' | 'record';

const ORDER: Stage[] = ['receive', 'inspect', 'decide', 'act', 'record'];

/** Cumulative offsets. The inspect leg is `--d-drain`, which is the sweep. */
const MARKS: Array<[Stage, number]> = [
  ['receive', 200],
  ['inspect', 620],
  ['decide', 1560],
  ['act', 2160],
  ['record', 2820],
];

type Scenario = 'redact' | 'block';

type Part =
  | { text: string }
  | { block: number; label: string; action: 'tokenise' | 'stop' };

interface Run {
  key: Scenario;
  tab: string;
  parts: Part[];
  /** Where the sweep stops. Detection reads the whole payload either way. */
  verdict: string;
  headline: string;
  lines: string[];
  trailer: string;
}

const RUNS: Record<Scenario, Run> = {
  redact: {
    key: 'redact',
    tab: 'Ordinary request',
    parts: [
      { text: '{ "role": "user", "content": "Refund for ' },
      { block: 12, label: 'person', action: 'tokenise' },
      { text: ', PAN ' },
      { block: 10, label: 'pan', action: 'tokenise' },
      { text: ', order 4471" }' },
    ],
    verdict: 'redacted',
    headline: 'Dispatched. The model received tokens, and answered.',
    lines: [
      '(1) person - tokenised, referentially stable across hops.',
      '(2) pan - tokenised, format preserved so the model still parses it.',
      '(3) inbound leg re-read on the way back. Nothing added.',
    ],
    trailer: 'HTTP 200 · 0.24 ms added · led_01JQ7F3M4H',
  },
  block: {
    key: 'block',
    tab: 'Request carrying a key',
    parts: [
      { text: '{ "role": "user", "content": "Refund for ' },
      { block: 12, label: 'person', action: 'tokenise' },
      { text: ', PAN ' },
      { block: 10, label: 'pan', action: 'tokenise' },
      { text: ', key ' },
      { block: 23, label: 'razorpay_key', action: 'stop' },
      { text: '" }' },
    ],
    verdict: 'blocked',
    headline: 'Blocked at the boundary. The payload was not dispatched and was not stored.',
    lines: [
      '(1) razorpay_key - matched a rule with no redaction strategy.',
      '(2) person, pan - would have been tokenised. The request never got that far.',
      '(3) no plaintext written. The ledger records the decision, not the value.',
    ],
    trailer: 'HTTP 403 · zt.blocked_by_policy · led_01JQ7F3M4K',
  },
};

/** The rail. Product vocabulary, not invented labels for an animation. */
const RAIL: Array<[Stage, string]> = [
  ['receive', 'received'],
  ['inspect', 'inspected'],
  ['decide', 'decided'],
  ['act', 'acted'],
  ['record', 'recorded'],
];

/**
 * The annotation line under the payload.
 *
 * Text runs become runs of spaces of the same length and a block becomes its
 * class name padded out to the block's width, so at a fixed advance width the
 * label sits under exactly the span it describes. A label longer than the span
 * it names would push the rest of the line out of alignment, so it is clipped
 * to the block's width rather than allowed to shift everything after it.
 */
interface Segment {
  text: string;
  label?: boolean;
  stop?: boolean;
}

function annotate(parts: Part[]): Segment[] {
  return parts.map((part) => {
    if ('text' in part) return { text: ' '.repeat(part.text.length) };
    const name = part.label.slice(0, part.block);
    return {
      text: name + ' '.repeat(part.block - name.length),
      label: true,
      stop: part.action === 'stop',
    };
  });
}

/* -------------------------------------------------------------------------- */

export function BreachHero() {
  const [scenario, setScenario] = useState<Scenario>('redact');
  const [stage, setStage] = useState<Stage>('idle');
  const [armed, setArmed] = useState(false);
  const frameRef = useRef<HTMLDivElement>(null);
  const timers = useRef<number[]>([]);

  const run = RUNS[scenario];

  const clear = useCallback(() => {
    timers.current.forEach(window.clearTimeout);
    timers.current = [];
  }, []);

  const play = useCallback(() => {
    clear();
    setStage('idle');
    // One frame at idle first, or a replay of the same scenario has nothing to
    // transition from and the sweep appears already finished.
    timers.current.push(
      window.setTimeout(() => {
        MARKS.forEach(([s, at]) => {
          timers.current.push(window.setTimeout(() => setStage(s), at));
        });
      }, 40),
    );
  }, [clear]);

  /* Plays when it is reached, not on load - the hero sits below the headline
     and a run that finished before the reader arrived is a run they missed. */
  useEffect(() => {
    const el = frameRef.current;
    if (!el || armed) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setArmed(true);
          io.disconnect();
        }
      },
      { threshold: 0.35 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [armed]);

  useEffect(() => {
    if (!armed) return;
    play();
    return clear;
  }, [armed, scenario, play, clear]);

  useEffect(() => clear, [clear]);

  const at = stage === 'idle' ? -1 : ORDER.indexOf(stage);
  const swept = at >= ORDER.indexOf('inspect');
  const decided = at >= ORDER.indexOf('decide');
  const acted = at >= ORDER.indexOf('act');
  const recorded = at >= ORDER.indexOf('record');
  const blocked = scenario === 'block';

  const settled = acted
    ? blocked
      ? 'var(--signal-blocked)'
      : 'var(--signal-redacted)'
    : 'rgba(242,242,240,0.36)';

  return (
    <figure style={{ margin: 0 }} aria-label="How one request is handled, end to end">
      {/* Which request is being run. Two tabs, because the ordinary case and the
          credential case are different claims and both need showing. */}
      <div
        role="tablist"
        aria-label="Example request"
        style={{ display: 'flex', gap: 4, marginBottom: 12, flexWrap: 'wrap' }}
      >
        {(Object.keys(RUNS) as Scenario[]).map((k) => {
          const on = k === scenario;
          return (
            <button
              key={k}
              role="tab"
              aria-selected={on}
              onClick={() => setScenario(k)}
              style={{
                font: 'var(--type-label)', letterSpacing: 0, cursor: 'pointer',
                border: 'none', borderRadius: 'var(--r-pill)', padding: '7px 14px',
                background: on ? 'var(--ink)' : 'transparent',
                color: on ? 'var(--ink-inverse)' : 'var(--text-quiet)',
                boxShadow: on ? 'none' : 'inset 0 0 0 1px var(--border-hairline)',
                transition: 'background-color var(--d-fast) var(--ease-out), color var(--d-fast) var(--ease-out)',
              }}
            >
              {RUNS[k].tab}
            </button>
          );
        })}
      </div>

      <div
        ref={frameRef}
        style={{
          background: 'var(--surface-dark)', borderRadius: 'var(--r-16)',
          boxShadow: 'var(--sh-3)', overflow: 'hidden',
        }}
      >
        {/* Where it was going, and what happened to it. */}
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '14px 20px',
            boxShadow: 'inset 0 -1px 0 var(--border-on-dark)', flexWrap: 'wrap',
          }}
        >
          <span className="zt-mono-sm" style={{ color: 'var(--text-on-dark-quiet)' }}>
            POST /v1/chat/completions
          </span>
          <span aria-hidden style={{ color: 'rgba(242,242,240,0.22)' }}>&#8594;</span>
          <span
            className="zt-mono-sm"
            style={{
              color: acted && blocked ? 'rgba(242,242,240,0.22)' : 'var(--text-on-dark-quiet)',
              textDecoration: acted && blocked ? 'line-through' : 'none',
              transition: 'color var(--d-base) var(--ease-out)',
            }}
          >
            hive-core
          </span>
          <span style={{ flex: 1, minWidth: 12 }} />
          <span
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 7,
              opacity: at >= 0 ? 1 : 0, transition: 'opacity var(--d-base) var(--ease-out)',
            }}
          >
            <span
              aria-hidden
              style={{
                width: 6, height: 6, borderRadius: '50%', flex: '0 0 auto',
                background: settled,
                transition: 'background-color var(--d-base) var(--ease-out)',
              }}
            />
            {/* The dot carries the colour; the word carries the meaning. A
                signal ink is desaturated by design and does not clear 4.5:1
                against the dark surface at 12px, so the word stays inverse. */}
            <span className="zt-mono-sm" style={{ color: 'var(--ink-inverse)' }}>
              {acted ? run.verdict : 'inspecting'}
            </span>
          </span>
        </div>

        {/* The stage rail: where the payload is, in the gateway's own words. */}
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 0, padding: '11px 20px',
            boxShadow: 'inset 0 -1px 0 var(--border-on-dark)', overflowX: 'auto',
          }}
        >
          {RAIL.map(([s, label], i) => {
            const idx = ORDER.indexOf(s);
            const done = at > idx;
            const here = at === idx;
            return (
              <span key={s} style={{ display: 'inline-flex', alignItems: 'center', flex: '0 0 auto' }}>
                {i > 0 ? (
                  <span
                    aria-hidden
                    style={{
                      width: 26, height: 1, margin: '0 9px',
                      background: 'rgba(242,242,240,0.11)', position: 'relative',
                      overflow: 'hidden', flex: '0 0 auto',
                    }}
                  >
                    <span
                      style={{
                        position: 'absolute', inset: 0, transformOrigin: 'left center',
                        transform: at >= idx ? 'scaleX(1)' : 'scaleX(0)',
                        background: 'rgba(242,242,240,0.36)',
                        transition: 'transform var(--d-base) var(--ease-out)',
                      }}
                    />
                  </span>
                ) : null}
                <span
                  className="zt-mono-sm"
                  aria-current={here ? 'step' : undefined}
                  style={{
                    color: here
                      ? 'var(--ink-inverse)'
                      : done
                      ? 'rgba(242,242,240,0.52)'
                      : 'rgba(242,242,240,0.22)',
                    transition: 'color var(--d-base) var(--ease-out)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {label}
                </span>
              </span>
            );
          })}
        </div>

        {/* The payload, and the scan that crosses it. */}
        <div style={{ position: 'relative', padding: '24px 20px 26px', overflowX: 'auto' }}>
          <div
            className="zt-mono"
            style={{
              color: 'var(--text-on-dark-body)', whiteSpace: 'pre', lineHeight: 2.3,
              fontSize: 'clamp(11px, 1.3vw, 14px)', position: 'relative', zIndex: 1,
            }}
          >
            {run.parts.map((part, i) =>
              'text' in part ? (
                <span key={i}>{part.text}</span>
              ) : (
                <Block key={i} {...part} decided={decided} acted={acted} />
              ),
            )}

            {/* What the detectors called each span, annotated under the span
                itself. The line is built at the same monospace metrics as the
                payload and padded with spaces, so every label lands under the
                block it names without a single measurement in JavaScript. */}
            <div
              aria-hidden
              style={{
                marginTop: 2,
                opacity: decided ? 1 : 0,
                transform: decided ? 'none' : 'translateY(-3px)',
                transition:
                  'opacity var(--d-base) var(--ease-out), transform var(--d-base) var(--ease-out)',
              }}
            >
              {annotate(run.parts).map((seg, i) =>
                seg.label ? (
                  <span
                    key={i}
                    style={{
                      color: seg.stop && acted ? 'var(--signal-blocked)' : 'rgba(242,242,240,0.52)',
                      transition: 'color var(--d-base) var(--ease-out)',
                    }}
                  >
                    {seg.text}
                  </span>
                ) : (
                  <span key={i}>{seg.text}</span>
                ),
              )}
            </div>
          </div>

          {/* A trailing wash behind a 1px leading rule. It crosses the payload,
              because detection reads all of it, and settles into the colour of
              the decision once one has been made. */}
          <div
            aria-hidden
            style={{
              position: 'absolute', top: 0, bottom: 0, left: 0, zIndex: 0, pointerEvents: 'none',
              width: swept ? '100%' : '0%',
              background: 'linear-gradient(to right, rgba(242,242,240,0.02), rgba(242,242,240,0.06))',
              borderRight: `1px solid ${acted ? settled : 'rgba(242,242,240,0.36)'}`,
              opacity: recorded ? 0 : 1,
              transition:
                'width var(--d-drain) var(--ease-out), border-color var(--d-base) var(--ease-out), opacity var(--d-slow) var(--ease-out)',
            }}
          />
        </div>

        {/* What the caller gets back. */}
        <div
          style={{
            padding: '18px 20px 20px',
            boxShadow: 'inset 0 1px 0 var(--border-on-dark)',
            opacity: acted ? 1 : 0,
            transform: acted ? 'none' : 'translateY(4px)',
            transition: 'opacity var(--d-base) var(--ease-out), transform var(--d-base) var(--ease-out)',
          }}
        >
          <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--ink-inverse)', maxWidth: '62ch' }}>
            {run.headline}
          </p>
          {run.lines.map((l, i) => (
            <p
              key={l}
              className="zt-mono-sm"
              style={{
                margin: i === 0 ? '10px 0 0' : '6px 0 0',
                color: i === 0 ? 'var(--text-on-dark-quiet)' : 'rgba(242,242,240,0.36)',
              }}
            >
              {l}
            </p>
          ))}
          <p
            className="zt-mono-sm"
            style={{
              margin: '14px 0 0', color: 'rgba(242,242,240,0.36)',
              opacity: recorded ? 1 : 0, transition: 'opacity var(--d-base) var(--ease-out)',
            }}
          >
            {run.trailer}
          </p>
        </div>
      </div>

      <figcaption
        style={{
          display: 'flex', alignItems: 'center', gap: 14, marginTop: 12, flexWrap: 'wrap',
        }}
      >
        <button
          onClick={play}
          style={{
            font: 'var(--type-label)', letterSpacing: 0, cursor: 'pointer', border: 'none',
            background: 'transparent', color: 'var(--text-quiet)', padding: '4px 0',
            textDecoration: 'underline', textDecorationColor: 'var(--border-line)',
            textUnderlineOffset: 3, transition: 'color var(--d-fast) var(--ease-out)',
          }}
        >
          Replay
        </button>
        <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>
          Example data. Values render at their true length and are never shown.
        </span>
      </figcaption>
    </figure>
  );
}

function Block({
  block,
  label,
  action,
  decided,
  acted,
}: {
  block: number;
  label: string;
  action: 'tokenise' | 'stop';
  decided: boolean;
  acted: boolean;
}) {
  const stopped = action === 'stop' && acted;
  return (
    <span
      style={{ position: 'relative', display: 'inline-block', whiteSpace: 'pre' }}
      title={`${label} - ${action === 'stop' ? 'matched a blocking rule' : 'tokenised'}`}
    >
      {/* Sized by character count, so the block is the length of what it stands in for. */}
      <span style={{ visibility: 'hidden' }}>{' '.repeat(block)}</span>
      <span
        aria-label={`${label}, redacted`}
        style={{
          position: 'absolute', left: 0, right: 0, top: '0.16em', bottom: '0.24em',
          background: 'rgba(242,242,240,0.11)',
          boxShadow: `inset 0 0 0 1px rgba(242,242,240,${decided ? 0.36 : 0.22})`,
          borderRadius: 'var(--r-2)',
          transition: 'box-shadow var(--d-base) var(--ease-out)',
        }}
      />
      {/* A 1px signal rule is the largest a signal colour is ever allowed to be. */}
      <span
        aria-hidden
        style={{
          position: 'absolute', left: 0, bottom: '0.02em', height: 1,
          width: stopped ? '100%' : '0%',
          background: 'var(--signal-blocked)',
          transition: 'width var(--d-base) var(--ease-out)',
        }}
      />
    </span>
  );
}
