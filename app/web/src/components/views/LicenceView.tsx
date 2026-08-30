'use client';

/**
 * Licence - what is being metered, and what leaves the building to meter it.
 *
 * This is the screen most at risk of inventing numbers, so it is built the other
 * way round: it shows the measured volume the run produced, states the one
 * conversion it applies and why that conversion is approximate, and then says
 * plainly that tier, price and period are commercial facts no benchmark can
 * produce. An invented rupee figure here would undermine every measured number on
 * the other six screens.
 *
 * The dark card is spent on the usage counter itself - the only thing this product
 * ever transmits outside the customer's perimeter - because a buyer evaluating a
 * self-hosted security tool asks what it phones home with before they ask what it
 * costs.
 */
import { Card, Tag, Tooltip } from '@/ds';
import { BarSeries, RatioBar } from '@/components/console/Draw';
import { Caveat, Figure, Headline, Pair, Panel, Provenance } from '@/components/console/Frame';
import { run } from '@/lib/benchmark';
import { compact, exact, percent } from '@/lib/format';

/**
 * Bytes to tokens. Four bytes per token is the common English-text approximation
 * and it is wrong in both directions - code and JSON structure run denser, Indic
 * scripts run much sparser. It is labelled as an estimate everywhere it appears
 * and never used to derive a price.
 */
const BYTES_PER_TOKEN = 4;

export function LicenceView() {
  const { meta, status, outcomes, throughput } = run;
  const estimatedTokens = Math.round(meta.bytes_scanned / BYTES_PER_TOKEN);
  const leaksPrevented = status.blocked + status.redacted;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 'var(--page-max)' }}>
      {/* Grid lives in `.zt-split` in globals.css, not inline: an inline
          grid-template-columns beats the media query and the two columns never
          collapsed on a narrow screen. */}
      <div className="zt-split">
        <div>
          <Headline
            sub={`Metering counts what the gateway inspected, on both legs. Bytes are
                  measured exactly; tokens are an estimate at four bytes each, which is a
                  usable approximation for English prose and a poor one for code or Indic
                  scripts.`}
          >
            <Figure>{(meta.bytes_scanned / 1e9).toFixed(2)} GB</Figure> inspected across{' '}
            <Figure>{exact(status.total)}</Figure> payloads.
          </Headline>

          <div style={{ display: 'flex', gap: 30, flexWrap: 'wrap', marginTop: 28 }}>
            <Pair value={compact(estimatedTokens)} of="tokens, estimated" size={27} />
            <Pair value={compact(meta.spans_scanned)} of="spans scanned" size={27} />
            <Pair value={exact(leaksPrevented)} of="payloads stopped or rewritten" size={27} />
          </div>
        </div>

        {/* The dark card: the only thing that ever leaves. */}
        <Card tone="dark" pad={24}>
          <Panel
            title="What leaves the perimeter"
            onDark
            note="The usage counter, and nothing else. It carries counts and a ledger hash - no payload, no span path, no class, no actor."
          >
            <div
              style={{
                display: 'flex', flexDirection: 'column', gap: 10, padding: '16px 0 4px',
              }}
            >
              {[
                ['payloads_inspected', exact(status.total)],
                ['bytes_inspected', exact(meta.bytes_scanned)],
                ['findings_total', exact(outcomes.findings_total)],
                ['redactions_verified', exact(outcomes.redactions_verified)],
                ['ledger_head', 'sha256:…'],
                ['signature', 'ed25519:…'],
              ].map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 14 }}>
                  <span className="zt-mono-sm" style={{ color: 'rgba(242,242,240,0.36)' }}>{k}</span>
                  <span className="zt-mono-sm zt-nums" style={{ color: 'var(--text-on-dark-quiet)' }}>{v}</span>
                </div>
              ))}
            </div>
            <p
              style={{
                margin: '20px 0 0', font: 'var(--type-body-sm)',
                color: 'var(--text-on-dark-body)', maxWidth: '48ch',
              }}
            >
              Written to disk before transmission, so a counter that was sent can be
              reconciled against the record it was derived from. The ledger head lets a
              customer prove the counts came from the chain without sending the chain.
            </p>
          </Panel>
        </Card>
      </div>

      {/* An hourly volume strip stood here and has been removed for the same reason it
          was removed from Traffic: the corpus assigns timestamps uniformly, so it drew
          twenty-four identical bars and implied a daily pattern that was never measured. */}

      {/* -- what the volume was made of ------------------------------------------- */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: 20 }}>
        <Card pad={22}>
          <Panel title="Metered work per payload" note="Averages across the whole run.">
            <div style={{ display: 'flex', gap: 26, flexWrap: 'wrap' }}>
              <Pair value={String(throughput.spans_per_record)} of="spans per payload" />
              <Pair value={`${throughput.bytes_per_record} B`} of="bytes per payload" />
              <Pair value={`${throughput.mb_per_second} MB/s`} of="sustained" />
            </div>
            <div style={{ marginTop: 22 }}>
              <RatioBar
                segments={[
                  { label: 'Scanned fresh', value: outcomes.cache_misses, stop: 0.72 },
                  { label: 'Served from cache', value: outcomes.cache_hits, stop: 0.22 },
                ]}
              />
            </div>
            <p style={{ margin: '18px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '52ch' }}>
              Metering counts payloads inspected, not spans rescanned. A conversation resent
              on every turn is charged once per payload, which is why the cache changes the
              cost of running the gateway and not the bill.
            </p>
          </Panel>
        </Card>

        <Card pad={22}>
          <Panel
            title="Value metered against"
            note="What the run actually prevented, counted the same way the counter counts it."
          >
            <BarSeries
              rows={[
                { label: 'Credential payloads stopped', value: run.integrity.credential_records - run.integrity.credential_not_blocked },
                { label: 'Values redacted and verified', value: outcomes.redactions_verified },
                { label: 'Records caught by co-occurrence', value: run.byClass.find((c) => c.entityClass === 'QUASI_IDENTIFIER_SET')?.count ?? 0 },
                { label: 'Findings inside tool schemas, reported', value: outcomes.readonly_findings_skipped },
              ]}
              format={exact}
            />
          </Panel>
        </Card>
      </div>

      <Caveat>
        <strong style={{ fontWeight: 'var(--w-medium)', color: 'var(--text-body)' }}>
          Tier, price, licensed volume and billing period are not shown, because no
          benchmark can produce them.
        </strong>{' '}
        They are commercial terms that come from a contract. This screen previously showed a
        tier, a rupee figure and a seven-day usage chart, all of them invented; they have
        been removed rather than restyled. What remains is the metered volume, which is the
        half of a licence screen that can be measured.
      </Caveat>

      <Provenance scope="Metering" />
    </div>
  );
}
