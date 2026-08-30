'use client';

/**
 * Usage - what was measured, and what leaves the building to measure it.
 *
 * The screen most at risk of inventing numbers, so it is built the other way round:
 * the volume that was measured, the one conversion it applies and why that
 * conversion is rough, and then a plain statement that price and plan are contract
 * terms no test can produce.
 *
 * The dark card carries the outgoing counter, because someone evaluating a
 * self-hosted security tool asks what it phones home with before they ask what it
 * costs - and the answer, five numbers and a checksum, is a better argument than any
 * sentence about privacy.
 */
import { Card } from '@/ds';
import { BarSeries, RatioBar } from '@/components/console/Draw';
import { Caveat, Figure, Footnote, Headline, Pair, Panel, Provenance } from '@/components/console/Frame';
import { run } from '@/lib/benchmark';
import { compact, exact } from '@/lib/format';

/**
 * Bytes to words, roughly. Four bytes per token is the usual English approximation
 * and it is wrong in both directions - code runs denser, Indian-language text much
 * sparser. Labelled as a guess everywhere it appears and never used to derive money.
 */
const BYTES_PER_TOKEN = 4;

export function LicenceView() {
  const { meta, status, outcomes, throughput } = run;
  const tokens = Math.round(meta.bytes_scanned / BYTES_PER_TOKEN);
  const caught = status.blocked + status.redacted;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 'var(--page-max)' }}>
      <div className="zt-split">
        <div>
          <Headline
            sub="Billing counts what was inspected, in both directions. The size is measured
                 exactly; the word count is an estimate, and a rough one for anything that
                 isn’t English prose."
          >
            <Figure>{(meta.bytes_scanned / 1e9).toFixed(2)} GB</Figure> inspected across{' '}
            <Figure>{exact(status.total)}</Figure> requests.
          </Headline>

          <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap', marginTop: 30 }}>
            <Pair value={compact(tokens)} of="words, roughly" size={27} />
            <Pair value={exact(caught)} of="requests we caught something in" size={27} />
          </div>
        </div>

        {/* The only thing that ever leaves. */}
        <Card tone="dark" pad={24}>
          <Panel
            title="What leaves your network"
            onDark
            note="A usage count, and nothing else. No prompt, no answer, no names, no record of what was found."
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 11, padding: '14px 0 4px' }}>
              {[
                ['Requests inspected', exact(status.total)],
                ['Bytes inspected', exact(meta.bytes_scanned)],
                ['Things found', exact(outcomes.findings_total)],
                ['Values removed', exact(outcomes.redactions_verified)],
                ['Tamper-check code', 'a checksum'],
              ].map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 14 }}>
                  <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)' }}>{k}</span>
                  <span className="zt-mono-sm zt-nums" style={{ color: 'var(--text-on-dark-quiet)' }}>{v}</span>
                </div>
              ))}
            </div>
            <Footnote onDark measure="48ch">
              Written to disk before it is sent, so an invoice can always be checked back
              against your own records.
            </Footnote>
          </Panel>
        </Card>
      </div>

      {/* -- what the volume was made of ------------------------------------------ */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: 20 }}>
        <Card pad={22}>
          <Panel
            title="Work done per request"
            note="A conversation gets re-sent in full on every turn, so most of what arrives has already been checked once."
          >
            <div style={{ marginBottom: 22 }}>
              <RatioBar
                segments={[
                  { label: 'Checked fresh', value: outcomes.cache_misses, stop: 0.72 },
                  { label: 'Already seen, reused', value: outcomes.cache_hits, stop: 0.22 },
                ]}
              />
            </div>
            <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '52ch' }}>
              Billing counts requests, not re-checks &ndash; so this changes what the gateway
              costs to run and not what you pay. Each request carried about{' '}
              {throughput.bytes_per_record} bytes across {throughput.spans_per_record} pieces
              of text.
            </p>
          </Panel>
        </Card>

        <Card pad={22}>
          <Panel title="What you got for it" note="Counted the same way the usage counter counts.">
            <BarSeries
              rows={[
                { label: 'Requests with a key stopped', value: run.integrity.credential_records - run.integrity.credential_not_blocked },
                { label: 'Values removed and verified', value: outcomes.redactions_verified },
                { label: 'Personal records caught by context', value: run.byClass.find((c) => c.entityClass === 'QUASI_IDENTIFIER_SET')?.count ?? 0 },
                { label: 'Findings reported but left alone', value: outcomes.readonly_findings_skipped },
              ]}
              format={exact}
            />
          </Panel>
        </Card>
      </div>

      <Caveat>
        <strong style={{ fontWeight: 'var(--w-medium)', color: 'var(--text-body)' }}>
          There is no price, plan or renewal date on this screen, because no test can
          produce one.
        </strong>{' '}
        Those come from a contract. A tier, a rupee figure and a weekly usage chart used to
        sit here and all three were invented, so they have been removed rather than
        restyled. What is left is the volume, which is the half of a billing screen that can
        actually be measured.
      </Caveat>

      <Provenance />
    </div>
  );
}
