import { Section, SectionHead, Source, Pull } from './Shared';

/**
 * Move 3: the competitors, named, with what they are genuinely good at.
 *
 * Naming the competition and crediting it is the whole credibility play here.
 * A procurement officer has already heard of Palo Alto; pretending otherwise
 * loses the room. The argument is not that they are bad - it is that every one
 * of them is structurally disqualified for this buyer, for reasons that are not
 * fixable with a roadmap item.
 */

const VENDORS: Array<{ name: string; origin: string; strength: string; miss: string }> = [
  {
    name: 'Protect AI → Palo Alto Networks',
    origin: 'US · acquired 2025, reported $500-700M',
    strength: 'Full AI-lifecycle security with enormous distribution behind it.',
    miss: 'Enterprise platform sale. No sovereign deployment path, no Indian identifier coverage.',
  },
  {
    name: 'Lakera → Check Point',
    origin: 'Switzerland/Israel · acquired 2025, reported ~$300M',
    strength: 'The best published runtime numbers in the category - >98% detection, sub-50ms, <0.5% false positives (their claim).',
    miss: 'Built for prompt injection and attack defence. That is ingress. Citizen data leaving is egress, and it is a different problem.',
  },
  {
    name: 'Prompt Security → SentinelOne',
    origin: 'US/Israel · acquired 2025, reported $250-300M',
    strength: 'Closest to the developer-workflow use case.',
    miss: 'Absorbed into an XDR roadmap. Foreign hosting, no government procurement path.',
  },
  {
    name: 'WitnessAI',
    origin: 'US · $58M, Jan 2026',
    strength: 'The strongest independent. Shipped agentic governance - monitoring which MCP servers and tools agents touch.',
    miss: 'Observability-and-governance framing, enterprise CISO motion. No India residency, no GeM route.',
  },
  {
    name: 'Harmonic Security',
    origin: 'UK/US · ~$26M',
    strength: 'Best time-to-first-insight, and a safe-vs-risky usage classifier at the right granularity.',
    miss: 'Requires an endpoint agent, which makes it structurally blind to server-side citizen-service pipelines - which is where government actually leaks.',
  },
  {
    name: 'Cyberhaven',
    origin: 'US',
    strength: 'Data lineage is a genuine technical moat. They own the defining 39.7% statistic on this page.',
    miss: 'Endpoint-first and lineage-first. AI egress is one surface among many.',
  },
  {
    name: 'Skyflow · Private AI · Strac',
    origin: 'US / Canada',
    strength: 'Tokenisation and PII detection across 50+ languages - closest to our reversibility layer.',
    miss: 'Vault-as-a-service. The integration burden lands on the buyer, and there is no policy engine over agent traffic.',
  },
  {
    name: 'Occludra · Grepture · OrcaRouter',
    origin: 'EU / US · 2026 cohort',
    strength: 'Security-first LLM proxies. Reversible mask-and-restore already shipping, sub-50ms budgets. The same shape as us.',
    miss: 'No compositional risk scoring, no self-authoring detector registry, no tamper-evident ledger, no Indian identifier or 22-language coverage, no sovereign deployment.',
  },
  {
    name: 'Presidio + LiteLLM',
    origin: 'US · open source, free',
    strength: 'Presidio is MIT-licensed and natively wired into LiteLLM with mask and block modes. LiteLLM has 53k+ GitHub stars and can restore masked tokens in responses.',
    miss: 'A library and a router. No policy engine, no multi-tenancy, no evidence trail, no learning. Skip one config step and prompts flow unprotected.',
  },
];

const GAPS: Array<[string, string, string]> = [
  ['G1', 'Sovereignty', 'Every vendor above is foreign-headquartered and SaaS-first. A control that ships citizen data offshore in order to stop citizen data going offshore is not a control.'],
  ['G2', 'Wrong insertion point', 'Browser extensions and endpoint agents govern employees on laptops. Government’s largest leak surface is server-side citizen-service pipelines and agent tool results, where no human is present.'],
  ['G3', 'Entity-level blindness', 'Detectors classify spans independently. A record with pincode, DOB, gender, scheme and block re-identifies a person and contains no flaggable entity. Every entity-based tool passes it.'],
  ['G4', 'No Indian identifier depth', 'Aadhaar-format, PAN, ABHA, EPIC, ration card, PPO, scheme-specific IDs - and names transliterated across 22 scheduled languages. Generic NER trained on Western corpora underperforms on all of it.'],
  ['G5', 'Blocking-first design', 'Block the request and the officer uses their phone instead. The Finance Ministry advisory and the CISA incident are the same lesson twice: blocking manufactures shadow AI.'],
  ['G6', 'No audit-grade evidence', 'Logs show detection after exposure. There is no tamper-evident record a DPO, a CAG auditor or a court will accept as proof that nothing left.'],
  ['G7', 'Cost scales with traffic', 'LLM-based guardrails cost more every year adoption grows. Government budgets are fixed annually and voted in advance. A control with unbounded opex is unprocurable.'],
  ['G8', 'No procurement path', 'No GeM listing, no STQC certification, no CERT-In empanelled audit trail, dollar pricing, no Indian entity to contract with, no support inside Indian time zones.'],
];

export function Competitors() {
  return (
    <>
      <Section id="gaps">
        <SectionHead
          step="02 · The competition"
          title="Every serious AI-security company is headquartered somewhere else."
          lead="The category consolidated almost entirely into foreign platform vendors in eighteen months. These are good products built by good teams, and each one is credited here for what it genuinely does well. None of them was built for this buyer."
        />

        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {VENDORS.map((v) => (
            <div
              key={v.name}
              style={{
                display: 'grid', gridTemplateColumns: 'minmax(220px,300px) minmax(0,1fr)',
                gap: 32, padding: '22px 0',
                boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
              }}
            >
              <div>
                <div style={{ font: 'var(--type-label)' }}>{v.name}</div>
                <div style={{ marginTop: 5 }}><Source>{v.origin}</Source></div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 24 }}>
                <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>
                  {v.strength}
                </p>
                <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-strong)' }}>
                  {v.miss}
                </p>
              </div>
            </div>
          ))}
        </div>

        <p style={{ margin: '20px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-faint)', maxWidth: '70ch' }}>
          Acquisition values are as reported in trade press, not disclosed. Vendor performance
          figures are the vendors&rsquo; own published claims.
        </p>
      </Section>

      <Section ground="card">
        <SectionHead
          step="02 · The gaps"
          title="Eight gaps, and none of them close with a roadmap item."
          lead="These are the reasons a government buyer cannot simply buy the market leader. They are structural - a consequence of where these products sit and who they were built to sell to."
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(340px,1fr))', gap: '36px 48px' }}>
          {GAPS.map(([id, title, body]) => (
            <div key={id} style={{ display: 'grid', gridTemplateColumns: '38px minmax(0,1fr)', gap: 16 }}>
              <span className="zt-mono-sm" style={{ color: 'var(--text-faint)', paddingTop: 3 }}>{id}</span>
              <div>
                <h3 style={{ font: 'var(--type-h3)', margin: '0 0 8px' }}>{title}</h3>
                <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)', maxWidth: '46ch' }}>
                  {body}
                </p>
              </div>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 48 }}>
          <Pull sub="Not a better rule list. A different unit of analysis, an economic model that runs the other way, and a procurement path nobody can buy quickly.">
            Four of these eight are things a competitor cannot fix by shipping faster.
          </Pull>
        </div>
      </Section>
    </>
  );
}
