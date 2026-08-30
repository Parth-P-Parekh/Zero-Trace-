import Link from 'next/link';
import { Button, Card, Icon, Tag, Wordmark } from '@/ds';
import { BreachHero } from '@/components/BreachHero';

export const metadata = {
  title: 'ZeroTrace - an egress firewall for AI traffic',
  description:
    'Deployed in the egress path, inside your perimeter. Redacts secrets and personal data out of outbound and inbound model payloads, one way, and logs every decision.',
};

const SHELL = { maxWidth: 1120, margin: '0 auto', padding: '0 32px' } as const;

export default function SitePage() {
  return (
    <>
      <SiteNav />

      <main>
        {/* Hero. The payload is the thesis - the most characteristic thing the
            product does, shown doing it, rather than described. */}
        <section style={{ ...SHELL, paddingTop: 72, paddingBottom: 88 }}>
          <h1
            style={{
              font: 'var(--w-regular) clamp(32px, 4.4vw, 58px)/var(--lh-tight) var(--font-core)',
              letterSpacing: 'var(--tr-display)', margin: 0, maxWidth: '21ch', textWrap: 'balance',
            }}
          >
            Nothing leaves that policy didn&rsquo;t allow.{' '}
            <span style={{ color: 'var(--text-faint)' }}>
              And no application had to be changed to make that true.
            </span>
          </h1>

          <p
            style={{
              font: 'var(--type-body)', color: 'var(--text-body)', margin: '28px 0 0',
              maxWidth: '58ch',
            }}
          >
            ZeroTrace is an egress firewall for AI traffic. It runs inside your perimeter, in the
            path every application already takes to reach a model. When a payload carries something
            policy forbids, the request stops there - the provider never receives it, and the caller
            is told exactly what was found.
          </p>

          <div style={{ display: 'flex', gap: 10, marginTop: 32, flexWrap: 'wrap' }}>
            <Link href="/login?next=%2Ftraffic" style={{ textDecoration: 'none' }}>
              <Button icon="scan-line">Open the console</Button>
            </Link>
            <Button variant="secondary" iconEnd="arrow-right">Read the architecture</Button>
          </div>

          <div style={{ marginTop: 48 }}>
            <BreachHero />
          </div>
        </section>

        {/* The mechanism, in the order it happens. The sequence is real, so the
            path is drawn as a path rather than as three equal cards. */}
        <section style={{ background: 'var(--surface-card)', boxShadow: 'inset 0 1px 0 var(--border-hairline), inset 0 -1px 0 var(--border-hairline)' }}>
          <div style={{ ...SHELL, paddingTop: 96, paddingBottom: 96 }}>
            <h2 style={{ font: 'var(--type-h1)', letterSpacing: 'var(--tr-display)', margin: 0, maxWidth: '20ch' }}>
              Where it sits is the product.
            </h2>
            <p style={{ font: 'var(--type-body)', color: 'var(--text-body)', margin: '20px 0 56px', maxWidth: '62ch' }}>
              A control that has to be integrated team by team has already lost the argument:
              coverage equals the set of teams that remembered. ZeroTrace is deployed once, by
              platform or security, into the path itself.
            </p>

            <Path />

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 12, marginTop: 56 }}>
              <Mode
                title="Mesh sidecar"
                body="An Envoy filter on the workload's egress listener. No application change, no CA rollout, no credential handed to anyone. Policy attaches to the identity the mesh already asserts."
                note="Default where a mesh exists"
              />
              <Mode
                title="Transparent gateway"
                body="Provider domains route to the gateway; TLS terminates under your own CA, which managed hosts already trust. Applications resolve and connect exactly as they did yesterday."
                note="Default where a mesh does not"
              />
              <Mode
                title="Explicit endpoint"
                body="The gateway speaks the provider APIs natively, so a team that would rather integrate directly can point a client at it. Nothing in the posture depends on anyone choosing this."
                note="Convenience, not the deployment model"
              />
            </div>
          </div>
        </section>

        {/* The three mechanisms. Prose, not a feature grid - each one is an
            argument that takes a paragraph to make honestly. */}
        <section style={{ ...SHELL, paddingTop: 96, paddingBottom: 96 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 48 }}>
            <Pillar
              title="It writes its own detectors"
              body="The expensive model is a teacher, not the runtime. When it catches something the deterministic rules missed, a detector is written, validated against the full corpus, and promoted to the hot path. Escalation rate, latency and cost all fall as traffic grows - the inverse of every model-in-the-loop guardrail."
              proof="Escalation fell from 11.4% to 3.8% across three runs on a fixed corpus."
            />
            <Pillar
              title="It scores the combination, not the entity"
              body="A record with no name, no email and no identifier can still identify one person. Risk is computed over the whole set of quasi-identifiers present - pincode alone is safe, pincode with a date of birth and an employer is a person. Entity filters pass these records unflagged."
              proof="Pincode, DOB, gender and employer scored 0.78 with no entity match."
            />
            <Pillar
              title="Redaction is one way"
              body="Tokens are format-preserving and referentially stable, so the same value yields the same token across every hop, session and restart, and the model reasons correctly. They are derived by keyed HMAC and never reversed. There is no plaintext stored and no restoration path to attack."
              proof="No table in the system holds a recoverable original."
            />
          </div>
        </section>

        {/* Non-goals. Unusual on a marketing page, and the most credible thing a
            security product can publish. */}
        <section style={{ background: 'var(--surface-dark)' }}>
          <div style={{ ...SHELL, paddingTop: 96, paddingBottom: 96 }}>
            <h2
              style={{
                font: 'var(--type-h1)', letterSpacing: 'var(--tr-display)', margin: 0,
                color: 'var(--ink-inverse)', maxWidth: '20ch',
              }}
            >
              What it is not.
            </h2>
            <ul
              style={{
                listStyle: 'none', margin: '40px 0 0', padding: 0,
                display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: 24,
              }}
            >
              {[
                ['Not a prompt-injection defence.', 'That market is consolidated. ZeroTrace is about what leaves, not what attacks.'],
                ['Not endpoint or browser DLP.', 'It sits at the API boundary, where server-to-server agent traffic actually is.'],
                ['Not an identity provider.', 'It enforces the clearance your directory asserts. It does not manage who anyone is.'],
                ['Not a reversible vault.', 'If a workflow needs the original back, that workflow belongs on the trusted side of the gateway.'],
                ['Not multi-tenant SaaS.', 'Payloads never reach our infrastructure. What reaches us is a signed usage count.'],
                ['Not a compliance certification.', 'It generates evidence. Auditors and counsel interpret it.'],
              ].map(([head, body]) => (
                <li key={head}>
                  <p style={{ margin: 0, font: 'var(--type-h3)', color: 'var(--ink-inverse)' }}>{head}</p>
                  <p style={{ margin: '8px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)' }}>{body}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section style={{ ...SHELL, paddingTop: 96, paddingBottom: 96 }}>
          <h2 style={{ font: 'var(--type-h1)', letterSpacing: 'var(--tr-display)', margin: 0, maxWidth: '22ch' }}>
            Licensed by business unit.
          </h2>
          <p style={{ font: 'var(--type-body)', color: 'var(--text-body)', margin: '20px 0 40px', maxWidth: '60ch' }}>
            Metered on tokens scanned, both legs. The meter is a signed counter your own deployment
            emits - counts and hashes only, readable before it is sent.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 12 }}>
            <Plan name="Proof of value" price="₹0" period="30 days" body="Self-hosted, shadow mode, one business unit. Full coverage report and counterfactual on your own traffic." />
            <Plan name="Platform" price="₹6L" period="per business unit / year" body="Enforcement on both legs, vault, synthesis loop, SSO and SCIM, coverage monitor, one-year ledger." />
            <Plan name="Enterprise" price="₹25L–₹1.2Cr" period="per year" body="Org-wide, unlimited business units, policy inheritance, HA, evidence export, support SLA." highlight />
            <Plan name="Sovereign" price="From ₹1.2Cr" period="per year" body="Air-gapped install, customer-managed keys, zero telemetry, source escrow." />
          </div>

          <p style={{ font: 'var(--type-body-sm)', color: 'var(--text-faint)', margin: '24px 0 0', maxWidth: '60ch' }}>
            Figures are planning assumptions, not quoted prices.
          </p>
        </section>
      </main>

      <SiteFooter />
    </>
  );
}

