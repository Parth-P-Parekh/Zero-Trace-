import { Section, SectionHead, Source, Pull } from './Shared';

/**
 * Move 5: who we are actually selling to, named.
 *
 * "Government and regulated enterprise" is not an ICP, it is a category. The
 * qualifying test used throughout this section is narrow on purpose: the
 * organisation must already run AI, already hold citizen or regulated data, and
 * have one accountable owner who can sanction a purchase. Everything here meets
 * all three.
 */

type Target = { name: string; why: string; signal: string };

const TIER_1: Target[] = [
  {
    name: 'Karnataka · Centre for e-Governance',
    why: 'Runs a dedicated AI-ML Cell that vets AI projects before rollout, under a government order requiring departments to seek approval before launching an AI initiative. That is a single chokepoint every state AI deployment already passes through - and a guardrail is exactly what a vetting body has no way to enforce today.',
    signal: 'AI-ML Cell · responsible-AI committee · state AI policy and AI university announced',
  },
  {
    name: 'Maharashtra · Dept of Electronics, IT & AI',
    why: 'Created as an independent department by cabinet decision in April 2026, with the IT Directorate becoming a commissionerate. It has already cleared Sarvam AI’s sovereign workspace for around 2,500 government users at ₹11.26 crore across two years. The AI is live, the budget is sanctioned, and there is no egress control around it.',
    signal: 'Sarvam "Indus" deployment cleared · ₹11.26 cr over two years · dedicated AI policy',
  },
  {
    name: 'Telangana · IT, E&C Department',
    why: 'Partnered with Meta to put generative AI into e-governance and is building an AI City in Hyderabad. Both put frontier models directly in front of citizen-service data, and the state has the shortest decision cycle of the three.',
    signal: 'Meta e-governance partnership · AI City Hyderabad',
  },
  {
    name: 'Kerala · Gujarat · Odisha',
    why: 'Second wave. Each has an IT Secretary with a public AI commitment, live citizen-service platforms, and a procurement cycle measured in months rather than years.',
    signal: 'Active state AI programmes',
  },
];

const TIER_2: Target[] = [
  {
    name: 'Bhashini · MeitY',
    why: 'The single highest-value integration on this list. Bhashini is embedded in DigiLocker, UMANG, MyGov, CoWIN, IRCTC and police documentation, and every translation hop duplicates the egress surface. It moved to sovereign Indian cloud and GPU infrastructure in Feb 2026, which means the platform owner is already thinking about exactly this problem.',
    signal: '22 scheduled languages · already sovereign-hosted',
  },
  {
    name: 'NIC and NICSI',
    why: 'Builds and hosts most central and state systems. Selling here is selling once and deploying many times - and NICSI is a rate-contract route that skips fresh tendering for every department.',
    signal: 'The delivery layer for central and state IT',
  },
  {
    name: 'IndiaAI Mission',
    why: 'A ₹10,371.92 crore outlay already sanctioned and already spending. Being a safety component inside a funded national programme skips the hardest step in government sales: creating a new budget line.',
    signal: '₹10,371.92 cr outlay · MeitY',
  },
  {
    name: 'DigiLocker · UMANG',
    why: 'The two largest citizen-facing document and service platforms in the country. Any AI feature either one ships touches identity documents at population scale.',
    signal: 'DigiLocker 72.43 cr users, 5,437 doc types · UMANG 11.66 cr users, 2,575 services',
  },
];

const TIER_3: Target[] = [
  { name: 'e-Sanjeevani', why: 'Health data is the highest-sensitivity class in every framework including DPDP, and teleconsultation summarisation is an obvious AI target.', signal: '48 crore+ consultations' },
  { name: 'DBT Mission', why: 'Beneficiary datasets, bank details and eligibility attributes - the exact composition that defeats entity-level detection.', signal: '₹52 lakh crore · 318 schemes · 56 ministries' },
  { name: 'State police documentation', why: 'FIR text, victim and accused identity, witness details. Bhashini is already integrated. A leak here is a physical-safety event.', signal: 'Bhashini-integrated' },
  { name: 'I4C · Ministry of Home Affairs', why: 'Owns the national cybercrime picture and the ₹22,495 crore loss number. The buyer most likely to already believe the problem statement.', signal: 'CFCFRMS · ₹11,158 cr saved by rapid reporting' },
];

