import { Section, SectionHead, Source } from './Shared';

/**
 * Move 3: the competition, credited and then disqualified.
 *
 * Nine vendors in a table was the honest version and the unreadable one. The
 * consolidation is one line, and only the four gaps that are structural survive
 * - the ones a competitor cannot close by shipping faster.
 */

const GAPS: Array<[string, string, string]> = [
  ['G1', 'Wrong insertion point', 'Endpoint agents and browser extensions watch people typing. The leak is server-side, in service pipelines and agent tool results where no human is present.'],
  ['G2', 'Entity-level blindness', 'Detectors classify spans one at a time. A record with pincode, DOB, gender and employer identifies one person and contains no flaggable entity. Every entity tool passes it.'],
  ['G3', 'Cost scales with traffic', 'A guardrail that calls a model per request gets more expensive every year adoption grows. Against a budget fixed annually, that is unprocurable however good it is.'],
  ['G4', 'No audit-grade evidence', 'Logs show detection after exposure. There is no tamper-evident record an auditor or a court will accept as proof that nothing left.'],
];

export function Competitors() {
  return (
    <Section id="gaps" tight>
      <SectionHead
        step="02 · The gap"
        title="Every serious AI-security company is headquartered somewhere else."
        lead="Protect AI went to Palo Alto, Lakera to Check Point, Prompt Security to SentinelOne, Robust Intelligence to Cisco - the category consolidated into foreign platform vendors in eighteen months. They are good products. Four things none of them do are structural rather than roadmap items."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: '32px 44px' }}>
        {GAPS.map(([id, title, body]) => (
          <div key={id} style={{ display: 'grid', gridTemplateColumns: '36px minmax(0,1fr)', gap: 14 }}>
            <span className="zt-mono-sm" style={{ color: 'var(--text-faint)', paddingTop: 3 }}>{id}</span>
            <div>
              <h3 style={{ font: 'var(--type-h3)', margin: '0 0 8px' }}>{title}</h3>
              <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)', maxWidth: '44ch' }}>
                {body}
              </p>
            </div>
          </div>
        ))}
      </div>

      <p style={{ margin: '32px 0 0' }}>
        <Source>Acquisition values as reported in trade press, not disclosed.</Source>
      </p>
    </Section>
  );
}
