import { Section, SectionHead, Source } from './Shared';
import { Reveal, RevealGroup, RevealItem } from './Reveal';

/**
 * Move 5: who buys it, and the exact desk it enters through.
 *
 * A list of organisation names is a wish. What makes it a pipeline is naming
 * the office inside each one that already owns the problem and already has the
 * authority to act on it - so every row is a post, a committee or a contract
 * vehicle rather than a logo.
 *
 * It is a list of names and nothing else. The first draft gave every row two
 * lines of justification and ran to a screen and a half, which is a briefing
 * document rather than a landing page: a reader either recognises "the
 * department CISO" as the right desk or they are not the buyer, and no amount
 * of explanation on this page changes which. The near column keeps a handful of
 * words because it is the one being acted on; the far column is bare, because
 * naming it is the whole point of it being there.
 */

interface Entry {
  where: string;
  why?: string;
  href?: string;
}

const PUBLIC_NOW: Entry[] = [
  { where: 'The department CISO', why: 'named by mandate, owns what leaves', href: 'https://www.cert-in.org.in/PDF/guidelinesgovtentities.pdf' },
  { where: 'State e-governance AI cell', why: 'already vets every AI project', href: 'https://ceg.karnataka.gov.in/' },
  { where: 'NIC and NICSI rate card', why: 'ordered, not tendered', href: 'https://nicsi.nic.in/' },
  { where: 'State Data Centre egress', why: 'one deploy, every department' },
];

const PUBLIC_NEXT: Entry[] = [
  { where: 'STQC Certificate of Conformance', href: 'https://www.stqc.gov.in/' },
  { where: 'CERT-In empanelment', href: 'https://www.cert-in.org.in/' },
  { where: 'GeM catalogue listing', href: 'https://gem.gov.in/' },
  { where: 'IndiaAI Mission empanelment', href: 'https://indiaai.gov.in/' },
];

const ENTERPRISE_NOW: Entry[] = [
  { where: 'Group CISO office, BFSI', why: 'sits outside IT, holds the budget', href: 'https://www.sebi.gov.in/legal/circulars' },
  { where: 'Platform and SRE', why: 'the mesh filter already in the path' },
  { where: 'DPO of a significant data fiduciary', why: 'enters via the annual assessment', href: 'https://www.meity.gov.in/data-protection-framework' },
  { where: 'AI enablement lead, GCC', why: 'one shared gateway, every team' },
];

const ENTERPRISE_NEXT: Entry[] = [
  { where: 'The group AI-use standard' },
  { where: 'RBI and SEBI audit evidence', href: 'https://www.rbi.org.in/' },
  { where: 'Vendor of record' },
  { where: 'Identifier pack per regulator', href: 'https://irdai.gov.in/' },
];

export function ICP() {
  return (
    <Section id="who" ground="card" tight>
      <SectionHead
        step="04 · Who buys it"
        title="Already running AI, already holding regulated data, one accountable owner."
        lead="Each one has a desk that can act without opening a tender. That desk is the row."
      />

      <Horizon />
      <Lane label="Public sector" now={PUBLIC_NOW} next={PUBLIC_NEXT} />
      <Lane label="Regulated enterprise" now={ENTERPRISE_NOW} next={ENTERPRISE_NEXT} last />
    </Section>
  );
}

/** The column heads, set once above both lanes so the two share one time axis. */
function Horizon() {
  return (
    <Reveal className="zt-horizon" style={{ marginBottom: 4 }}>
      <div />
      <div>
        <div className="zt-eyebrow" style={{ color: 'var(--ink)' }}>Enter now · 1–6 months</div>
        <div className="zt-hair" style={{ marginTop: 10, background: 'var(--ink)' }} />
      </div>
      <div>
        <div className="zt-eyebrow">Integrate · 2–3 years</div>
        <div
          className="zt-hair"
          style={{
            marginTop: 10, background: 'transparent',
            backgroundImage:
              'repeating-linear-gradient(to right, var(--border-strong) 0 4px, transparent 4px 8px)',
            ['--i' as string]: 2,
          }}
        />
      </div>
    </Reveal>
  );
}

function Lane({
  label,
  now,
  next,
  last,
}: {
  label: string;
  now: Entry[];
  next: Entry[];
  last?: boolean;
}) {
  return (
    <RevealGroup
      className="zt-horizon"
      style={{ paddingTop: 22, paddingBottom: last ? 0 : 22, alignItems: 'start' }}
    >
      <RevealItem>
        <h3 style={{ font: 'var(--type-h3)', margin: 0 }}>{label}</h3>
      </RevealItem>

      <div>
        <div className="zt-eyebrow zt-lane-label" style={{ color: 'var(--ink)', marginBottom: 10 }}>
          Enter now · 1–6 months
        </div>
        {now.map((e, i) => (
          <RevealItem key={e.where} index={i}>
            <Cell entry={e} />
          </RevealItem>
        ))}
      </div>

      {/* The future column recedes: quieter text, a dashed edge and no
          explanation, because none of it is being acted on this year. */}
      <div
        style={{
          paddingLeft: 20,
          backgroundImage:
            'repeating-linear-gradient(to bottom, var(--border-hairline) 0 4px, transparent 4px 8px)',
          backgroundSize: '1px 100%',
          backgroundRepeat: 'no-repeat',
        }}
      >
        <div className="zt-eyebrow zt-lane-label" style={{ marginBottom: 10 }}>
          Integrate · 2–3 years
        </div>
        {next.map((e, i) => (
          <RevealItem key={e.where} index={i}>
            <Cell entry={e} quiet />
          </RevealItem>
        ))}
      </div>
    </RevealGroup>
  );
}

function Cell({ entry, quiet }: { entry: Entry; quiet?: boolean }) {
  const name = (
    <span style={{ font: 'var(--type-label)', color: quiet ? 'var(--text-body)' : 'var(--text-strong)' }}>
      {entry.where}
    </span>
  );
  return (
    <div style={{ padding: '7px 0', display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
      {entry.href ? (
        <a
          className="zt-cite"
          href={entry.href}
          target="_blank"
          rel="noopener noreferrer"
          style={{ textDecoration: 'underline', textDecorationColor: 'var(--border-hairline)', textUnderlineOffset: 3 }}
        >
          {name}
        </a>
      ) : (
        name
      )}
      {entry.why ? <Source>{entry.why}</Source> : null}
    </div>
  );
}
