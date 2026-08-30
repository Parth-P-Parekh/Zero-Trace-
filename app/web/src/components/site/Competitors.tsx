'use client';

import { useState } from 'react';
import { Section, SectionHead } from './Shared';
import { Reveal } from './Reveal';

/**
 * Move 3: the gap, stated and then shown.
 *
 * The four gaps used to sit alone in the left half of the page with nothing
 * opposite them, which asked the reader to take each one on trust. Each gap now
 * selects a panel that renders the gap as machine data - the path the leak
 * actually takes, the record that walks past an entity filter, the two cost
 * curves, the difference between a log line and a hash chain. The claim is on
 * the left and the artefact is on the right, and a reader who does not believe
 * the sentence can look at the thing.
 *
 * Mono is not a costume here. Every panel is data a gateway would emit.
 */

type Key = 'endpoint' | 'spans' | 'cost' | 'logs';

const GAPS: Array<{ key: Key; gap: string; consequence: string }> = [
  {
    key: 'endpoint',
    gap: 'They watch laptops.',
    consequence: 'The leak is server-side, where no human is present.',
  },
  {
    key: 'spans',
    gap: 'They classify spans one at a time.',
    consequence: 'The record with no flaggable entity walks straight through.',
  },
  {
    key: 'cost',
    gap: 'They call a model on every request.',
    consequence: 'Cost grows with adoption, forever, against a budget fixed once a year.',
  },
  {
    key: 'logs',
    gap: 'They write logs, not proof.',
    consequence: 'Nothing an auditor or a court will accept as evidence that nothing left.',
  },
];

