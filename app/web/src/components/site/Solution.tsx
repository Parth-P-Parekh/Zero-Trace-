import { Section, SectionHead, Source } from './Shared';
import { Reveal, RevealGroup, RevealItem } from './Reveal';
import { run } from '@/lib/benchmark';
import { exact, micros, percent } from '@/lib/format';

/**
 * Move 4: what it does, and what happened when it was tested.
 *
 * The product and the evidence used to be two full sections, one of them dark,
 * and together they were the longest stretch of the page. They are one section
 * now: four claims, then the one dark card that carries what the run actually
 * measured. That is the design system's own rule - one dark card per screen,
 * spent on the thing that matters most - and here the thing that matters most
 * is that the numbers are counts rather than projections.
 *
 * Every figure comes from `data/benchmark.json` rather than from a string typed
 * here, so the landing page and the console cannot drift apart.
 */

const { integrity, outcomes, latencyAsync, meta, byStage, byClass } = run;

const composite = byClass.find((c) => c.entityClass === 'QUASI_IDENTIFIER_SET')?.count ?? 0;
const deterministic = byStage.S0 / Object.values(byStage).reduce((a, b) => a + b, 0);

const CLAIMS: Array<[string, string]> = [
  [micros(latencyAsync.p50_us), 'added to a request, against a model call of 300 to 2,000 ms.'],
  ['One package', 'a dependency, not an infrastructure project. No proxy tier, no endpoint agent.'],
  ['One container', 'no GPU, no external classifier. Runs on what you already have.'],
  ['Zero telemetry', 'in your VPC or air-gapped. The product cannot be the leak.'],
];

const MEASURED: Array<[string, string, string]> = [
  [
    percent(integrity.credential_block_rate, 1),
    'of requests carrying a live key were stopped before the model saw one.',
    `${exact(integrity.credential_records)} planted`,
  ],
  [
    exact(composite),
    'records identified where no single field in them was identifying.',
    'the case entity filters have no answer for',
  ],
  [
    String(outcomes.verify_failures),
    'redactions where the original was still in the payload we sent.',
    `${exact(outcomes.redactions_verified)} re-read before dispatch`,
  ],
];

export function Solution() {
  return (
    <Section id="solution" tight>
      <SectionHead
        step="03 · The product"
        title="Nothing sensitive leaves. Everything still works."
        lead="Sensitive values are swapped for stand-ins on the way out, so the answer still lands. A credential is the exception: a key is never tokenised, so a prompt carrying one is stopped."
      />

      <RevealGroup
        style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(210px,1fr))', gap: 28 }}
      >
        {CLAIMS.map(([value, body], i) => (
          <RevealItem key={value} index={i}>
            <div
              className="zt-nums"
              style={{
                font: 'var(--w-medium) var(--t-21)/var(--lh-snug) var(--font-core)',
                letterSpacing: 'var(--tr-heading)', marginBottom: 8,
              }}
            >
              {value}
            </div>
            <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)', maxWidth: '32ch' }}>
              {body}
            </p>
          </RevealItem>
        ))}
      </RevealGroup>

      {/* The one dark card. It carries the measurement, because the measurement
          is the only part of this section a competitor cannot also assert. */}
      <Reveal
        delay={1}
        style={{
          marginTop: 56, background: 'var(--surface-dark)', borderRadius: 'var(--r-16)',
          boxShadow: 'var(--sh-3)', padding: '34px 34px 30px',
        }}
      >
        <div className="zt-on-dark">
          <div className="zt-eyebrow" style={{ color: 'rgba(242,242,240,0.52)', marginBottom: 16 }}>
            Measured, not modelled
          </div>
          <p
            style={{
              font: 'var(--w-regular) clamp(21px, 2.2vw, 26px)/var(--lh-snug) var(--font-core)',
              letterSpacing: 'var(--tr-heading)', margin: 0, maxWidth: '30ch',
              color: 'var(--ink-inverse)',
            }}
          >
            Five million requests, with the answers known in advance.
          </p>
          <p
            style={{
              font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)',
              margin: '14px 0 34px', maxWidth: '58ch',
            }}
          >
            You cannot measure a guardrail on live traffic, because nobody knows what was in it.
            So the traffic was written: {exact(meta.records)} requests with the answer decided
            before the test ran. {percent(deterministic, 0)} of what it found needed no model
            call at all.
          </p>

          <RevealGroup
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(190px,1fr))', gap: 32 }}
          >
            {MEASURED.map(([value, body, note], i) => (
              <RevealItem key={value} index={i}>
                <div
                  className="zt-nums"
                  style={{
                    font: 'var(--w-semibold) clamp(26px, 2.8vw, 33px)/var(--lh-tight) var(--font-core)',
                    letterSpacing: 'var(--tr-display)', color: 'var(--ink-inverse)', marginBottom: 10,
                  }}
                >
                  {value}
                </div>
                <p style={{ margin: '0 0 8px', font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)', maxWidth: '32ch' }}>
                  {body}
                </p>
                <Source onDark>{note}</Source>
              </RevealItem>
            ))}
          </RevealGroup>

          <p style={{ margin: '32px 0 0', maxWidth: '64ch' }}>
            <Source onDark>
              It also raised a false alarm on {percent(integrity.false_positive_rate, 1)} of clean
              traffic, and missed keys typed with spaces in them. Both numbers are on the Detection
              screen in the console rather than left off this page.
            </Source>
          </p>
        </div>
      </Reveal>
    </Section>
  );
}
