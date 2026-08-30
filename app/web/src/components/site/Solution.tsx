import { Section, SectionHead, Source, Stat } from './Shared';

/**
 * Move 4: what it does, and the three things that cannot be copied quickly.
 *
 * N1 keeps the dark ground because a guardrail whose cost falls as it scales is
 * the claim that decides a fixed-budget purchase. The other two get a paragraph
 * each and no more.
 */

/** Third field is a caveat, rendered at ramp .36 like every other attribution. */
const CLAIMS: Array<[string, string, string?]> = [
  ['p50 ≤25ms', 'Added latency, inside the noise band of a cross-region model call.',
    'Placeholder. Design budget, not yet measured.'],
  ['One container', 'No GPU, no external classifier. Runs on infrastructure you already have.'],
  ['One package', 'A dependency, not an infrastructure project. No proxy tier, no gateway, no endpoint agent.'],
  ['Zero telemetry', 'Fully in-country, in your VPC, or air-gapped. The product cannot be the leak.'],
];

export function Solution() {
  return (
    <>
      <Section id="solution" tight>
        <SectionHead
          step="03 · The product"
          title="Nothing sensitive leaves. Everything still works."
          lead="ZeroTrace redacts sensitive data on the way out and restores it on the way back, so the answer still lands. Credentials are the exception: a key is never tokenised, so a prompt carrying one is stopped."
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(224px,1fr))', gap: 30 }}>
          {CLAIMS.map(([value, body, note]) => (
            <div key={value}>
              <div
                className="zt-nums"
                style={{
                  font: 'var(--w-medium) var(--t-21)/var(--lh-snug) var(--font-core)',
                  letterSpacing: 'var(--tr-heading)', marginBottom: 10,
                }}
              >
                {value}
              </div>
              <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)', maxWidth: '34ch' }}>
                {body}
              </p>
              {note ? (
                <p style={{ margin: '8px 0 0' }}>
                  <Source>{note}</Source>
                </p>
              ) : null}
            </div>
          ))}
        </div>
      </Section>

      <Section ground="dark" tight>
        <SectionHead
          step="03 · The moat"
          onDark
          title="Every other AI guardrail gets more expensive as you scale. This one saturates."
          lead="The model is a teacher, not a runtime. When it catches a leak class the deterministic rules missed, a detector is written, validated against the full corpus, and promoted to the fast path. The next occurrence is caught in 3ms with no model call - so you pay to learn a pattern once, not to check for it forever."
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: 36 }}>
          <Stat onDark value="8-12% → <3%" body="Escalation rate, launch to maturity." source="Placeholder. Target, not yet measured." />
          <Stat onDark value="₹0.75 → ₹0.52" body="COGS per 1M tokens scanned, still falling." source="Placeholder. Tracks model cost, not yet measured." />
        </div>

      </Section>

    </>
  );
}