export function Competitors() {
  const [active, setActive] = useState<Key>('endpoint');

  return (
    <Section id="gaps" ground="card" tight>
      <SectionHead
        step="02 · The gap"
        title="Every serious AI-security company is headquartered somewhere else."
      />

      <Reveal
        as="p"
        style={{
          margin: '-24px 0 40px', font: 'var(--type-body-sm)',
          color: 'var(--text-faint)', maxWidth: '62ch',
        }}
      >
        Protect AI to Palo Alto. Lakera to Check Point. Prompt Security to SentinelOne. Robust
        Intelligence to Cisco.
      </Reveal>

      <div className="zt-gap-grid">
        {/* The claims. Selecting one changes what is drawn beside it. */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {GAPS.map(({ key, gap, consequence }, i) => {
            const on = key === active;
            return (
              <button
                key={key}
                onClick={() => setActive(key)}
                onMouseEnter={() => setActive(key)}
                onFocus={() => setActive(key)}
                aria-pressed={on}
                style={{
                  appearance: 'none', border: 'none', background: 'transparent',
                  textAlign: 'left', cursor: 'pointer', padding: '20px 0 20px 18px',
                  position: 'relative', display: 'block', width: '100%',
                  boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
                  font: 'var(--w-regular) var(--t-21)/var(--lh-snug) var(--font-core)',
                  letterSpacing: 'var(--tr-heading)',
                  color: 'var(--text-strong)',
                }}
              >
                {/* The selection marker is a 1px rule that grows, not a fill. */}
                <span
                  aria-hidden
                  style={{
                    position: 'absolute', left: 0, top: 18, bottom: 18, width: 1,
                    background: on ? 'var(--ink)' : 'var(--border-hairline)',
                    transform: on ? 'scaleY(1)' : 'scaleY(0.35)',
                    transformOrigin: 'top center',
                    transition:
                      'transform var(--d-base) var(--ease-out), background-color var(--d-base) var(--ease-out)',
                  }}
                />
                <span style={{ opacity: on ? 1 : 0.72, transition: 'opacity var(--d-fast) var(--ease-out)' }}>
                  {gap}{' '}
                  <span style={{ color: 'var(--text-faint)' }}>{consequence}</span>
                </span>
                <span
                  className="zt-mono-sm"
                  style={{
                    display: 'block', marginTop: 10, color: 'var(--text-faint)',
                    opacity: on ? 1 : 0, transition: 'opacity var(--d-fast) var(--ease-out)',
                  }}
                >
                  {/* Not "opposite": below 960px the panel stacks under the
                      claims, and a label that names a position is wrong on half
                      the widths the page ships at. */}
                  {String(i + 1).padStart(2, '0')} · showing
                </span>
              </button>
            );
          })}
        </div>

        {/* The artefact. One panel at a time, keyed so it re-enters on change. */}
        <div className="zt-gap-panel">
          <div key={active} className="zt-panel-in">
            {active === 'endpoint' ? <PathPanel /> : null}
            {active === 'spans' ? <CompositePanel /> : null}
            {active === 'cost' ? <CostPanel /> : null}
            {active === 'logs' ? <LedgerPanel /> : null}
          </div>
        </div>
      </div>
    </Section>
  );
}

/* -------------------------------------------------------------------------- */
/* Panels                                                                      */
/* -------------------------------------------------------------------------- */

function PanelFrame({ title, children, foot }: { title: string; children: React.ReactNode; foot?: React.ReactNode }) {
  return (
    <div
      style={{
        background: 'var(--surface-dark)', borderRadius: 'var(--r-12)',
        padding: '20px 22px 22px', boxShadow: 'var(--sh-3)', height: '100%',
      }}
    >
      <div className="zt-eyebrow" style={{ color: 'rgba(242,242,240,0.52)', marginBottom: 18 }}>
        {title}
      </div>
      {children}
      {foot ? (
        <p style={{ margin: '18px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)', maxWidth: '42ch' }}>
          {foot}
        </p>
      ) : null}
    </div>
  );
}

/** Where a request actually goes, and how little of it an endpoint agent can reach. */
function PathPanel() {
  const HOPS: Array<[string, boolean]> = [
    ['person types a prompt', true],
    ['browser', true],
    ['application server', false],
    ['agent hop 2', false],
    ['agent hop 3', false],
    ['model provider', false],
  ];
  return (
    <PanelFrame title="One request, and who is watching it" foot="Endpoint and browser controls reach the first two rows. Everything below them is machine-to-machine, and it is the part that is growing.">
      <div style={{ position: 'relative', paddingLeft: 16 }}>
        <span
          aria-hidden
          style={{ position: 'absolute', left: 3, top: 8, bottom: 8, width: 1, background: 'rgba(242,242,240,0.22)' }}
        />
        {HOPS.map(([label, covered], i) => (
          <div
            key={label}
            style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '7px 0', position: 'relative' }}
          >
            <span
              aria-hidden
              style={{
                position: 'absolute', left: -16, width: 7, height: 7, borderRadius: '50%',
                background: covered ? 'rgba(242,242,240,0.52)' : 'rgba(242,242,240,0.22)',
                boxShadow: '0 0 0 4px var(--surface-dark)',
              }}
            />
            <span
              className="zt-mono-sm"
              style={{ color: covered ? 'rgba(242,242,240,0.52)' : 'var(--ink-inverse)' }}
            >
              {label}
            </span>
            <span style={{ flex: 1 }} />
            <span className="zt-mono-sm" style={{ color: 'rgba(242,242,240,0.36)' }}>
              {covered ? 'watched' : 'no human present'}
            </span>
            {i === 1 ? (
              <span
                aria-hidden
                style={{
                  position: 'absolute', left: -16, right: 0, bottom: -4, height: 1,
                  backgroundImage: 'repeating-linear-gradient(to right, rgba(242,242,240,0.22) 0 4px, transparent 4px 8px)',
                }}
              />
            ) : null}
          </div>
        ))}
      </div>
    </PanelFrame>
  );
}

/** A record where no single field is identifying and the set is. */
function CompositePanel() {
  const FIELDS: Array<[string, string]> = [
    ['pin', '560001'],
    ['dob', '1994-03-11'],
    ['role', 'district judge'],
    ['gender', 'f'],
  ];
  return (
    <PanelFrame title="A record every entity filter passes" foot="No name, no ID, nothing to flag field by field. Scored as a set, it resolves to one person.">
      <div>
        {FIELDS.map(([k, v]) => (
          <div
            key={k}
            style={{
              display: 'grid', gridTemplateColumns: '72px minmax(0,1fr) auto', gap: 12,
              padding: '9px 0', alignItems: 'baseline',
              boxShadow: 'inset 0 -1px 0 var(--border-on-dark)',
            }}
          >
            <span className="zt-mono-sm" style={{ color: 'rgba(242,242,240,0.36)' }}>{k}</span>
            <span className="zt-mono-sm" style={{ color: 'var(--text-on-dark-body)' }}>{v}</span>
            <span className="zt-mono-sm" style={{ color: 'rgba(242,242,240,0.36)' }}>clean</span>
          </div>
        ))}
        <div
          style={{
            display: 'grid', gridTemplateColumns: '72px minmax(0,1fr) auto', gap: 12,
            padding: '13px 0 0', alignItems: 'baseline',
          }}
        >
          <span className="zt-mono-sm" style={{ color: 'rgba(242,242,240,0.52)' }}>as a set</span>
          <span className="zt-mono-sm" style={{ color: 'var(--ink-inverse)' }}>k = 1</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span
              aria-hidden
              style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--signal-redacted)' }}
            />
            {/* The dot carries the colour, the word carries the meaning - a
                desaturated signal ink does not clear 4.5:1 at 12px on dark. */}
            <span className="zt-mono-sm" style={{ color: 'var(--ink-inverse)' }}>redacted</span>
          </span>
        </div>
      </div>
    </PanelFrame>
  );
}

