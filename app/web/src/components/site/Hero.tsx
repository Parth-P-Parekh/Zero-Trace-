import { Button } from '@/ds';
import { BreachHero } from '@/components/BreachHero';
import { SHELL } from './Shared';

/**
 * Move 1: what it is, in five words, then what it does in three lines.
 *
 * The fading continuation is the reference chrome's treatment the design system
 * names: first clause at full ink, the rest at ramp .36, fading like the mark.
 */
export function Hero() {
  return (
    <section style={{ ...SHELL, paddingTop: 84, paddingBottom: 96 }}>
      <h1
        style={{
          font: 'var(--w-regular) clamp(34px, 5vw, 64px)/var(--lh-tight) var(--font-core)',
          letterSpacing: 'var(--tr-display)', margin: 0, maxWidth: '17ch', textWrap: 'balance',
        }}
      >
        An egress firewall security agent.{' '}
        <span style={{ color: 'var(--text-faint)' }}>For everything your apps send to a model.</span>
      </h1>

      <p
        style={{
          font: 'var(--type-body)', color: 'var(--text-body)', margin: '28px 0 0', maxWidth: '54ch',
        }}
      >
        It sits between your application and the model. Sensitive data comes out of the outbound
        payload and goes back into the response, a prompt carrying a credential is stopped outright,
        and every decision lands in a tamper-evident record. It ships as a package, so there is
        nothing new to deploy or operate.
      </p>

      <div style={{ display: 'flex', gap: 10, marginTop: 32, flexWrap: 'wrap' }}>
        <a href="#demo" style={{ textDecoration: 'none' }}>
          <Button icon="scan-line">See the live demo</Button>
        </a>
        <a href="#problem" style={{ textDecoration: 'none' }}>
          <Button variant="secondary" iconEnd="arrow-right">Why it exists</Button>
        </a>
      </div>

      <div style={{ marginTop: 52 }}>
        <BreachHero />
      </div>
    </section>
  );
}
