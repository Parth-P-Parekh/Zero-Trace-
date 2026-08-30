import { Section, SectionHead, Source, Pull, Stat } from './Shared';

/**
 * Move 6: how we enter, why they choose us, and where this goes in five years.
 *
 * The seven moves are numbered because they are genuinely ordered - move 4
 * before move 1 and the tender kills you - which is the only condition under
 * which numbering carries information rather than decoration.
 */

const MOVES: Array<[string, string]> = [
  ['States before the Centre', 'State IT departments have shorter cycles, a single accountable IT Secretary, and real AI budgets. Central ministries take 12 to 24 months. Start with the states that already have live AI and a secretary who has publicly committed to it.'],
  ['Sell the audit, not the software', 'Nobody buys an unbudgeted security product. Everyone can sanction a ₹4 to 8 lakh assessment. Four weeks in shadow mode, then a report that says: in 30 days, N citizen records and M credential classes would have left, and here is the tamper-evident evidence. The report creates the budget line for the following year. This is the single most important move in the plan.'],
  ['Be a component, not a procurement', 'Bhashini, IndiaAI, NIC platforms and state DPI stacks are already funded and already sanctioned. Integrating as a guardrail inside a programme that exists skips the hardest step in government sales.'],
  ['Earn the procurement path early, in parallel', 'GeM listing, STQC certification, CERT-In empanelled audit partner, MeitY engagement. Unglamorous, slow, and the one moat a better-funded foreign competitor cannot buy quickly. Start at month one, not month twelve.'],
  ['Channel through the SIs who hold the contracts', 'NIC and NICSI, and the government practices at TCS, Wipro and Infosys. They own the relationships and the delivery capacity. Sell to them as a component they can attach margin to, not as a competitor.'],
  ['Use the DPDP clock before it expires', 'Enforcement powers begin 13 November 2026; full compliance is due 13 May 2027; penalties reach ₹250 crore for a security failure, ₹200 crore for a notification failure, and they stack per violation category. Government bodies are Data Fiduciaries under the same Act. There is a window where the deadline opens doors, and it closes once everyone has bought something.'],
  ['Fund the government cycle with enterprise', 'BFSI, healthtech, insurance and GCCs buy in weeks and need the identical product. Self-serve, PLG, Razorpay. Government is the mission; enterprise is the payroll.'],
];

const HORIZON: Array<[string, string, string]> = [
  ['Year 1', 'Prove and land', 'Two paid audits with any government body - a municipal corporation counts. Convert one into a Portal or Department licence. GeM and STQC processes started. Enterprise self-serve live. Target: one government contract and ₹1 crore combined ARR by month twelve.'],
  ['Year 2', 'Qualify and repeat', 'GeM listing live and one SI partnership signed, so the second department is an order rather than a tender. Two to three states running. One national programme integration. The audit becomes a repeatable product with a fixed delivery cost.'],
  ['Year 3', 'Become the specification', 'Compositional detection, reversibility and tamper-evident evidence written into technical specifications by the buyers themselves. At that point competitors are non-compliant rather than merely more expensive, which is a far better position than being cheaper.'],
  ['Years 4-5', 'Category default, then export', 'The Indian public-sector standard for AI egress control, funded by an enterprise base that no longer depends on it. Then the same wedge in markets facing the identical contradiction - sovereign data obligations against a mandate to adopt AI at scale. The product does not change; the identifier pack and the procurement path do.'],
];

const RISKS: Array<[string, string]> = [
  ['Government cycles run 9 to 18 months', 'You cannot fund a company on this alone, which is why the enterprise wedge is not optional.'],
  ['A foreign vendor localises', 'Palo Alto or Check Point can announce Indian hosting in a quarter. Race to empanelment and to the compositional moat - neither of which is a hosting decision.'],
  ['DPDP enforcement slips again', 'It has moved before. Lead with the exposure report and close with the deadline, never the reverse.'],
  ['Procurement blocks a startup on turnover', 'Common and rarely negotiable. Go through an SI or an empanelled partner for the first large tenders.'],
];

