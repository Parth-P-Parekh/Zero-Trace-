import { Section, SectionHead, Source, Pull } from './Shared';

/**
 * Move 7: the price, and the one paragraph that justifies its shape.
 *
 * The shape is the argument. Per-seat and unbounded metering both fail against
 * a budget voted annually in advance, and showing that you know why is most of
 * what makes a number credible to the person who has to defend it.
 */

const TIERS: Array<{ tier: string; price: string; who: string; lead?: boolean }> = [
  { tier: 'Audit', price: '₹4L - ₹8L', who: 'One-time. Four weeks in shadow mode, an exposure report and the counterfactual. The wedge, and it is paid.', lead: true },
  { tier: 'Portal', price: '₹9L / year', who: 'One service. Enforcement, vault, ledger, 25 crore tokens included. Plus 18% AMC.' },
  { tier: 'Department', price: '₹35L / year', who: 'Unlimited portals, SSO, evidence export, identifier pack, capped metering above the band.' },
  { tier: 'Sovereign', price: '₹1.2 - 3.5 Cr', who: 'Air-gapped or in-VPC, on-prem detectors, dedicated support, certification support.' },
];

export function Pricing() {
  return (
    <Section id="pricing" tight>
      <SectionHead
        step="06 · Pricing"
        title="Priced per deployment, because per-seat is unpurchasable."
        lead="A department has lakhs of employees, so per-seat produces a number nobody can sanction. Budgets are voted annually in advance, so unbounded metering cannot be approved at all. Flat annual per deployment, with a hard ceiling above the included band, is the only shape that survives procurement - and it is the shape a finance officer can defend without a conversation."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(230px,1fr))', gap: 12 }}>
        {TIERS.map((t) => (
          <div
            key={t.tier}
            style={{
              padding: 22, borderRadius: 'var(--r-12)',
              background: t.lead ? 'var(--ink)' : 'var(--surface-card)',
              border: t.lead ? 'none' : '1px solid var(--border-hairline)',
              boxShadow: t.lead ? 'var(--sh-3)' : 'var(--sh-2)',
            }}
          >
            <div className="zt-eyebrow" style={{ color: t.lead ? 'rgba(242,242,240,0.52)' : 'var(--muted)' }}>
              {t.tier}
            </div>
            <div
              className="zt-nums"
              style={{
                font: 'var(--w-semibold) var(--t-21)/var(--lh-snug) var(--font-core)',
                margin: '12px 0 10px', color: t.lead ? 'var(--ink-inverse)' : 'var(--ink)',
              }}
            >
              {t.price}
            </div>
            <p
              style={{
                margin: 0, font: 'var(--type-body-sm)',
                color: t.lead ? 'var(--text-on-dark-body)' : 'var(--text-body)',
              }}
            >
              {t.who}
            </p>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 44 }}>
        <Pull sub="India's average data breach costs ₹25.5 crore, shadow AI adds ₹1.79 crore on top, and the maximum penalty for a single security failure is ₹250 crore. IBM 2026, DPDP Act 2023.">
          The Portal tier is ₹9 lakh a year. It pays for itself if it prevents one
          incident in 283 years.
        </Pull>
      </div>

      <p style={{ margin: '28px 0 0', maxWidth: '68ch' }}>
        <Source>
          Enterprise runs self-serve alongside this, from ₹1,499 per developer per month. Figures are
          planning assumptions, not quoted prices.
        </Source>
      </p>
    </Section>
  );
}
