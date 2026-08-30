import { Section, SectionHead, Source, Stat, Pull } from './Shared';

/**
 * Move 2: why it exists, in one idea and four numbers.
 *
 * The idea is that prohibition is the only control most organisations have, and
 * it demonstrably fails. One event proves it better than a page of survey data,
 * so one event leads and the numbers corroborate.
 */
export function Problem() {
  return (
    <>
      <Section id="problem" ground="card" tight>
        <SectionHead
          step="01 · The problem"
          title="A ban is not a control. It is a blind spot with paperwork."
          lead="Most organisations have exactly two options today: ban AI and watch people use it anyway, or allow it and hope nothing sensitive is in the prompt."
        />

        <Pull sub="In August 2025 the acting director of the United States' national cyber-defence agency uploaded documents marked For Official Use Only into public ChatGPT - while most of his department was blocked from it. India's Finance Ministry had issued its own advisory that January. Politico, TechRepublic, Reuters.">
          If a ban does not hold at the top of a cyber-defence agency, it does not hold
          anywhere.
        </Pull>
      </Section>

      <Section ground="dark" tight>
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
    </>
  );
}
