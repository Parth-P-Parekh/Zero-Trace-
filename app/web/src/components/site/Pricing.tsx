import { Section, SectionHead, Source, Pull } from './Shared';

/**
 * Move 7: pricing, and why it is shaped the way it is.
 *
 * The justification matters more than the numbers here. Government pricing
 * fails for structural reasons - per-seat produces an unpurchasable number,
 * unbounded metering cannot be sanctioned against a budget voted in advance -
 * and showing that you know why is what makes the number credible.
 */

const TIERS: Array<{ tier: string; who: string; price: string; includes: string; lead?: boolean }> = [
  {
    tier: 'Audit',
    who: 'Any department. The entry point.',
    price: '₹4L - ₹8L one-time',
    includes: 'Four weeks in shadow mode, an exposure report, the counterfactual, and a board-ready evidence pack. This is the wedge, and it is paid.',
    lead: true,
  },
  {
    tier: 'Portal',
    who: 'One citizen-facing service',
    price: '₹9L / year + 18% AMC',
    includes: 'Single deployment, enforcement, vault, ledger, 25 crore tokens a year included.',
  },
  {
    tier: 'Department',
    who: 'A full department or state IT agency',
    price: '₹35L / year + AMC',
    includes: 'Unlimited portals within the department, SSO, evidence export, the Indian identifier pack, capped metering above the band.',
  },
  {
    tier: 'Sovereign',
    who: 'State government or central ministry',
    price: '₹1.2Cr - ₹3.5Cr / year',
    includes: 'Air-gapped or in-VPC, on-prem detector bundle, dedicated support, STQC and CERT-In audit support, training.',
  },
];

const INSTINCTS: Array<[string, string, string]> = [
  ['Per seat', 'A state department has lakhs of employees. Per-seat produces a number nobody can purchase.', 'Per deployment, per portal'],
  ['Usage-based metering', 'Budgets are voted annually, in advance. Unbounded opex cannot be sanctioned.', 'Capped metering with a hard ceiling'],
  ['Monthly subscription', 'Procurement runs on annual and multi-year contracts with AMC.', 'Annual licence + 18% AMC, 3-year option'],
  ['Land and expand', 'There is no expansion budget mid-year.', 'Size correctly at contract, expand at renewal'],
  ['Card checkout', 'Payment runs 60 to 180 days through treasury.', 'Invoice, PO, GeM order'],
];

export function Pricing() {
  return (
    <>
      <Section id="pricing">
        <SectionHead
          step="06 · Pricing"
          title="Government pricing is a different sport."
          lead="Every enterprise SaaS instinct fails here, and it fails structurally rather than because the number is wrong. Showing that you know why is most of what makes a price credible to someone who has to defend it in a file."
        />

        <div style={{ display: 'flex', flexDirection: 'column', marginBottom: 56 }}>
          {INSTINCTS.map(([instinct, why, instead]) => (
            <div
              key={instinct}
              style={{
                display: 'grid', gridTemplateColumns: 'minmax(160px,200px) minmax(0,1fr) minmax(200px,260px)',
                gap: 24, padding: '18px 0', alignItems: 'baseline',
                boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
              }}
            >
              <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-faint)', textDecoration: 'line-through' }}>
                {instinct}
              </div>
              <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>{why}</p>
              <div style={{ font: 'var(--type-label)' }}>{instead}</div>
            </div>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(250px,1fr))', gap: 12 }}>
          {TIERS.map((t) => (
            <div
              key={t.tier}
              style={{
                padding: 24, borderRadius: 'var(--r-12)',
                background: t.lead ? 'var(--ink)' : 'var(--surface-card)',
                border: t.lead ? 'none' : '1px solid var(--border-hairline)',
                boxShadow: t.lead ? 'var(--sh-3)' : 'var(--sh-2)',
                display: 'flex', flexDirection: 'column',
              }}
            >
              <div
                className="zt-eyebrow"
                style={{ color: t.lead ? 'rgba(242,242,240,0.52)' : 'var(--muted)' }}
              >
                {t.tier}
              </div>
              <div
                className="zt-nums"
                style={{
                  font: 'var(--w-semibold) var(--t-21)/var(--lh-snug) var(--font-core)',
                  margin: '14px 0 4px',
                  color: t.lead ? 'var(--ink-inverse)' : 'var(--ink)',
                }}
              >
                {t.price}
              </div>
              <div
                className="zt-mono-sm"
                style={{ color: t.lead ? 'rgba(242,242,240,0.52)' : 'var(--text-faint)', marginBottom: 16 }}
              >
                {t.who}
              </div>
              <p
                style={{
                  margin: 0, font: 'var(--type-body-sm)',
                  color: t.lead ? 'var(--text-on-dark-body)' : 'var(--text-body)',
                }}
              >
                {t.includes}
              </p>
            </div>
          ))}
        </div>

        <p style={{ margin: '24px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-faint)', maxWidth: '70ch' }}>
          Enterprise, the second wedge, runs self-serve alongside this: ₹1,499 per developer per
          month rising to ₹24,999 a month plus ₹25 per additional million tokens scanned, on Razorpay
          checkout. Figures are planning assumptions, not quoted prices.
        </p>
      </Section>

      <Section ground="dark">
        <SectionHead step="06 · The justification" onDark title="What the number is actually being compared against." />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: 48 }}>
          <div>
            <Pull
              onDark
              sub="India's average data breach costs ₹25.5 crore. Shadow AI adds ₹1.79 crore on top of it. The maximum DPDP penalty is ₹250 crore for a single security failure, ₹200 crore for a notification failure, and they stack per violation category rather than per incident."
            >
              The Portal tier is ₹9 lakh a year. It pays for itself if it prevents one
              incident in 283 years.
            </Pull>
            <div style={{ marginTop: 20 }}>
              <Source onDark>IBM Cost of a Data Breach Report 2026 · DPDP Act 2023, Schedule</Source>
            </div>
          </div>

          <div>
            <div className="zt-eyebrow" style={{ color: 'rgba(242,242,240,0.52)', marginBottom: 18 }}>
              Procurement realities to build for, not around
            </div>
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
              {[
                ['L1 lowest-bid tendering', 'Win by shaping the requirement, not the price. Get compositional detection, reversibility and tamper-evident evidence written into the technical specification, so competitors are non-compliant rather than cheaper.'],
                ['EMD and performance guarantees', 'They tie up working capital. Budget for it before the first tender, not during it.'],
                ['60 to 180-day payment cycles', 'The structural reason the enterprise wedge is not optional.'],
                ['STQC and CERT-In empanelment', 'Gating for many deployments, and it takes longer than any sales cycle. Start before you need it.'],
              ].map(([head, body]) => (
                <li key={head}>
                  <p style={{ margin: '0 0 4px', font: 'var(--type-body-sm)', color: 'var(--ink-inverse)' }}>{head}</p>
                  <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)' }}>{body}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Section>
    </>
  );
}
