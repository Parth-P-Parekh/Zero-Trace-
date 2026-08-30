import { Section, SectionHead, Source, Stat, Pull, Rows, Row } from './Shared';

/**
 * Move 2: the problem, and the data behind it.
 *
 * The argument is not "AI leaks data" - everyone has heard that. It is that
 * government's only available control today is prohibition, and prohibition is
 * demonstrably failing at the highest levels of two governments. The evidence
 * leads; the numbers corroborate.
 */

const SURFACES: Array<[string, string, string]> = [
  ['Grievance and helpline bots', 'Name, mobile, address, case ID, and the grievance text itself. "My pension has not come, my husband died in March" is health, financial and family status in one line.', 'UMANG · MyGov · state CM helplines'],
  ['Document processing', 'Scanned IDs, signatures, family details, property and land records, court filings.', 'DigiLocker: 72.43 crore users, 5,437 document types'],
  ['Translation pipelines', 'Everything above, duplicated through a second AI hop. Translation doubles the egress surface and is almost never governed.', 'Bhashini · 22 scheduled languages'],
  ['Officer drafting', 'Pre-decisional policy, unpublished data, named individuals - noting, RTI responses, tenders, parliamentary answers.', 'Exactly what the Finance Ministry advisory was written to stop'],
  ['Software and DevOps', 'Connection strings, API keys, schema dumps, and sample beneficiary records pasted in to debug. One leaked production string is a breach of the database behind it, not of one record.', 'NIC · state IT departments · e-gov vendors'],
  ['Scheme analytics', 'Beneficiary IDs, bank details, eligibility attributes.', 'DBT: ₹52 lakh crore, 318 schemes, 56 ministries'],
  ['Police documentation', 'FIR text, victim and accused identity, witness details. A leaked victim identity is a physical-safety event, not an IT incident.', 'Bhashini is already integrated here'],
  ['Health', 'Symptoms, diagnoses, prescriptions, patient identity - the highest-sensitivity class in every framework, including DPDP.', 'e-Sanjeevani: 48 crore+ consultations'],
  ['Agentic and RAG systems', 'Full rows from live citizen databases, retrieved on hop 3 of a chain no human reviewed. Nobody typed it. No browser extension sees it. No endpoint DLP sees it. It leaves anyway.', 'The surface nobody governs'],
];

