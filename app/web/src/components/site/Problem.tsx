import { Section, SectionHead, Stat, Pull } from './Shared';

/**
 * Move 2: why it exists, in one idea and four numbers.
 *
 * One band, not two. The idea is that prohibition is the only control most
 * organisations have and it does not work, and the numbers are the evidence -
 * so they share a ground instead of the heading getting a stripe of its own.
 */
export function Problem() {
  return (
    <Section id="problem" ground="dark" tight>
      <SectionHead
        step="01 · The problem"
        onDark
        title="A ban is not a control. It is a blind spot with paperwork."
        lead="Most organisations have exactly two options today: ban AI and watch people use it anyway, or allow it and hope nothing sensitive is in the prompt."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 36 }}>
        <Stat onDark value="39.7%" body="of AI interactions carry sensitive data." source="Cyberhaven, 2026" />
        <Stat onDark value="66%" body="of staff have used AI in ways that break their own policy." source="PagerDuty/Wakefield, 2026" />
        <Stat onDark value="23%" body="of leaders actually have visibility into it. 78% believe they do." source="Reported, May 2026" />
        <Stat onDark value="₹25.5 cr" body="average cost of one data breach in India. Shadow AI adds ₹1.79 crore." source="IBM, 2026" />
      </div>

      <div style={{ marginTop: 44 }}>
        <Pull onDark sub="Nobody typed it, no browser extension sees it, no endpoint DLP sees it, and it leaves anyway.">
          And the fastest-growing surface is the one no human touches: agent tool
          results entering context on hop three of a chain nobody reviewed.
        </Pull>
      </div>
    </Section>
  );
}
