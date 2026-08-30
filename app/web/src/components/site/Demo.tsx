import Link from 'next/link';
import { Button } from '@/ds';
import { SHELL, Source } from './Shared';

/**
 * Move 8: the close.
 *
 * The demo is given live and off this page, so this section's job is
 * anticipation, not embedding. It is deliberately the emptiest section on the
 * scroll: after six sections of dense evidence, arrival should feel like air.
 * The one dark element is the sequence itself, because that is the thing the
 * reader is being asked to book.
 */

const BEATS: Array<[string, string, string]> = [
  ['0:00', 'The one-line change', 'An application nobody modified. Its config has no ZeroTrace URL, no key, no SDK - and its traffic is already being inspected.'],
  ['0:40', 'The catch', 'A support transcript carrying a citizen name, a PAN and a live API key. Response headers show the findings and the latency. The upstream payload is displayed: tokenized, and the credential never leaves.'],
  ['1:30', 'The round trip', 'The same citizen across three hops resolves to the same token every time, so the model reasons correctly - and the answer comes back re-hydrated. Coherent, not mangled.'],
  ['2:20', 'The invisible leak', 'A record with no name, no Aadhaar, no phone. Every entity filter passes it. ZeroTrace scores composite re-identification risk at 0.78 and says which combination identifies the person.'],
  ['3:20', 'The system teaches itself', 'A leak class absent from the rule pack. The adjudicator catches it, a detector is written and validated against the corpus, and it is promoted. Send the same class again: caught in 3ms with no model call.'],
  ['5:20', 'The evidence', 'Kill the process. Restart. The token still resolves. The ledger chain verifies unbroken. Then the counterfactual: what would have left, if this had been off.'],
];

export function Demo() {
  return (
    <section id="demo" style={{ scrollMarginTop: 64 }}>
      <div style={{ ...SHELL, paddingTop: 128, paddingBottom: 128 }}>
        <div className="zt-eyebrow" style={{ marginBottom: 24 }}>07 · The demo</div>

        <h2
          style={{
            font: 'var(--w-regular) clamp(32px, 4.6vw, 58px)/var(--lh-tight) var(--font-core)',
            letterSpacing: 'var(--tr-display)', margin: 0, maxWidth: '17ch', textWrap: 'balance',
          }}
        >
          None of this is a slide.{' '}
          <span style={{ color: 'var(--text-faint)' }}>Seven minutes, live, on real traffic.</span>
        </h2>

        <p
          style={{
            font: 'var(--type-body)', color: 'var(--text-body)', margin: '28px 0 0', maxWidth: '56ch',
          }}
        >
          The demo runs off this page, on request, against a live gateway - not a recording and not a
          mock. You send the prompts. Every number quoted on this page is reproducible in the room,
          including the ones we would rather round up.
        </p>

        <div style={{ display: 'flex', gap: 10, marginTop: 36, flexWrap: 'wrap' }}>
          <Button size="lg" icon="scan-line">Book the live demo</Button>
          <Link href="/login" style={{ textDecoration: 'none' }}>
            <Button size="lg" variant="secondary" iconEnd="arrow-right">Open the console</Button>
          </Link>
        </div>

        <div
          style={{
            marginTop: 72, background: 'var(--surface-dark)', borderRadius: 'var(--r-20)',
            boxShadow: 'var(--sh-4)', padding: '40px 40px 34px',
          }}
        >
          <div className="zt-eyebrow" style={{ color: 'rgba(242,242,240,0.52)', marginBottom: 28 }}>
            What you will see, in order
          </div>

          {BEATS.map(([time, title, body]) => (
            <div
              key={time}
              style={{
                display: 'grid', gridTemplateColumns: '68px minmax(180px,240px) minmax(0,1fr)',
                gap: 24, padding: '18px 0', alignItems: 'baseline',
                boxShadow: 'inset 0 -1px 0 var(--border-on-dark)',
              }}
            >
              <span className="zt-mono-sm" style={{ color: 'rgba(242,242,240,0.36)' }}>{time}</span>
              <div style={{ font: 'var(--type-label)', color: 'var(--ink-inverse)' }}>{title}</div>
              <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)' }}>
                {body}
              </p>
            </div>
          ))}

          <p
            style={{
              margin: '28px 0 0', font: 'var(--type-body-sm)',
              color: 'var(--text-on-dark-body)', maxWidth: '62ch',
            }}
          >
            And the question every security buyer asks at minute six, answered on the machine rather
            than in a deck: <span style={{ color: 'var(--ink-inverse)' }}>what happens when your
            detector is wrong?</span> One click, a scoped exception drafted, an approver who is not
            the person who raised it, and the whole exchange in the ledger.
          </p>
        </div>

        <p style={{ margin: '32px 0 0', maxWidth: '72ch' }}>
          <Source>
            Every figure on this page carries its source inline. Modelled figures are labelled as
            modelled, competitor performance numbers as their own published claims, and the
            815-million-record health exposure as claimed rather than confirmed. Sources are
            re-verified quarterly, because a stale number on a security site is worse than no number.
          </Source>
        </p>
      </div>
    </section>
  );
}
