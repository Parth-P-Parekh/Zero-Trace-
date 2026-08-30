import { Section, SectionHead, Source } from './Shared';
import { Reveal, RevealGroup, RevealItem } from './Reveal';

/**
 * Move 8: the price, shaped around who is allowed to sign it.
 *
 * The old ladder opened at ₹4-8 lakh for a four-week assessment. That number is
 * defensible and it is also unsellable, because it sits above the line where a
 * department can act on its own: a purchase committee stops at ₹5,00,000 and
 * anything past it becomes a tender. A tender is a nine-to-eighteen-month cycle
 * run by people who have never heard of us, against a company with no
 * certification yet and no reference customer. That is not a long sale. It is a
 * sale that does not start.
 *
 * So the entry is zero and the ladder is built out of other people's signing
 * authority. The first paid step clears under GFR Rule 154, which one officer
 * signs without a quotation. The second clears under Rule 155, which a purchase
 * committee signs without a tender. Nothing on this page needs a procurement to
 * happen, and nothing needs us to be credible yet - the shadow run is what
 * makes us credible, and it is free because a free thing needs no sanction at
 * all.
 *
 * The threshold scale above the ladder is the whole strategy in one graphic, and
 * the four notes under it answer the other half of the friction: what happens
 * after the signature. Sovereign and air-gapped pricing is deliberately absent -
 * it does not exist until empanelment does, and a number with no certificate
 * behind it is the thing this whole ladder was built to avoid quoting.
 */

interface Rung {
  name: string;
  price: string;
  unit?: string;
  what: string;
  signer: string;
  rule?: string;
  href?: string;
  lead?: boolean;
}

const RUNGS: Rung[] = [
  {
    name: 'Shadow',
    price: '₹0',
    unit: '30 days',
    what: 'Runs beside your traffic inside your own VPC, deciding nothing. You get the exposure report and the counterfactual: what left, what a per-entity classifier would have missed, and what a log could not have proved.',
    signer: 'Nobody has to sign a purchase.',
    rule: 'An MoU, not a purchase order.',
    lead: true,
  },
  {
    name: 'One service',
    price: '₹49,000',
    unit: 'per year',
    what: 'Enforcement on a single portal or service. Detection pack, one-way tokens, the ledger, and evidence export.',
    signer: 'One officer, no quotation.',
    rule: 'GFR 2017, Rule 154',
    href: 'https://doe.gov.in/general-financial-rules',
  },
  {
    name: 'One department',
    price: '₹4.2 L',
    unit: 'per year',
    what: 'Every service the department runs. SSO, per-unit policy, the identifier pack, and the audit export the annual assessment asks for.',
    signer: 'A purchase committee, no tender.',
    rule: 'GFR 2017, Rule 155',
    href: 'https://doe.gov.in/general-financial-rules',
  },
  {
    name: 'Enterprise',
    price: '₹9 L',
    unit: 'per year',
    what: 'The same product for a capability centre or regulated enterprise, sold against an open control gap the annual audit already names.',
    signer: 'A security budget that already exists.',
    rule: 'Closes in weeks. It funds the public cycle.',
  },
];

/** The scale the ladder is built against. Three zones we live in, one we avoid. */
const ZONES: Array<{ cap: string; who: string; ours: boolean }> = [
  { cap: '₹0', who: 'no sanction needed', ours: true },
  { cap: '₹50,000', who: 'one officer signs', ours: true },
  { cap: '₹5,00,000', who: 'a committee signs', ours: true },
  { cap: 'above', who: 'open tender · 9–18 months', ours: false },
];

export function Pricing() {
  return (
    <Section id="pricing" tight>
      <SectionHead
        step="07 · Pricing"
        title="Start at zero, and stay under the line where a tender begins."
        lead="A department can act on its own up to ₹5,00,000. Above that it is a nine-to-eighteen-month procurement run against a company with no certification yet. So the ladder is built out of authority that already exists."
      />

      {/* The scale. Every rung below is placed against it, and the fourth zone
          is drawn only to show what the pricing is deliberately staying under. */}
      <Reveal className="zt-scale" style={{ marginBottom: 44 }}>
        {ZONES.map((z, i) => (
          <div
            key={z.cap}
            style={{
              paddingTop: 12,
              opacity: z.ours ? 1 : 0.52,
            }}
          >
            <div
              className="zt-hair"
              style={{
                marginBottom: 12,
                ['--i' as string]: i,
                background: z.ours ? 'var(--ink)' : 'transparent',
                backgroundImage: z.ours
                  ? undefined
                  : 'repeating-linear-gradient(to right, var(--border-strong) 0 4px, transparent 4px 8px)',
              }}
            />
            <div
              className="zt-nums"
              style={{
                font: 'var(--w-medium) var(--t-16)/var(--lh-snug) var(--font-core)',
                color: z.ours ? 'var(--text-strong)' : 'var(--text-quiet)',
              }}
            >
              {z.cap}
            </div>
            <div style={{ marginTop: 4 }}>
              <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>{z.who}</span>
            </div>
          </div>
        ))}
      </Reveal>

      <RevealGroup>
        {RUNGS.map((r, i) => (
          <RevealItem key={r.name} index={i} className="zt-lift">
            <div className="zt-rung">
              <div>
                <div className="zt-eyebrow" style={{ marginBottom: 10 }}>{r.name}</div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                  <span
                    className="zt-nums"
                    style={{
                      font: `var(--w-semibold) ${r.lead ? 'clamp(30px, 3.4vw, 42px)' : 'clamp(26px, 2.8vw, 33px)'}/var(--lh-tight) var(--font-core)`,
                      letterSpacing: 'var(--tr-display)',
                    }}
                  >
                    {r.price}
                  </span>
                  {r.unit ? (
                    <span className="zt-mono-sm" style={{ color: 'var(--text-quiet)' }}>{r.unit}</span>
                  ) : null}
                </div>
              </div>

              <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)', maxWidth: '52ch' }}>
                {r.what}
              </p>

              <div className="zt-rung-signer">
                <div style={{ font: 'var(--type-label)', marginBottom: 5 }}>{r.signer}</div>
                {r.rule ? <Source href={r.href}>{r.rule}</Source> : null}
              </div>
            </div>
            <div className="zt-hair" style={{ ['--i' as string]: i }} />
          </RevealItem>
        ))}
      </RevealGroup>

      {/* Price is only half the friction. The other half is what happens after
          the signature, and the answer to that is what makes the first one easy. */}
      <RevealGroup
        style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(230px,1fr))',
          gap: 30, marginTop: 52,
        }}
      >
        {([
          ['Nothing to integrate', 'One container in your VPC and one line on the proxy your traffic already crosses. No application team is asked for anything.'],
          ['Nothing to migrate', 'It reads traffic in the path it is already in. There is no data to move and no schema to agree on.'],
          ['Nothing to unwind', 'Removing it is the same one line, reversed. The ledger stays readable without us.'],
          ['Nothing leaves', 'Payloads never reach us. A signed usage counter does, and that is the entire outbound surface.'],
        ] as Array<[string, string]>).map(([t, b], i) => (
          <RevealItem key={t} index={i}>
            <h3 style={{ font: 'var(--type-h3)', margin: '0 0 8px' }}>{t}</h3>
            <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '34ch' }}>
              {b}
            </p>
          </RevealItem>
        ))}
      </RevealGroup>
    </Section>
  );
}
