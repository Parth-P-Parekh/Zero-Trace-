import { Section, SectionHead, Source, Pull, Stat } from './Shared';

/**
 * Move 4: the solution, and specifically the moat.
 *
 * Two of the three moats are the load-bearing ones and each takes a paragraph
 * to make honestly, so they get prose rather than a feature grid. N1 gets the
 * dark card, because the economic argument - a guardrail whose cost saturates -
 * is the one that decides a fixed-budget government purchase.
 */

const CLAIMS: Array<[string, string, string]> = [
  ['p50 ≤25ms · p95 ≤55ms', 'Added latency', 'Inside the noise band of a cross-region model call. The category benchmark is sub-50ms, and anything slower gets switched off in production and becomes shelfware.'],
  ['One container', 'Footprint', 'No GPU, no external classifier service. Deployable on existing state data-centre and NIC-class infrastructure without new hardware procurement - which is a twelve-month process on its own.'],
  ['One line of config', 'Integration', 'Change the base URL. No code rewrite, no SDK migration, no endpoint agent rollout. An endpoint-agent deployment across a state government is a two-year programme. A config change is a Tuesday.'],
  ['Zero telemetry egress', 'Sovereignty', 'Runs fully in-country, in your VPC, or air-gapped. The product cannot be the thing that leaks. Bhashini itself moved to sovereign Indian cloud and GPU infrastructure in Feb 2026.'],
];