export function Problem() {
  return (
    <>
      <Section id="problem" ground="card">
        <SectionHead
          step="01 · The problem"
          title="Government runs on citizen data. AI runs on prompts. Nobody is watching the gap."
          lead="Every AI feature a government ships sends citizen data to infrastructure it does not own, cannot audit, and cannot subpoena. Today there are two options: ban AI and watch officers use it anyway on personal devices, or allow AI and hope nothing sensitive is in the prompt."
        />

        {/* The evidence that prohibition fails, before any statistic. Two events
            are more persuasive than a survey, and these two are unanswerable. */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(320px,1fr))', gap: 40 }}>
          <Evidence
            when="29 January 2025"
            what="India's Ministry of Finance told officers that AI tools on office computers put the confidentiality of government data at risk, and to strictly avoid them. Australia banned DeepSeek from government devices that February. Italy and Germany followed."
            source="Reuters · PTI · Australian government policy"
          />
          <Evidence
            when="August 2025, surfaced January 2026"
            what="The acting director of the United States' national cyber-defence agency uploaded documents marked For Official Use Only into public ChatGPT - while most of his department was blocked from it. Automated sensors caught it. A department-level review followed."
            source="Politico · TechRepublic, reported"
          />
        </div>

        <div style={{ marginTop: 44 }}>
          <Pull sub="Meanwhile the same governments are mandated to adopt AI at population scale. The IndiaAI Mission carries an outlay of ₹10,371.92 crore, and Bhashini is already embedded in DigiLocker, UMANG, MyGov, CoWIN, IRCTC and police documentation. Adopt AI, or protect citizen data - governments are currently forced to choose. ZeroTrace removes the choice.">
            The head of a national cyber-defence agency, under an active ban, leaked
            sensitive documents into a consumer chatbot. If a ban does not hold there, it
            does not hold anywhere.
          </Pull>
        </div>
      </Section>

      {/* The numbers. Dark, because this is the section that has to land hardest. */}
      <Section ground="dark">
        <SectionHead
          step="01 · The numbers"
          onDark
          title="The exposure is real, and nobody is measuring it."
          lead="India does not publish a consolidated figure for government data-breach loss. That absence is itself the finding. Here is what the published record does support."
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 40 }}>
          <Stat onDark size="lg" value="₹22,495 cr" body="lost by Indians to cybercrime in 2025, a 24% jump year on year." source="Ministry of Home Affairs, Feb 2026" />
          <Stat onDark size="lg" value="2,04,844" body="cybersecurity incidents involving Indian government organisations in a single year." source="Parliament reply, Dec 2024 (2023 data)" />
          <Stat onDark size="lg" value="₹25.5 cr" body="average cost of one data breach in India in 2026, an all-time high, up 15.9%." source="IBM Cost of a Data Breach Report 2026" />
          <Stat onDark size="lg" value="₹1.79 cr" body="added to a breach by shadow AI, one of India's top three cost amplifiers." source="IBM Cost of a Data Breach Report 2026" />
        </div>

        <div style={{ marginTop: 56, display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: 40 }}>
          <Pull
            onDark
            sub="₹782 crore allocated in the Union Budget 2025-26, against ₹22,495 crore lost by citizens in the same period. The maximum DPDP penalty for a single security failure is ₹250 crore - one-third of the entire national cybersecurity allocation."
          >
            ₹1 : ₹29
          </Pull>
          <Pull
            onDark
            sub="66% of staff say they have used AI in ways that violate policy, rising to 72% in organisations above 1,500 people; 34% have entered customer data into public AI tools. 78% of executives believe they have a clear picture of AI usage. 23% actually do. A breach now takes 247 days to identify and contain - up, reversing a five-year decline."
          >
            A ban is not a control. It is a blind spot with paperwork.
          </Pull>
        </div>

        <p style={{ margin: '40px 0 0', maxWidth: '70ch', font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)' }}>
          <strong style={{ fontWeight: 'var(--w-medium)', color: 'var(--ink-inverse)' }}>Modelled, and labelled as modelled:</strong>{' '}
          if 0.1% of those 2,04,844 annual government-organisation incidents result in a material
          breach at the Indian average of ₹25.5 crore, that is roughly ₹5,200 crore of annual
          government breach exposure. At 1%, ₹52,000 crore. Adjust the rate and the number moves.
          The point is that nobody currently measures it.
        </p>

        <p style={{ margin: '24px 0 0', maxWidth: '70ch', font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)' }}>
          <strong style={{ fontWeight: 'var(--w-medium)', color: 'var(--ink-inverse)' }}>The counter-number, before someone else raises it:</strong>{' '}
          IBM's per-industry tables put the public sector at the lowest average breach cost of any
          industry. Those models measure what the institution pays - forensics, notification,
          downtime. They do not price what the citizen pays. A leaked Aadhaar-linked record cannot
          be re-issued, cancelled or refunded. The cost sits outside the balance sheet the survey
          measures, which is exactly why it never gets budgeted for.{' '}
          <Source onDark>IBM per-industry table, 2025 edition</Source>
        </p>
      </Section>

      {/* Where it actually happens. A list, because ten uniform items in cards
          would be ten cards saying "we made a grid". */}
      <Section>
        <SectionHead
          step="01 · The surface"
          title="Nine places a government already touches a frontier model."
          lead="Each one is a documented deployment pattern, not a hypothetical."
        />
        <Rows>
          {SURFACES.map(([lead, body, meta]) => (
            <Row key={lead} lead={lead} meta={<Source>{meta}</Source>}>
              {body}
            </Row>
          ))}
        </Rows>

        <div style={{ marginTop: 48, display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 32 }}>
          <Contrast label="Whose data" enterprise="Customers who chose the company" government="Citizens with no opt-out" />
          <Contrast label="Scale of one database" enterprise="Thousands to millions" government="Hundreds of millions. Aadhaar has issued 1.44 billion numbers" />
          <Contrast label="Remedy after a leak" enterprise="Churn, refund, lawsuit" government="None. You cannot re-issue a citizen's identity" />
          <Contrast label="Political cost" enterprise="Share price" government="Parliamentary questions, CAG audit, judicial scrutiny" />
        </div>
      </Section>
    </>
  );
}

function Evidence({ when, what, source }: { when: string; what: string; source: string }) {
  return (
    <div>
      <Source>{when}</Source>
      <p style={{ font: 'var(--type-body)', color: 'var(--text-body)', margin: '12px 0 10px', maxWidth: '46ch' }}>
        {what}
      </p>
      <Source>{source}</Source>
    </div>
  );
}

function Contrast({ label, enterprise, government }: { label: string; enterprise: string; government: string }) {
  return (
    <div>
      <div className="zt-eyebrow" style={{ marginBottom: 12 }}>{label}</div>
      <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-faint)' }}>
        Enterprise: {enterprise}
      </p>
      <p style={{ margin: '6px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-strong)' }}>
        Government: {government}
      </p>
    </div>
  );
}
