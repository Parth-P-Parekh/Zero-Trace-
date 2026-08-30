import { Section, SectionHead } from './Shared';
import { RevealGroup, RevealItem } from './Reveal';

/**
 * Move 7: the moat, measured in what it would cost someone else to cross it.
 *
 * A moat is not a feature; it is a distance. So each row carries the distance in
 * the right-hand column, in mono, because it is a measurement - and the four
 * measurements are the argument. A reader who takes nothing else from the page
 * should be able to scan that column alone and understand why a better-funded
 * competitor does not simply do this next quarter.
 *
 * One line per moat, and no paragraph anywhere. The first draft explained each
 * one in three sentences, which is how a moat stops sounding like a moat: the
 * more it needs defending, the less structural it reads. A claim and its price,
 * on one line, is the strongest form this section has.
 *
 * On the dark ground, because it is the loudest thing the system allows and this
 * is the claim the whole pitch rests on.
 */

const MOATS: Array<{ title: string; line: string; cost: string }> = [
  {
    title: 'Empanelment cannot be compressed',
    line: 'Certification finishes before a tender opens, not during it.',
    cost: 'started, never bought',
  },
  {
    title: 'Risk is scored over the set',
    line: 'A record with no name and no ID still identifies one person.',
    cost: 'a detection-core rewrite',
  },
  {
    title: 'The system writes its own detectors',
    line: 'Every catch becomes a deterministic rule, and the model call retires.',
    cost: 'falls as traffic grows',
  },
  {
    title: 'The evidence is a chain, not a log',
    line: 'One-way tokens, no plaintext held, nothing to hand over.',
    cost: 'nothing to reverse',
  },
];

export function Moat() {
  return (
    <Section id="moat" ground="dark" tight>
      <SectionHead
        step="06 · The moat"
        onDark
        title="Four gaps that are structural, and the price of closing them."
        lead="A buyer who needs all four has one option. The right-hand column is why."
      />

      <RevealGroup>
        <RevealItem className="zt-moat zt-moat-head">
          <div />
          <div />
          <div />
          <div className="zt-eyebrow" style={{ color: 'rgba(242,242,240,0.52)', textAlign: 'right' }}>
            What it would take
          </div>
        </RevealItem>
        <div className="zt-hair zt-hair-dark" />

        {MOATS.map((m, i) => (
          <RevealItem key={m.title} index={i} className="zt-lift zt-lift-dark">
            <div className="zt-moat">
              <span className="zt-mono-sm" style={{ color: 'rgba(242,242,240,0.36)' }}>
                {String(i + 1).padStart(2, '0')}
              </span>

              <div style={{ font: 'var(--type-label)', color: 'var(--ink-inverse)' }}>
                {m.title}
              </div>

              <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)', maxWidth: '52ch' }}>
                {m.line}
              </p>

              <div className="zt-moat-cost">
                <span className="zt-mono-sm" style={{ color: 'var(--ink-inverse)' }}>{m.cost}</span>
              </div>
            </div>
            <div className="zt-hair zt-hair-dark" style={{ ['--i' as string]: i }} />
          </RevealItem>
        ))}
      </RevealGroup>

      <RevealItem index={5}>
        <p
          style={{
            margin: '30px 0 0', font: 'var(--type-body-sm)',
            color: 'var(--text-on-dark-quiet)', maxWidth: '62ch',
          }}
        >
          And one that is a position rather than a gap: the leak is server-side, on a hop no person
          is present for. An endpoint product cannot reach it without becoming a different product.
        </p>
      </RevealItem>
    </Section>
  );
}
