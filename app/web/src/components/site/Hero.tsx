import Link from 'next/link';
import { Button } from '@/ds';
import { BreachHero } from '@/components/BreachHero';
import { SHELL } from './Shared';

/**
 * Move 1: the contradiction, and the widget that resolves it.
 *
 * The headline is the thesis of the entire scroll rather than a description of
 * the product - everything after it is evidence for this one sentence. The
 * fading continuation is the reference chrome's treatment the design system
 * names: first clause at full ink, the rest at ramp .36, fading like the mark.
 */
export function Hero() {
  return (
    <section style={{ ...SHELL, paddingTop: 76, paddingBottom: 92 }}>
      <h1
        style={{
          font: 'var(--w-regular) clamp(32px, 4.4vw, 58px)/var(--lh-tight) var(--font-core)',
          letterSpacing: 'var(--tr-display)', margin: 0, maxWidth: '20ch', textWrap: 'balance',
        }}
      >
        Adopt AI, or protect citizen data.{' '}
        <span style={{ color: 'var(--text-faint)' }}>
          Governments are currently forced to choose one.
        </span>
      </h1>

      <p
        style={{
          font: 'var(--type-body)', color: 'var(--text-body)', margin: '28px 0 0', maxWidth: '58ch',
        }}
      >
        ZeroTrace removes the choice. It sits between your application and the model, takes citizen
        data out of the outbound payload, restores it in the response, and stops a prompt outright
        when it carries a credential. One line of config. Nothing sensitive leaves, and everything
        still works.
      </p>

      <div style={{ display: 'flex', gap: 10, marginTop: 32, flexWrap: 'wrap' }}>
        <a href="#demo" style={{ textDecoration: 'none' }}>
          <Button icon="scan-line">See the live demo</Button>
        </a>
        <a href="#problem" style={{ textDecoration: 'none' }}>
          <Button variant="secondary" iconEnd="arrow-right">Start with the evidence</Button>
        </a>
      </div>

      <div style={{ marginTop: 48 }}>
        <BreachHero />
      </div>
    </section>
  );
}