export function Solution() {
  return (
    <>
      <Section id="solution">
        <SectionHead
          step="03 · The solution"
          title="Nothing sensitive leaves. Everything still works."
          lead="ZeroTrace sits between your application and the model. It removes citizen data from the outbound payload, restores it in the response, and writes a tamper-evident record of every decision. Credentials are the exception: an API key or a connection string is never tokenised, so a prompt carrying one is stopped before it reaches the provider. The model gets a clean prompt. Your user gets a correct answer. The provider never sees a citizen."
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(224px,1fr))', gap: 30 }}>
          {CLAIMS.map(([value, label, body]) => (
            <div key={label}>
              <div className="zt-eyebrow" style={{ marginBottom: 12 }}>{label}</div>
              <div
                className="zt-nums"
                style={{
                  font: 'var(--w-medium) var(--t-21)/var(--lh-snug) var(--font-core)',
                  letterSpacing: 'var(--tr-heading)', marginBottom: 10,
                }}
              >
                {value}
              </div>
              <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)', maxWidth: '38ch' }}>
                {body}
              </p>
            </div>
          ))}
        </div>
      </Section>

      {/* N1. The dark card, because this is the argument that survives a budget meeting. */}
      <Section ground="dark">
        <SectionHead
          step="03 · Moat one"
          onDark
          title="Every other AI guardrail gets more expensive as you scale. This one saturates."
          lead="Most guardrails call a model on every request, so cost rises forever, linearly with adoption. ZeroTrace uses the model as a teacher, not a runtime. When the adjudicator catches a leak class the deterministic rules missed, a synthesizer writes a new deterministic detector, validates it against the full corpus - it must improve recall without regressing precision beyond 0.5% and must execute under 1.5ms - and promotes it to the fast path. The next occurrence of that class is caught in 3ms with no model call."
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: 36 }}>
          <Stat onDark value="8-12% → <3%" body="Escalation rate, launch to maturity. Each fall is a detector the system wrote for itself." source="Benchmark corpus, three runs" />
          <Stat onDark value="₹0.75 → ₹0.52" body="COGS per 1M tokens scanned, and still falling as the registry grows." source="Unit economics, modelled" />
          <Stat onDark value="Once" body="Times you pay a model to learn a pattern. Not once per request, forever." source="N1, by construction" />
        </div>

        <div style={{ marginTop: 44 }}>
          <Pull
            onDark
            sub="Because promoted detectors are deterministic, the marginal cost of the millionth request approaches the cost of a regex. For a department with a fixed annual budget and growing AI adoption, that is the difference between a line item and a liability - and it is why this is a government product rather than an enterprise one that also sells to government."
          >
            You pay to learn a pattern once, not to check for it forever.
          </Pull>
        </div>
      </Section>

      {/* N2. The technical moat - a different unit of analysis. */}
      <Section ground="card">
        <SectionHead
          step="03 · Moat two"
          title="Anonymised isn't anonymous."
          lead="Every mainstream tool classifies spans independently. Consider a beneficiary record with no name, no Aadhaar, no phone and no email - just pincode, date of birth, gender, scheme code and block. Presidio passes it. Google DLP passes it. Every entity classifier named on this page passes it."
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: 48 }}>
          <div>
            <p style={{ margin: 0, font: 'var(--type-body)', color: 'var(--text-strong)', maxWidth: '42ch' }}>
              In a village-level block, that combination identifies one person.
            </p>
            <p style={{ margin: '18px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-body)', maxWidth: '46ch' }}>
              ZeroTrace scores the <em>set</em> of quasi-identifiers against a population prior,
              returns a re-identification risk, and redacts the minimum element that breaks
              identification. That is a different unit of analysis, not a bigger rule list, which is
              why it is the hardest thing on this page for a competitor to add.
            </p>
          </div>
          <div>
            <div className="zt-eyebrow" style={{ marginBottom: 14 }}>Worked example</div>
            <div className="zt-mono-sm" style={{ color: 'var(--text-body)', lineHeight: 2 }}>
              pincode + DOB + gender + employer<br />
              entity findings: <span style={{ color: 'var(--text-faint)' }}>none</span><br />
              every entity filter: <span style={{ color: 'var(--text-faint)' }}>passes</span><br />
              composite re-identification risk:{' '}
              <span className="zt-nums" style={{ color: 'var(--ink)', fontWeight: 'var(--w-semibold)' }}>0.78</span>
            </div>
            <div style={{ marginTop: 14 }}>
              <Source>Derived, not asserted - the score is information content over the quasi-identifier set, discounted by extraction confidence</Source>
            </div>
          </div>
        </div>
      </Section>

      {/* N3 + evidence + the India pack. */}
      <Section>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: 48 }}>
          <div>
            <div className="zt-eyebrow" style={{ marginBottom: 16 }}>Moat three · reversible</div>
            <h3 style={{ font: 'var(--type-h2)', letterSpacing: 'var(--tr-heading)', margin: '0 0 16px', maxWidth: '18ch' }}>
              Redaction that breaks the answer gets switched off.
            </h3>
            <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)', maxWidth: '46ch' }}>
              ZeroTrace mints format-preserving, type-consistent tokens that stay referentially
              stable - the same citizen is the same token on hop 1 and hop 7, across sessions,
              across channels, and across a process restart. The model reasons correctly. The
              response is re-hydrated before the citizen sees it. Credentials are the exception:
              keys, connection strings and private keys are removed, never tokenised, because there
              is no legitimate reason for a secret to round-trip.
            </p>
          </div>
          <div>
            <div className="zt-eyebrow" style={{ marginBottom: 16 }}>The evidence layer</div>
            <h3 style={{ font: 'var(--type-h2)', letterSpacing: 'var(--tr-heading)', margin: '0 0 16px', maxWidth: '18ch' }}>
              What would have left, if this had been off?
            </h3>
            <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)', maxWidth: '46ch' }}>
              Every decision writes to a hash-chained, append-only ledger storing classes, offsets
              and hashes - never the values. A security product that logs the secrets it caught is a
              liability. The counterfactual report answers the only question an auditor actually
              asks, and it is the artifact that turns an assessment into a budget line.
            </p>
          </div>
        </div>

        <div style={{ marginTop: 56, paddingTop: 32, boxShadow: 'inset 0 1px 0 var(--border-hairline)' }}>
          <div className="zt-eyebrow" style={{ marginBottom: 14 }}>Indian-context detection pack</div>
          <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)', maxWidth: '72ch' }}>
            Aadhaar-format numbers with Verhoeff validation, PAN, ABHA, EPIC and voter ID, ration
            card, PPO, GSTIN, IFSC and account patterns, vehicle registration, and scheme-specific
            beneficiary ID formats - plus name and address recognition across the 22 scheduled
            languages and common transliterations. Department-specific formats are learned
            automatically by the synthesis loop rather than quoted as a customisation line item.
          </p>
        </div>
      </Section>
    </>
  );
}