export function GTM() {
  return (
    <>
      <Section id="gtm">
        <SectionHead
          step="05 · Go to market"
          title="Seven moves, in an order that matters."
          lead="Government procurement punishes improvisation. These are ordered because the sequence is the strategy: start the certification path in month one and it is ready when the first large tender lands; start it in month twelve and you watch someone else win on paperwork."
        />

        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {MOVES.map(([title, body], i) => (
            <div
              key={title}
              style={{
                display: 'grid', gridTemplateColumns: '44px minmax(200px,260px) minmax(0,1fr)',
                gap: 24, padding: '22px 0', alignItems: 'baseline',
                boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
              }}
            >
              <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>
                {String(i + 1).padStart(2, '0')}
              </span>
              <div style={{ font: 'var(--type-label)' }}>{title}</div>
              <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>{body}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* The differentiation question, answered directly. */}
      <Section ground="dark">
        <SectionHead
          step="05 · Why us"
          onDark
          title="Why an organisation picks this over a vendor with a hundred times the distribution."
          lead="Not because the product is better at everything. Because four of the eight gaps are structural, and a buyer who needs all four has exactly one option."
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap: 40 }}>
          <Why
            title="They cannot host here quickly enough to matter"
            body="A foreign vendor can announce Indian hosting in a quarter, and some will. What they cannot compress is GeM listing, STQC certification and CERT-In empanelment - a qualification path measured in years that has to be finished before the tender, not during it."
          />
          <Why
            title="They classify spans; we score sets"
            body="Compositional re-identification is a different unit of analysis, not a longer rule list. Adding it means rebuilding the detection core around a population prior. That is a rewrite, and rewrites do not happen inside an acquired product absorbed into an XDR roadmap."
          />
          <Why
            title="Their cost curve points the wrong way"
            body="A guardrail that calls a model per request gets more expensive every year adoption grows. Against a budget voted annually in advance, that is unprocurable regardless of how good the detection is. Ours converges toward a CPU floor."
          />
          <Why
            title="They govern laptops; the leak is server-side"
            body="Endpoint agents and browser extensions watch employees typing. Citizen data leaves through service pipelines and agent tool results where no human is present. That is an architectural position, not a feature gap."
          />
        </div>

        <div style={{ marginTop: 48 }}>
          <Pull onDark sub="Every number on this page is sourced, every modelled figure is labelled as modelled, and every competitor is credited with what it genuinely does well. For a security product sold into procurement, that is not modesty - it is the shortest path to being believed.">
            The honest version of this pitch is also the most persuasive one.
          </Pull>
        </div>
      </Section>

      {/* Twelve months, then five years. */}
      <Section ground="card">
        <SectionHead
          step="05 · The horizon"
          title="Tomorrow, and then the next five years."
          lead="The category is growing fast enough that the question is not whether this market exists but who holds the procurement path when it arrives."
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 36, marginBottom: 52 }}>
          <Stat value="$7.69B" body="AI prompt security market by 2030, growing at 31.1% a year." source="Research and Markets, 2026" />
          <Stat value="$7.99B" body="Inference guardrails for LLMs by 2030, at 32.5% a year." source="Market research, 2026" />
          <Stat value="11 weeks" body="Until DPDP enforcement powers begin on 13 November 2026. Full compliance follows on 13 May 2027." source="DPDP Rules 2025 · MeitY" />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {HORIZON.map(([when, what, body]) => (
            <div
              key={when}
              style={{
                display: 'grid', gridTemplateColumns: '110px minmax(180px,220px) minmax(0,1fr)',
                gap: 24, padding: '22px 0', alignItems: 'baseline',
                boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
              }}
            >
              <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>{when}</span>
              <div style={{ font: 'var(--type-label)' }}>{what}</div>
              <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>{body}</p>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 48 }}>
          <div className="zt-eyebrow" style={{ marginBottom: 18 }}>Honest risks</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 28 }}>
            {RISKS.map(([risk, mitigation]) => (
              <div key={risk}>
                <p style={{ margin: '0 0 6px', font: 'var(--type-body-sm)', color: 'var(--text-strong)' }}>{risk}</p>
                <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>{mitigation}</p>
              </div>
            ))}
          </div>
        </div>
      </Section>
    </>
  );
}

function Why({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <h3 style={{ font: 'var(--type-h3)', color: 'var(--ink-inverse)', margin: '0 0 12px', maxWidth: '22ch' }}>
        {title}
      </h3>
      <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)', maxWidth: '42ch' }}>
        {body}
      </p>
    </div>
  );
}
