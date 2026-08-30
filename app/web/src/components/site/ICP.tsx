import { Section, SectionHead, Source } from './Shared';

/**
 * Move 5: who buys it. Names and a signal, no essays.
 *
 * The qualifying test is the only prose here, because it is the part that makes
 * the list a pipeline rather than a wish.
 */

const PUBLIC: Array<[string, string]> = [
  ['Karnataka · Centre for e-Governance', 'An AI-ML Cell already vets every departmental AI project. One chokepoint, nothing to enforce with.'],
  ['Maharashtra · Dept of Electronics, IT & AI', 'Sarvam workspace cleared for ~2,500 users, ₹11.26 cr. AI live, budget sanctioned, no egress control.'],
  ['Telangana · IT, E&C', 'Meta partnership for gen-AI in e-governance. AI City in Hyderabad.'],
  ['Bhashini · MeitY', 'Embedded in DigiLocker, UMANG, MyGov, CoWIN, IRCTC. Every translation hop doubles the surface.'],
  ['NIC and NICSI', 'Builds and hosts most central and state systems. Sell once, deploy many times.'],
  ['DigiLocker · UMANG', '72.43 crore and 11.66 crore users. Identity documents at population scale.'],
];

const PRIVATE: Array<[string, string]> = [
  ['BFSI capability centres', '~170 GCCs running 333 units. RBI and SEBI already mandate data localisation.'],
  ['AI-first GCCs', '2,100+ centres, 2.3M people. ~80% of 2026 launches are AI-first by mandate.'],
  ['Health and insurance', 'ABDM platforms and IRDAI insurers hold the highest-sensitivity classes under DPDP.'],
];

export function ICP() {
  return (
    <Section id="who" ground="card" tight>
      <SectionHead
        step="04 · Who buys it"
        title="Already running AI, already holding regulated data, one accountable owner."
        lead="An organisation missing any of those three is a two-year sale, not a pipeline. These are not."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(320px,1fr))', gap: 48 }}>
        <Column label="Public sector · the mission" rows={PUBLIC} />
        <Column
          label="Regulated enterprise · the payroll"
          rows={PRIVATE}
          note="A government cycle runs 9 to 18 months with 60 to 180-day payment terms. Enterprise buys in weeks and needs the identical product. Inverting that order is how a company with the right product runs out of money before the tender lands."
        />
      </div>
    </Section>
  );
}

function Column({
  label,
  rows,
  note,
}: {
  label: string;
  rows: Array<[string, string]>;
  note?: string;
}) {
  return (
    <div>
      <div className="zt-eyebrow" style={{ marginBottom: 18 }}>{label}</div>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {rows.map(([name, why]) => (
          <div key={name} style={{ padding: '14px 0', boxShadow: 'inset 0 -1px 0 var(--border-hairline)' }}>
            <div style={{ font: 'var(--type-label)', marginBottom: 4 }}>{name}</div>
            <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>{why}</p>
          </div>
        ))}
      </div>
      {note ? (
        <p style={{ margin: '20px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-body)', maxWidth: '46ch' }}>
          {note}
        </p>
      ) : null}
    </div>
  );
}