/**
 * Two cost curves, drawn rather than charted. A polyline over the ramp is the
 * readme's one sanctioned functional gradient, and here it happens to be the
 * argument: one line is a slope and the other is a floor.
 */
function CostPanel() {
  return (
    <PanelFrame title="Cost per million requests, against adoption" foot="A model call per request is a slope. Deterministic detectors that the system writes for itself converge on a CPU floor.">
      <svg viewBox="0 0 280 120" width="100%" height="120" role="img" aria-label="Two cost curves: per-request model calls rise with adoption, deterministic detection falls to a floor" style={{ display: 'block' }}>
        <defs>
          <linearGradient id="zt-cost-fade" x1="0" x2="1">
            <stop offset="0" stopColor="#F2F2F0" stopOpacity="0.02" />
            <stop offset="1" stopColor="#F2F2F0" stopOpacity="0.11" />
          </linearGradient>
        </defs>
        <line x1="0" y1="119.5" x2="280" y2="119.5" stroke="rgba(242,242,240,0.22)" strokeWidth="1" />
        <line x1="0.5" y1="0" x2="0.5" y2="120" stroke="rgba(242,242,240,0.11)" strokeWidth="1" />
        <path d="M0 96 L280 96 L280 120 L0 120 Z" fill="url(#zt-cost-fade)" />
        {/* Theirs: rises with adoption. */}
        <polyline
          points="0,104 56,92 112,74 168,50 224,28 280,8"
          fill="none" stroke="rgba(242,242,240,0.52)" strokeWidth="1.5"
        />
        {/* Ours: falls to the floor and stays. */}
        <polyline
          points="0,86 56,64 112,44 168,34 224,30 280,29"
          fill="none" stroke="#F2F2F0" strokeWidth="1.5"
          transform="translate(0,58)"
        />
      </svg>
      <div style={{ display: 'flex', gap: 20, marginTop: 12, flexWrap: 'wrap' }}>
        <span className="zt-mono-sm" style={{ color: 'rgba(242,242,240,0.52)' }}>theirs · per-request model call</span>
        <span className="zt-mono-sm" style={{ color: 'var(--ink-inverse)' }}>ours · deterministic hot path</span>
      </div>
    </PanelFrame>
  );
}

/** A log line, and the hash-chained entry that replaces it. */
function LedgerPanel() {
  return (
    <PanelFrame title="What an auditor is handed" foot="A log says what a service claims happened. A chained entry means changing any earlier record breaks every hash after it.">
      <div style={{ paddingBottom: 16, marginBottom: 16, boxShadow: 'inset 0 -1px 0 var(--border-on-dark)' }}>
        <div className="zt-mono-sm" style={{ color: 'rgba(242,242,240,0.36)', marginBottom: 8 }}>a log line</div>
        <div className="zt-mono-sm" style={{ color: 'var(--text-on-dark-body)', wordBreak: 'break-all' }}>
          2026-08-30T11:04:22Z redacted 3 spans actor=svc-refunds
        </div>
        <div className="zt-mono-sm" style={{ color: 'rgba(242,242,240,0.36)', marginTop: 8 }}>
          editable, replayable, proves nothing
        </div>
      </div>
      <div>
        <div className="zt-mono-sm" style={{ color: 'rgba(242,242,240,0.36)', marginBottom: 8 }}>a ledger entry</div>
        {([['seq', '104871'], ['prev', '9f2c…a41d'], ['hash', '3b70…c8e2'], ['verify', 'ok']] as Array<[string, string]>).map(([k, v]) => (
          <div key={k} style={{ display: 'flex', gap: 14, padding: '4px 0' }}>
            <span className="zt-mono-sm" style={{ color: 'rgba(242,242,240,0.36)', width: 46 }}>{k}</span>
            <span className="zt-mono-sm" style={{ color: v === 'ok' ? 'var(--ink-inverse)' : 'var(--text-on-dark-body)' }}>{v}</span>
          </div>
        ))}
      </div>
    </PanelFrame>
  );
}
