import { Section, SectionHead } from './Shared';

/**
 * Move 3: the gap, stated and not explained.
 *
 * Each line is the gap and its consequence in one breath. A title with a
 * paragraph under it asks the reader to assemble the point themselves; a
 * sentence hands it over. Four sentences, no descriptions.
 */

const GAPS: Array<[string, string]> = [
  ['They watch laptops.', 'The leak is server-side, where no human is present.'],
  ['They classify spans one at a time.', 'The record with no flaggable entity walks straight through.'],
  ['They call a model on every request.', 'Cost grows with adoption, forever, against a budget fixed once a year.'],
  ['They write logs, not proof.', 'Nothing an auditor or a court will accept as evidence that nothing left.'],
];

export function Competitors() {
  return (
    <Section id="gaps" ground="card" tight>
      <SectionHead
        step="02 · The gap"
        title="Every serious AI-security company is headquartered somewhere else."
      />

      {/* Not mono: the system reserves mono for machine data, and these are company
          names. Ramp .36 carries the same "this is a footnote" weight. */}
      <p
        style={{
          margin: '-24px 0 44px', font: 'var(--type-body-sm)',
          color: 'var(--text-faint)', maxWidth: '62ch',
        }}
      >
        Protect AI to Palo Alto. Lakera to Check Point. Prompt Security to SentinelOne. Robust
        Intelligence to Cisco.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {GAPS.map(([gap, consequence]) => (
          <p
            key={gap}
            style={{
              margin: 0, padding: '22px 0', maxWidth: '46ch',
              font: 'var(--w-regular) var(--t-21)/var(--lh-snug) var(--font-core)',
              letterSpacing: 'var(--tr-heading)',
              boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
            }}
          >
            {gap} <span style={{ color: 'var(--text-faint)' }}>{consequence}</span>
          </p>
        ))}
      </div>
    </Section>
  );
}
