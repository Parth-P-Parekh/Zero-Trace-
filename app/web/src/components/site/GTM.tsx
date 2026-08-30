import { Section, SectionHead, Stat, Pull } from './Shared';

/**
 * Move 6: how we get in, why they pick us, and where it goes.
 *
 * Seven moves became four, because three of them were sequencing detail that
 * belongs in a plan rather than on a page.
 */

const MOVES: Array<[string, string]> = [
  ['Sell the audit, not the software', 'Nobody buys an unbudgeted security product; anyone can sanction a four-week assessment. The exposure report it produces creates the budget line for the year after. This is the whole entry strategy.'],
  ['Be a component, not a procurement', 'Attach to programmes that are already funded and already sanctioned, instead of starting a new line item from zero.'],
  ['Earn the procurement path in parallel', 'GeM, STQC, CERT-In empanelment. Slow, unglamorous, and the one moat a better-funded competitor cannot buy quickly.'],
  ['Fund the long cycle with the short one', 'Regulated enterprise closes in weeks and needs the same product. It pays for the public-sector cycle that closes in quarters.'],
];

const HORIZON: Array<[string, string]> = [
  ['Year 1', 'Two paid audits, one converted to a licence, certification started, enterprise self-serve live.'],
  ['Year 2', 'Listed and partnered, so the second department is an order rather than a tender.'],
  ['Year 3', 'Compositional detection and tamper-evident evidence written into buyers’ own specifications - competitors become non-compliant rather than merely pricier.'],
  ['Years 4-5', 'The default for AI egress control here, then the same wedge in markets with the identical contradiction. The product does not change; the identifier pack and the procurement path do.'],
];

const WHY: Array<[string, string]> = [
  ['They cannot certify fast', 'Hosting can be announced in a quarter. Empanelment cannot be compressed, and it has to be finished before the tender, not during it.'],
  ['They classify spans; we score sets', 'Adding compositional risk means rebuilding the detection core. Rewrites do not happen inside a product absorbed into someone’s XDR roadmap.'],
  ['Their cost curve points the wrong way', 'Per-request model calls get more expensive as adoption grows. Ours converges toward a CPU floor.'],
  ['They govern laptops', 'The leak is server-side. That is an architectural position, not a feature gap.'],
];

export function GTM() {
  return (
    <>
      <Section id="gtm" tight>
        <SectionHead
          step="05 · Go to market"
          title="Four moves, in an order that matters."
          lead="Start certification in month one and it is ready when the first large tender lands. Start it in month twelve and you watch someone else win on paperwork."
        />

        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {MOVES.map(([title, body], i) => (
            <div
              key={title}
              style={{
                display: 'grid', gridTemplateColumns: '40px minmax(180px,260px) minmax(0,1fr)',
                gap: 24, padding: '18px 0', alignItems: 'baseline',
                boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
              }}
            >
              <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>
                {String(i + 1).padStart(2, '0')}
              </span>
              <div style={{ font: 'var(--type-label)' }}>{title}</div>
              <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>{body}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section ground="dark" tight>
        <SectionHead
          step="05 · Why us"
          onDark
          title="Why anyone picks this over a vendor with a hundred times the distribution."
          lead="Not because it is better at everything. Because four of the gaps are structural, and a buyer who needs all four has one option."
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(250px,1fr))', gap: 36 }}>
          {WHY.map(([title, body]) => (
            <div key={title}>
              <h3 style={{ font: 'var(--type-h3)', color: 'var(--ink-inverse)', margin: '0 0 10px', maxWidth: '22ch' }}>
                {title}
              </h3>
              <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)', maxWidth: '40ch' }}>
                {body}
              </p>
            </div>
          ))}
        </div>
      </Section>

      <Section ground="card" tight>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: 32, marginBottom: 44 }}>
          <Stat value="$7.69B" body="AI prompt security by 2030, growing 31.1% a year." source="Research and Markets, 2026" />
          <Stat value="11 weeks" body="Until DPDP enforcement powers begin. Full compliance follows in May 2027." source="DPDP Rules 2025" />
          <Stat value="₹250 cr" body="Maximum penalty for one security failure, and penalties stack per category." source="DPDP Act 2023, Schedule" />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {HORIZON.map(([when, what]) => (
            <div
              key={when}
              style={{
                display: 'grid', gridTemplateColumns: '110px minmax(0,1fr)', gap: 24,
                padding: '16px 0', alignItems: 'baseline',
                boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
              }}
            >
              <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>{when}</span>
              <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>{what}</p>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 40 }}>
          <Pull sub="Every figure here carries its source. Modelled numbers are labelled modelled, competitor performance figures are labelled as their claims. For a security product sold into procurement, that is not modesty - it is the shortest path to being believed.">
            The honest version of this pitch is also the most persuasive one.
          </Pull>
        </div>
      </Section>
    </>
  );
}
