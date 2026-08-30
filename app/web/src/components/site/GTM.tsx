import { Section, SectionHead, Source } from './Shared';
import { RevealGroup, RevealItem } from './Reveal';

/**
 * Move 6: the next six months, one line each.
 *
 * The section used to run to five years and three paragraphs a move. A five-year
 * plan on a landing page is a statement of ambition, and a reader deciding
 * something this quarter cannot act on one - so what survives is the window a
 * first customer can actually be in.
 *
 * Each row is a month, a move and the rule it is pitched against, and nothing
 * else. The rule is the whole content: "sell to government" is not a plan, and
 * "Rule 155, so a purchase committee can sign it" is. The order matters more
 * than the prose, and certification is first because it is the only item that
 * money cannot speed up later.
 */

interface Move {
  when: string;
  title: string;
  line: string;
  cite?: string;
  href?: string;
}

const MOVES: Move[] = [
  {
    when: 'Month 1',
    title: 'Start certification',
    line: 'The only item money cannot speed up later, and it has to be done before a tender, not during one.',
    cite: 'STQC · CERT-In',
    href: 'https://www.stqc.gov.in/',
  },
  {
    when: 'Month 1–2',
    title: 'Open with a free exposure run',
    line: 'Thirty days in shadow mode inside their own VPC. Nothing is bought, so nothing has to be sanctioned.',
    cite: 'DPDP Rules 2025',
    href: 'https://www.meity.gov.in/data-protection-framework',
  },
  {
    when: 'Month 2–3',
    title: 'Attach to a funded programme',
    line: 'A control placed on an AI project that is already sanctioned, not a new line item beside it.',
    cite: 'IndiaAI Mission',
    href: 'https://indiaai.gov.in/',
  },
  {
    when: 'Month 3–4',
    title: 'Take the first paid order',
    line: 'One officer signs up to ₹50,000 with no quotation; a committee to ₹5,00,000 with no tender.',
    cite: 'GFR 2017, Rule 154–155',
    href: 'https://doe.gov.in/general-financial-rules',
  },
  {
    when: 'Month 3–4',
    title: 'Run the enterprise sale for cash',
    line: 'AI egress is an open control gap in both frameworks, and it closes in weeks rather than quarters.',
    cite: 'SEBI CSCRF',
    href: 'https://www.sebi.gov.in/legal/circulars',
  },
  {
    when: 'Month 4–6',
    title: 'Get on the rate card',
    line: 'A department that has to run a procurement will not. One that can place an order will.',
    cite: 'NICSI · GeM',
    href: 'https://gem.gov.in/',
  },
];

export function GTM() {
  return (
    <Section id="gtm" tight>
      <SectionHead
        step="05 · Go to market"
        title="Six months, six moves, and not one of them needs a tender."
        lead="Every move names the rule it is pitched against."
      />

      <RevealGroup>
        {MOVES.map((m, i) => (
          <RevealItem key={m.title} index={i} className="zt-lift">
            <div className="zt-move">
              <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>{m.when}</span>

              <div style={{ font: 'var(--type-label)' }}>{m.title}</div>

              <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)', maxWidth: '58ch' }}>
                {m.line}
              </p>

              <div className="zt-move-cite">
                {m.cite ? <Source href={m.href}>{m.cite}</Source> : null}
              </div>
            </div>
            <div className="zt-hair" style={{ ['--i' as string]: i }} />
          </RevealItem>
        ))}
      </RevealGroup>
    </Section>
  );
}
