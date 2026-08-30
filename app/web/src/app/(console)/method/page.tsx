import { Card } from '@/ds';
import { Caveat, Headline, Pair, Panel, Figure } from '@/components/console/Frame';
import { BarSeries } from '@/components/console/Draw';
import { run } from '@/lib/benchmark';
import { compact, exact, micros, percent } from '@/lib/format';

export const metadata = { title: 'Method · ZeroTrace' };

/**
 * How the numbers were produced.
 *
 * A Read surface inside an Operate console: measure is narrower, prose carries the
 * page, and there is no table anyone has to scan. It exists because every other
 * screen links here from its provenance line, and a claim whose method is one
 * click away is a different kind of claim from one whose method is nowhere.
 */
export default function MethodPage() {
  const { meta, latency, latencyAsync, integrity, outcomes } = run;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 32, maxWidth: 860 }}>
      <Headline
        sub="Everything on the six screens behind this one came from a single run against the
             product's own code paths. This page says what ran, what was substituted, and
             what the result does not prove."
      >
        <Figure>{exact(meta.records)}</Figure> synthetic payloads through the real pipeline.
      </Headline>

      <Card pad={24}>
        <Panel
          title="What ran"
          note="The benchmark imports the gateway. It does not reimplement it, and every object below is the one a live request goes through."
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {[
              ['gateway/spans/jsonspan.py', 'extract_spans', 'Byte-accurate JSON leaf extraction, including $json recursion into stringified tool results.'],
              ['gateway/base/checker.py', 'Checker', 'Three-tier scan, span cache, 50 ms deadline, green/amber/red verdict.'],
              ['gateway/detect/', 'five scanners', 'S0 credentials, obfuscation rescan, S1 key-name context, S2 co-occurrence, encoded rescan.'],
              ['gateway/base/policy.py', 'StubPolicyClient', 'Family defaults, the action lattice, read-only origin rules, inbound clearance.'],
              ['gateway/redact.py', 'plan → apply → verify_dispatch', 'Redaction planned, spliced into the original bytes, then proven absent in the bytes about to leave.'],
            ].map(([file, symbol, what]) => (
              <div
                key={file}
                style={{
                  display: 'grid', gridTemplateColumns: 'minmax(0,220px) minmax(0,1fr)',
                  gap: 20, padding: '14px 0',
                  boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div className="zt-mono-sm" style={{ color: 'var(--text-body)' }}>{symbol}</div>
                  <div className="zt-mono-sm" style={{ color: 'var(--text-faint)', marginTop: 3 }}>{file}</div>
                </div>
                <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>
                  {what}
                </p>
              </div>
            ))}
          </div>
        </Panel>
      </Card>

      <Card pad={24}>
        <Panel
          title="The one substitution"
          note="Stated rather than buried, because it is the only place the benchmark and the product differ."
        >
          <p style={{ margin: '0 0 18px', font: 'var(--type-body)', color: 'var(--text-body)', maxWidth: '70ch' }}>
            <code className="zt-mono-sm">Checker.check()</code> dispatches the scan to a worker
            thread so a watchdog can bound it - CPU-bound Python cannot be interrupted from
            outside. That is a latency-safety mechanism, not a detection mechanism, and paying
            a thread hop five million times would have measured the executor. So the sweep
            called <code className="zt-mono-sm">_scan_all</code> and{' '}
            <code className="zt-mono-sm">_verdict</code> directly, and a separate pass of{' '}
            {exact(latencyAsync.records)} payloads went through the full{' '}
            <code className="zt-mono-sm">check()</code> to measure what was skipped.
          </p>
          <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
            <Pair value={micros(latency.p50)} of="p50, scan only" />
            <Pair value={micros(latencyAsync.p50_us)} of="p50, full check" />
            <Pair value={micros(latencyAsync.p95_us)} of="p95, full check" />
          </div>
          <p style={{ margin: '18px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '70ch' }}>
            The two agree, so the console quotes the full-check figures everywhere a latency
            number appears.
          </p>
        </Panel>
      </Card>

      <Card pad={24}>
        <Panel
          title="The corpus"
          note="Generated, not stored. Shard k seeds from the run seed and its own index, so any record can be regenerated from its index alone and the whole corpus is reproducible without a 3.5 GB artifact."
        >
          <BarSeries
            rows={Object.entries(run.scenarios)
              .sort((a, b) => b[1] - a[1])
              .map(([name, n]) => ({ label: name.replace(/_/g, ' '), value: n, mono: true }))}
            format={compact}
            limit={12}
          />
          <p style={{ margin: '20px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '70ch' }}>
            Thirty-eight families across five groups: ordinary work, things shaped like
            secrets that are not, real leaks, evasion variants of those leaks, and inbound
            responses. The families generated with nothing in them are larger than the
            families carrying credentials, because a false positive is what gets a security
            control switched off and needs the bigger sample.
          </p>
        </Panel>
      </Card>

      <Card pad={24}>
        <Panel title="How each score is defined">
          {[
            ['Recall', 'Planted a known number of times, then counted. A class present in the payload and absent from the findings is a miss - there is no partial credit and no judgement call.'],
            ['Precision', `Measured only on the ${exact(integrity.quiet_records)} payloads generated with no leak in them. An enforceable finding there has no defence available, which is the only place a false positive is unambiguous.`],
            ['False-positive rate', `Payloads in that same set that raised any enforceable finding, over the set. ${percent(integrity.false_positive_rate, 2)}.`],
            ['Detection under evasion', 'The same credential values, rewritten. Recall is computed per technique rather than pooled, because pooling hides which technique works.'],
            ['Runtime', 'One class per probe, scanned in isolation and averaged over 3,000 repetitions after a warm pass. Composed scanners report nothing rather than a misleading share.'],
          ].map(([term, def]) => (
            <div
              key={term}
              style={{
                display: 'grid', gridTemplateColumns: 'minmax(0,180px) minmax(0,1fr)',
                gap: 20, padding: '14px 0',
                boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
              }}
            >
              <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>{term}</span>
              <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>{def}</p>
            </div>
          ))}
        </Panel>
      </Card>

      <Caveat>
        <strong style={{ fontWeight: 'var(--w-medium)', color: 'var(--text-body)' }}>
          What this does not prove.
        </strong>{' '}
        The corpus is synthetic, so recall is recall against shapes someone chose - a
        credential format nobody thought of is not in it and would not show as a miss. The
        mix is an assumption about what enterprise AI traffic looks like, not a measurement
        of it. Throughput was measured on one machine with twenty workers and says nothing
        about behaviour under concurrent load. And no part of this run exercised the control
        plane, the ledger chain, streaming responses, or the inbound clearance path against
        a real directory.
      </Caveat>

      <p className="zt-mono-sm" style={{ margin: 0, color: 'var(--text-faint)', lineHeight: 1.8 }}>
        Reproduce: <span style={{ color: 'var(--text-quiet)' }}>python test_dashboard/benchmark.py --records {meta.records} --workers {meta.workers}</span>
        <br />
        Run {meta.generated_at} · engines {meta.engines} · seed {meta.corpus_seed} ·{' '}
        {compact(meta.bytes_scanned)} bytes · {outcomes.verify_failures} verification failures
      </p>
    </div>
  );
}
