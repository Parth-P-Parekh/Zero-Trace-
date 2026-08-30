import { Card } from '@/ds';
import { Caveat, Figure, Headline, Pair, Panel } from '@/components/console/Frame';
import { run } from '@/lib/benchmark';
import { compact, exact, micros, percent } from '@/lib/format';
import { howFound, howFoundLong } from '@/lib/words';

export const metadata = { title: 'How it works · ZeroTrace' };

/**
 * How the numbers were produced.
 *
 * This is the one screen allowed to be technical, and it is deliberately ordered so
 * that a reader can stop whenever they have had enough: the idea first, then the
 * test, then the definitions, then the file names. Someone who only reads the first
 * card still leaves knowing what the dashboard is measuring.
 *
 * A Read surface inside an Operate console - narrower measure, prose carrying the
 * page, nothing anyone has to scan.
 */
export default function MethodPage() {
  const { meta, latency, latencyAsync, integrity } = run;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 32, maxWidth: 820 }}>
      <Headline
        sub="Not a simulation of the product and not a model of it. The test feeds made-up
             traffic through the same code that would handle a real request, and counts
             what comes out."
      >
        We hid known secrets in{' '}
        <Figure>{exact(meta.records)}</Figure> fake requests and counted how many it caught.
      </Headline>

      {/* -- the idea, for anyone who reads only one card ------------------------ */}
      <Card pad={26}>
        <Panel title="The idea">
          <p style={{ margin: 0, font: 'var(--type-body)', color: 'var(--text-body)', maxWidth: '68ch' }}>
            You cannot measure whether a guardrail works by watching real traffic, because
            nobody knows what was in it. So the test writes the traffic itself: five million
            requests where we already know the answer &ndash; this one has an AWS key in it,
            this one has an Aadhaar number, this one has nothing at all and must stay quiet.
          </p>
          <p style={{ margin: '18px 0 0', font: 'var(--type-body)', color: 'var(--text-body)', maxWidth: '68ch' }}>
            Then every number on this dashboard is a count rather than an estimate. When a
            screen says it caught 96% of keys, that is 96% of a number we planted on purpose.
          </p>
        </Panel>
      </Card>

      {/* -- the three ways it looks --------------------------------------------- */}
      <Card pad={26}>
        <Panel
          title="Three ways of looking"
          note="Most tools only do the first. The third is the one that finds records nobody labelled."
        >
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {['S0', 'S1', 'S2'].map((stage) => (
              <div
                key={stage}
                style={{
                  display: 'grid', gridTemplateColumns: 'minmax(0,200px) minmax(0,1fr)',
                  gap: 22, padding: '16px 0',
                  boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
                }}
              >
                <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>
                  {howFound(stage)}
                </span>
                <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>
                  {howFoundLong(stage)}
                </p>
              </div>
            ))}
          </div>
        </Panel>
      </Card>

      {/* -- what the words on the other screens mean ---------------------------- */}
      <Card pad={26}>
        <Panel title="What the numbers mean">
          {[
            ['Share it found',
              'We planted a known number and counted how many came back. A value that was in the request and not in the results is a miss - no partial credit, no judgement call.'],
            ['False alarms',
              `Counted only on the ${exact(integrity.quiet_records)} requests written with nothing sensitive in them. An alert there has no possible defence, which makes it the only place a false alarm is unarguable. The rate was ${percent(integrity.false_positive_rate, 1)}.`],
            ['Ways around it',
              'The same keys retyped the way people actually paste them - with spaces, split over lines, encoded. Counted per trick rather than lumped together, because lumping hides which trick works.'],
            ['Time added',
              `Measured end to end, including the safety timer the product runs the check inside. Typically ${micros(latencyAsync.p50_us)}; the slowest one in twenty took ${micros(latencyAsync.p95_us)}.`],
          ].map(([term, def]) => (
            <div
              key={term}
              style={{
                display: 'grid', gridTemplateColumns: 'minmax(0,180px) minmax(0,1fr)',
                gap: 22, padding: '15px 0',
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
        The traffic is made up, so &ldquo;caught all of them&rdquo; means all of the shapes
        somebody thought to write down &ndash; a key format nobody anticipated would not
        show up as a miss. The mix of clean and risky requests is an assumption about what
        real AI traffic looks like, not a measurement of it. Speed was measured on one
        machine with nothing else competing for it. And none of this exercised the sign-in
        system, the audit log, or streamed replies.
      </Caveat>

      {/* -- the engineering detail, last, for the one reader who wants it -------- */}
      <Card pad={26} tone="sunken">
        <Panel
          title="For engineers"
          note="The test imports the product rather than reimplementing it. Every stage below is the one a live request goes through."
        >
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {[
              ['gateway/spans/jsonspan.py', 'Pulls every piece of text out of the request, including text hidden inside text.'],
              ['gateway/base/checker.py', 'Runs the three passes, reuses what it has seen before, and stops if it takes too long.'],
              ['gateway/detect/', 'The five scanners: shapes, obfuscated shapes, field names, context, and encoded values.'],
              ['gateway/base/policy.py', 'Turns findings into a decision, and decides what may not enforce.'],
              ['gateway/redact.py', 'Rewrites the request, then re-reads the bytes about to be sent to prove the original is gone.'],
            ].map(([file, what]) => (
              <div
                key={file}
                style={{
                  display: 'grid', gridTemplateColumns: 'minmax(0,230px) minmax(0,1fr)',
                  gap: 22, padding: '13px 0',
                  boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
                }}
              >
                <span className="zt-mono-sm" style={{ color: 'var(--text-body)' }}>{file}</span>
                <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>
                  {what}
                </p>
              </div>
            ))}
          </div>

          <p style={{ margin: '22px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '70ch' }}>
            One substitution, stated rather than buried. The scan normally runs on a worker
            thread so a watchdog can bound it; paying that hop five million times would have
            measured the thread pool, so the sweep called the scan directly and a separate
            pass of {exact(latencyAsync.records)} requests measured the full path. The two
            agree &ndash; {micros(latency.p50)} against {micros(latencyAsync.p50_us)} &ndash;
            so the dashboard quotes the full-path figure everywhere.
          </p>

          <div style={{ display: 'flex', gap: 30, flexWrap: 'wrap', marginTop: 24 }}>
            <Pair value={compact(meta.spans_scanned)} of="pieces of text scanned" />
            <Pair value={`${meta.wall_seconds.toFixed(0)} s`} of="to run" />
            <Pair value={exact(Math.round(meta.records_per_second))} of="requests a second" />
          </div>

          <p className="zt-mono-sm" style={{ margin: '24px 0 0', color: 'var(--text-faint)', lineHeight: 1.8 }}>
            python test_dashboard/benchmark.py --records {meta.records} --workers {meta.workers}
            <br />
            {meta.generated_at} · engines {meta.engines} · seed {meta.corpus_seed}
          </p>
        </Panel>
      </Card>
    </div>
  );
}