function SiteNav() {
  return (
    <header
      style={{
        position: 'sticky', top: 0, zIndex: 30, background: 'rgba(232,232,230,0.82)',
        backdropFilter: 'var(--blur-panel)', boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
      }}
    >
      <nav style={{ ...SHELL, height: 64, display: 'flex', alignItems: 'center', gap: 24 }}>
        <Link href="/" aria-label="ZeroTrace" style={{ textDecoration: 'none', display: 'inline-flex' }}>
          <Wordmark size={16} />
        </Link>
        <span style={{ flex: 1 }} />
        {/* No direct console link. The console is reachable only through sign-in. */}
        <Link href="/login" style={{ textDecoration: 'none' }}>
          <Button size="sm" variant="secondary" pill>Sign in</Button>
        </Link>
      </nav>
    </header>
  );
}

function Path() {
  const steps = [
    { label: 'Your application', note: 'unmodified' },
    { label: 'ZeroTrace', note: 'S0–S5 outbound' },
    { label: 'The model', note: 'only what policy allowed' },
    { label: 'ZeroTrace', note: 'S6 inbound' },
    { label: 'Your user', note: 'cleared to read it' },
  ];

  return (
    <ol
      style={{
        listStyle: 'none', margin: 0, padding: 0, display: 'flex', alignItems: 'stretch',
        gap: 0, flexWrap: 'wrap',
      }}
    >
      {steps.map((s, i) => (
        <li key={s.label + i} style={{ display: 'flex', alignItems: 'center', gap: 0, flex: '1 1 auto', minWidth: 150 }}>
          <div
            style={{
              flex: 1, padding: '16px 18px', borderRadius: 'var(--r-12)',
              background: i === 1 || i === 3 ? 'var(--ink)' : 'transparent',
              border: i === 1 || i === 3 ? 'none' : '1px solid var(--border-line)',
              color: i === 1 || i === 3 ? 'var(--ink-inverse)' : 'var(--text-strong)',
            }}
          >
            <div style={{ font: 'var(--type-label)' }}>{s.label}</div>
            <div
              className="zt-mono-sm"
              style={{ marginTop: 4, color: i === 1 || i === 3 ? 'rgba(242,242,240,0.52)' : 'var(--text-faint)' }}
            >
              {s.note}
            </div>
          </div>
          {i < steps.length - 1 ? (
            <span style={{ color: 'var(--text-faint)', padding: '0 10px', flex: '0 0 auto' }} aria-hidden>
              <Icon name="arrow-right" size={14} />
            </span>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

function Mode({ title, body, note }: { title: string; body: string; note: string }) {
  return (
    <Card pad={24}>
      <h3 style={{ font: 'var(--type-h3)', margin: 0 }}>{title}</h3>
      <p style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)', margin: '10px 0 14px' }}>{body}</p>
      <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>{note}</span>
    </Card>
  );
}

function Pillar({ title, body, proof }: { title: string; body: string; proof: string }) {
  return (
    <div>
      <h3 style={{ font: 'var(--type-h2)', letterSpacing: 'var(--tr-heading)', margin: 0, maxWidth: '16ch' }}>
        {title}
      </h3>
      <p style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)', margin: '16px 0 16px', maxWidth: '46ch' }}>
        {body}
      </p>
      <p
        className="zt-mono-sm"
        style={{ margin: 0, color: 'var(--text-quiet)', paddingTop: 14, boxShadow: 'inset 0 1px 0 var(--border-hairline)', maxWidth: '46ch' }}
      >
        {proof}
      </p>
    </div>
  );
}

function Plan({
  name, price, period, body, highlight,
}: {
  name: string; price: string; period: string; body: string; highlight?: boolean;
}) {
  return (
    <Card tone={highlight ? 'dark' : 'paper'} pad={24}>
      <div className="zt-eyebrow" style={{ color: highlight ? 'rgba(242,242,240,0.52)' : 'var(--muted)' }}>{name}</div>
      <div
        className="zt-nums"
        style={{
          font: 'var(--w-semibold) var(--t-26)/1.2 var(--font-core)', marginTop: 12,
          color: highlight ? 'var(--ink-inverse)' : 'var(--ink)',
        }}
      >
        {price}
      </div>
      <div className="zt-mono-sm" style={{ color: highlight ? 'rgba(242,242,240,0.52)' : 'var(--text-faint)', marginTop: 4 }}>
        {period}
      </div>
      <p
        style={{
          font: 'var(--type-body-sm)', margin: '16px 0 0',
          color: highlight ? 'var(--text-on-dark-body)' : 'var(--text-body)',
        }}
      >
        {body}
      </p>
    </Card>
  );
}

function SiteFooter() {
  return (
    <footer style={{ boxShadow: 'inset 0 1px 0 var(--border-hairline)' }}>
      <div
        style={{
          ...SHELL, paddingTop: 40, paddingBottom: 56, display: 'flex',
          alignItems: 'flex-start', justifyContent: 'space-between', gap: 32, flexWrap: 'wrap',
        }}
      >
        <div>
          <Wordmark size={15} descriptor="egress firewall for AI traffic" />
        </div>
        <div style={{ display: 'flex', gap: 48, flexWrap: 'wrap' }}>
          <FooterCol title="Product" links={['Console', 'Architecture', 'Coverage', 'Ledger']} />
          <FooterCol title="Deploy" links={['Mesh sidecar', 'Transparent gateway', 'Air-gapped']} />
          <FooterCol title="Company" links={['Security', 'Licence', 'Contact']} />
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: string[] }) {
  return (
    <div>
      <div className="zt-eyebrow" style={{ marginBottom: 12 }}>{title}</div>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {links.map((l) => (
          <li key={l} style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>{l}</li>
        ))}
      </ul>
    </div>
  );
}
