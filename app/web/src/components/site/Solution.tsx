import { Section, SectionHead, Source, Pull, Stat } from './Shared';

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
          <Stat onDark value="0.78" body="Composite risk on a record with no name, no ID, no phone - and no flaggable entity." source="Placeholder. Formula holds; its inputs are not calibrated." />
        </div>

        <div style={{ marginTop: 44 }}>
          <Pull onDark sub="Every mainstream tool classifies spans independently. Pincode with a date of birth, a gender and an employer identifies one person, and passes every entity filter on the market. Scoring the set instead of the span is a different unit of analysis, not a longer rule list - which is why it is the hardest thing here to copy.">
            Anonymised isn&rsquo;t anonymous.
          </Pull>
        </div>
      </Section>

      <Section tight>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 44 }}>
          <Third
            label="Coherent across hops"
            title="Redaction that breaks the answer gets switched off."
            body="Format-preserving tokens stay referentially stable - the same person is the same token on hop 1 and hop 7, across sessions and restarts. The response is re-hydrated before your user sees it."
          />
          <Third
            label="The evidence layer"
            title="What would have left, if this had been off?"
            body="Every decision writes to a hash-chained ledger storing classes, offsets and hashes, never the values. The counterfactual answers the only question an auditor actually asks."
          />
          <Third
            label="India-context pack"
            title="Aadhaar-format, PAN, ABHA, EPIC, GSTIN, IFSC."
            body="With Verhoeff validation, scheme-specific beneficiary formats, and names across the 22 scheduled languages and their transliterations. Department-specific formats are learned, not quoted as a customisation."
          />
        </div>
      </Section>
    </>
  );
}

function Third({ label, title, body }: { label: string; title: string; body: string }) {
  return (
    <div>
      <div className="zt-eyebrow" style={{ marginBottom: 14 }}>{label}</div>
      <h3 style={{ font: 'var(--type-h3)', margin: '0 0 12px', maxWidth: '24ch' }}>{title}</h3>
      <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)', maxWidth: '42ch' }}>
        {body}
      </p>
    </div>
  );
}
