import { Section, SectionHead, Stat } from './Shared';
import { RevealGroup, RevealItem } from './Reveal';

/**
 * Move 2: why it exists, in one idea and four numbers.
 *
 * One band, not two. The idea is that prohibition is the only control most
 * organisations have and it does not work; the numbers are the evidence, and
 * each one carries a link to where it came from rather than a name a reader
 * would have to go and search for.
 */

const FIGURES: Array<{ value: string; body: string; source: string; href: string }> = [
  {
    value: '39.7%',
    body: 'of AI interactions carry sensitive data.',
    source: 'Cyberhaven research',
    href: 'https://www.cyberhaven.com/research',
  },
  {
    value: '66%',
    body: 'of staff have used AI in ways that break their own policy.',
    source: 'PagerDuty / Wakefield',
    href: 'https://www.pagerduty.com/newsroom/',
  },
  {
    value: '78%',
    body: 'of leaders believe they have visibility into it. 23% actually do.',
    source: 'Reported, May 2026',
    href: 'https://www.cyberhaven.com/research',
  },
  {
    value: '₹25.5 cr',
    body: 'average cost of one breach in India. Shadow AI adds ₹1.79 crore.',
    source: 'IBM Cost of a Data Breach',
    href: 'https://www.ibm.com/reports/data-breach',
  },
];

export function Problem() {
  return (
    <Section id="problem" ground="dark" tight>
      <SectionHead
        step="01 · The problem"
        onDark
        title="A ban is not a control. It is a blind spot with paperwork."
        lead="Two options exist today: ban AI and watch people use it anyway, or allow it and hope nothing sensitive is in the prompt."
      />

      <RevealGroup
        style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 36 }}
      >
        {FIGURES.map((f, i) => (
          <RevealItem key={f.value} index={i}>
            <Stat onDark value={f.value} body={f.body} source={f.source} href={f.href} />
          </RevealItem>
        ))}
      </RevealGroup>
    </Section>
  );
}
