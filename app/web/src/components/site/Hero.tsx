import { Button } from '@/ds';
import { BreachHero } from '@/components/BreachHero';
import { SHELL } from './Shared';
import { Reveal } from './Reveal';

/**
 * Move 1: the line, and then what it means.
 *
 * The headline is the user's own, kept verbatim. The category name lives in the
 * paragraph instead, where it costs one clause rather than the whole headline -
 * a CISO knows what an egress firewall is, and the officer who has to sanction
 * it reads the first line and nothing else.
 *
 * The drain runs inside the line rather than across two sentences: the claim at
 * full ink, what it is a firewall for at ramp .36, fading the way the wordmark
 * does. It is five words, so the gesture has to happen within them. Sentence
 * case, because the system permits caps only for the wordmark and eyebrows.
 */
export function Hero() {
  return (
    <section style={{ ...SHELL, paddingTop: 84, paddingBottom: 96 }}>
      <Reveal
        as="h1"
        variant="sweep"
        style={{
          font: 'var(--w-regular) clamp(34px, 5vw, 64px)/var(--lh-tight) var(--font-core)',
          letterSpacing: 'var(--tr-display)', margin: 0, maxWidth: '17ch', textWrap: 'balance',
        }}
      >
        Simplest firewall{' '}
        <span style={{ color: 'var(--text-faint)' }}>for frontier LLMs</span>
      </Reveal>

      <Reveal
        as="p"
        delay={1}
        style={{
          font: 'var(--type-body)', color: 'var(--text-body)', margin: '28px 0 0', maxWidth: '54ch',
        }}
      >
        ZeroTrace is an egress firewall for AI traffic. It sits between your apps and the model,
        swaps names, ID numbers and card details for stand-ins on the way out, and stops any
        message carrying a live key. Every decision is written down where an auditor can check it.
      </Reveal>

      <Reveal delay={2} style={{ display: 'flex', gap: 10, marginTop: 32, flexWrap: 'wrap' }}>
        <a href="#demo" style={{ textDecoration: 'none' }}>
          <Button icon="scan-line">See the live demo</Button>
        </a>
        <a href="#problem" style={{ textDecoration: 'none' }}>
          <Button variant="secondary" iconEnd="arrow-right">Why it exists</Button>
        </a>
      </Reveal>

      <div style={{ marginTop: 52 }}>
        <BreachHero />
      </div>
    </section>
  );
}