export function ICP() {
  return (
    <>
      <Section id="who" ground="card">
        <SectionHead
          step="04 · Who we sell to"
          title="Three tiers, and every one of them already runs AI on citizen data."
          lead="The qualifying test is narrow on purpose. The organisation must already have frontier models in production, already hold citizen or regulated data, and have one accountable owner who can sanction a purchase. An organisation missing any of the three is a two-year sale, not a pipeline."
        />

        <Tier
          label="Tier 1 · States before the Centre"
          note="Shorter cycles, a single accountable IT Secretary, and real AI budgets. Central ministries take 12 to 24 months; a state takes one."
          targets={TIER_1}
        />
        <Tier
          label="Tier 2 · National platform owners"
          note="Be a component of a programme that already exists and is already funded, rather than a new procurement."
          targets={TIER_2}
        />
        <Tier
          label="Tier 3 · Highest-sensitivity departments"
          note="Where a leak is unrecoverable, and where the exposure report writes itself."
          targets={TIER_3}
        />
      </Section>

      <Section>
        <SectionHead
          step="04 · The second wedge"
          title="Regulated enterprise is not a distraction. It is the payroll."
          lead="Government is the mission and the moat. But a government cycle runs 9 to 18 months with 60 to 180-day payment terms, and no company survives on that alone. The regulated private sector needs the identical product, is under the identical DPDP clock, and buys in weeks."
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap: 40 }}>
          <Segment
            name="BFSI global capability centres"
            body="Around 170 BFSI GCCs run 333 units in India, roughly 8% of all centres in the country, and more than a third of them opened in the last five years. RBI and SEBI already mandate data localisation, so the obligation exists before the conversation starts."
            source="Zinnov · GCC industry reporting, 2026"
          />
          <Segment
            name="AI-first GCCs generally"
            body="India hosts more than 2,100 global capability centres employing over 2.3 million people, and roughly 80% of those launched in 2026 are AI-first in mandate. AI is the reason the centre exists, which means model traffic is the core workload, not a side project."
            source="GCC industry reporting, mid-2026"
          />
          <Segment
            name="Healthtech and insurance"
            body="ABDM-linked health platforms and IRDAI-regulated insurers hold the highest-sensitivity data classes under DPDP, and both are actively deploying summarisation and claims-processing models."
            source="DPDP Act 2023 · sectoral regulators"
          />
        </div>

        <div style={{ marginTop: 48 }}>
          <Pull sub="An enterprise deal closes in weeks and funds the government cycle that closes in quarters. Inverting that order is how a company with the right product runs out of money before the tender lands.">
            Government is the mission and the moat. Enterprise is the payroll. Do not invert it.
          </Pull>
        </div>
      </Section>
    </>
  );
}

function Tier({ label, note, targets }: { label: string; note: string; targets: Target[] }) {
  return (
    <div style={{ marginBottom: 52 }}>
      <div style={{ marginBottom: 22 }}>
        <div className="zt-eyebrow" style={{ marginBottom: 10 }}>{label}</div>
        <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '64ch' }}>
          {note}
        </p>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {targets.map((t) => (
          <div
            key={t.name}
            style={{
              display: 'grid', gridTemplateColumns: 'minmax(220px,300px) minmax(0,1fr)',
              gap: 32, padding: '20px 0',
              boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
            }}
          >
            <div>
              <div style={{ font: 'var(--type-label)' }}>{t.name}</div>
              <div style={{ marginTop: 6 }}><Source>{t.signal}</Source></div>
            </div>
            <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>{t.why}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function Segment({ name, body, source }: { name: string; body: string; source: string }) {
  return (
    <div>
      <h3 style={{ font: 'var(--type-h3)', margin: '0 0 12px', maxWidth: '20ch' }}>{name}</h3>
      <p style={{ margin: '0 0 12px', font: 'var(--type-body-sm)', color: 'var(--text-body)', maxWidth: '42ch' }}>
        {body}
      </p>
      <Source>{source}</Source>
    </div>
  );
}
