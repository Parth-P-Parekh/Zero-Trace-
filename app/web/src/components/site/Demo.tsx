import Link from 'next/link';
import { Button } from '@/ds';
import { SHELL } from './Shared';

/**
 * Move 8: the close.
 *
 * Deliberately the emptiest section on the page. After six sections of
 * evidence, arrival should feel like air - so the only dense element is the
 * sequence the reader is being asked to book.
 */

const BEATS: Array<[string, string]> = [
  ['The install', 'One dependency added to an app. The next prompt it sends is already inspected.'],
  ['The catch', 'A transcript with a name, a PAN and a live key. The name and PAN go upstream tokenized. The key never leaves.'],
  ['The invisible leak', 'A record with no name and no ID. Every entity filter passes it. ZeroTrace names the combination that identifies the person.'],
  // The self-teaching beat used to promise "3ms, no model call" - a figure for a
  // loop this run never exercised. What replaces it is the part that was measured.
  ['The speed', 'The same prompts again, timed. A quarter of a millisecond in front of a model call that takes a thousand times longer.'],
  ['The evidence', 'Kill the process, restart, the token still resolves and the ledger verifies. Then the counterfactual.'],
];

export function Demo() {
  return (
    <section id="demo" style={{ scrollMarginTop: 64 }}>
      <div style={{ ...SHELL, paddingTop: 120, paddingBottom: 120 }}>
        <div className="zt-eyebrow" style={{ marginBottom: 24 }}>07 · The demo</div>

        <h2
          style={{
            font: 'var(--w-regular) clamp(32px, 4.6vw, 58px)/var(--lh-tight) var(--font-core)',
            letterSpacing: 'var(--tr-display)', margin: 0, maxWidth: '16ch', textWrap: 'balance',
          }}
        >
          None of this is a slide.{' '}
          <span style={{ color: 'var(--text-faint)' }}>Seven minutes, live, on real traffic.</span>
        </h2>

        <p style={{ font: 'var(--type-body)', color: 'var(--text-body)', margin: '26px 0 0', maxWidth: '52ch' }}>
          The demo runs off this page, on request, against a live gateway. You send the prompts.
          The five million test requests behind every figure on this page are generated from a
          seed, so you can regenerate them and re-run the whole thing yourself.
        </p>

        {/* One action left, so it takes the primary weight - a lone secondary
            button at the close of the page reads as an afterthought. */}
        <div style={{ display: 'flex', gap: 10, marginTop: 34, flexWrap: 'wrap' }}>
          <Link href="/login" style={{ textDecoration: 'none' }}>
            <Button size="lg" iconEnd="arrow-right">Open the console</Button>
          </Link>
        </div>

        <div
          style={{
            marginTop: 64, background: 'var(--surface-dark)', borderRadius: 'var(--r-20)',
            boxShadow: 'var(--sh-4)', padding: '34px 36px 30px',
          }}
        >
          <div className="zt-eyebrow" style={{ color: 'rgba(242,242,240,0.52)', marginBottom: 22 }}>
            What you will see
          </div>

          {BEATS.map(([title, body]) => (
            <div
              key={title}
              style={{
                display: 'grid', gridTemplateColumns: 'minmax(160px,220px) minmax(0,1fr)',
                gap: 24, padding: '14px 0', alignItems: 'baseline',
                boxShadow: 'inset 0 -1px 0 var(--border-on-dark)',
              }}
            >
              <div style={{ font: 'var(--type-label)', color: 'var(--ink-inverse)' }}>{title}</div>
              <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)' }}>
                {body}
              </p>
            </div>
          ))}

          <p style={{ margin: '24px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)', maxWidth: '56ch' }}>
            And the question every buyer asks at minute six, answered on the machine:{' '}
            <span style={{ color: 'var(--ink-inverse)' }}>what happens when your detector is
            wrong?</span>
          </p>
        </div>

      </div>
    </section>
  );
}
