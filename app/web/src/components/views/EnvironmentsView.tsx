'use client';

/**
 * Environments - the live system, and the one watching quietly beside it.
 *
 * Shadow mode is the only safe way to put a blocking control in front of traffic
 * nobody has characterised yet, and the number that decides whether to switch it on
 * is "what would this have stopped". So the two are one comparison rather than two
 * dashboards: same rules, same detection, and the only difference is whether the
 * decision was acted on.
 *
 * "Intervention rate" and "shadow" both went. The first is a phrase nobody says out
 * loud; the second is a term of art meaning "watching without acting", which is
 * shorter than the term is.
 */
import { Badge, Card, StatusDot } from '@/ds';
import { BarSeries, RatioBar } from '@/components/console/Draw';
import { Caveat, Figure, Footnote, Headline, Pair, Panel, Provenance } from '@/components/console/Frame';
import { run } from '@/lib/benchmark';
import { compact, exact } from '@/lib/format';
import { instruction } from '@/lib/words';

const ORDER = ['production', 'staging'] as const;

const NAMES: Record<string, string> = { production: 'Live', staging: 'Test' };

export function EnvironmentsView() {
  const envs = run.environments;
  const prod = envs.production;
  const stage = envs.staging;
  const delta = stage ? stage.intervention_rate - prod.intervention_rate : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 'var(--page-max)' }}>
      <div className="zt-split">
        <div>
          {/* The two rates match to within a rounding place, so stating them as a
              comparison read as a mistake. What the match means is the finding. */}
          <Headline
            sub="The test system checks every request and writes down what it would have
                 done, then sends it anyway. The live system does the same and acts on it.
                 Same rules, same detection - the only difference is whether anything
                 happens."
          >
            Both systems reach the same decisions, within{' '}
            <Figure>{Math.abs(delta * 100).toFixed(2)}</Figure> of a percentage point.
          </Headline>
        </div>

        <Card tone="dark" pad={24}>
          <Panel title="Safe to switch on?" onDark>
            <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap' }}>
              <Pair
                value={`${delta >= 0 ? '+' : ''}${(delta * 100).toFixed(2)} pts`}
                of="difference between the two"
                onDark
                size={33}
              />
              <Pair
                value={exact((stage?.would_block ?? 0) + (stage?.would_redact ?? 0))}
                of="requests the test system would have touched"
                onDark
              />
            </div>
            <Footnote onDark measure="50ch">
              Yes. When the test system stops the same share of traffic as the live one,
              switching it on changes nothing anybody has not already seen. A gap in either
              direction would be the thing to explain first.
            </Footnote>
          </Panel>
        </Card>
      </div>

      {/* -- the two, side by side ------------------------------------------------ */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(340px,1fr))', gap: 20 }}>
        {ORDER.filter((name) => envs[name]).map((name) => {
          const env = envs[name];
          const acting = env.mode === 'enforce';
          return (
            <Card key={name} pad={22}>
              <div
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  gap: 12, marginBottom: 22,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                  <StatusDot state={acting ? 'clean' : 'info'} size={6} live={acting} />
                  <span style={{ font: 'var(--type-body-sm)' }}>{NAMES[name]}</span>
                </div>
                <Badge status={acting ? 'clean' : 'info'} tone={acting ? 'clean' : 'info'}>
                  {acting ? 'Acting on it' : 'Watching only'}
                </Badge>
              </div>

              <div style={{ display: 'flex', gap: 26, flexWrap: 'wrap', marginBottom: 22 }}>
                <Pair value={compact(env.records)} of="requests" />
                <Pair
                  value={exact(env.would_block)}
                  of={acting ? 'stopped' : 'would have been stopped'}
                />
                <Pair
                  value={exact(env.would_redact)}
                  of={acting ? 'cleaned up' : 'would have been cleaned up'}
                />
              </div>

              <RatioBar
                total={env.records}
                segments={[
                  { label: 'Sent as-is', value: env.allowed, stop: 0.22 },
                  { label: acting ? 'Cleaned up' : 'Would clean up', value: env.would_redact, stop: 0.52 },
                  { label: acting ? 'Stopped' : 'Would stop', value: env.would_block, stop: 1.0 },
                ]}
              />

              <p
                style={{
                  margin: '22px 0 0', font: 'var(--type-body-sm)',
                  color: 'var(--text-quiet)', maxWidth: '52ch',
                }}
              >
                {acting
                  ? `Everything here actually happened. A stopped request never reached the
                     model, and a cleaned-up one was checked before it was sent.`
                  : `Nothing here was stopped or changed. The decisions were made and
                     written down anyway, which is the whole point - switching it on later
                     becomes a review rather than a gamble.`}
              </p>
            </Card>
          );
        })}
      </div>

      {/* -- side by side, by decision ------------------------------------------- */}
      <Card pad={22}>
        <Panel
          title="What each decided"
          note="The same rules in both. The test system’s numbers are decisions written down, not actions taken."
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {ORDER.filter((n) => envs[n]).map((name) => (
              <div key={name}>
                <div
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                    marginBottom: 10,
                  }}
                >
                  <span style={{ font: 'var(--type-body-sm)' }}>{NAMES[name]}</span>
                  <span className="zt-mono-sm zt-nums" style={{ color: 'var(--text-quiet)' }}>
                    {exact(envs[name].records)} requests
                  </span>
                </div>
                <BarSeries
                  rows={Object.entries(envs[name].actions)
                    .sort((a, b) => b[1] - a[1])
                    .map(([action, n]) => ({ label: instruction(action), value: n }))}
                  format={compact}
                  max={envs[name].records}
                />
              </div>
            ))}
          </div>
        </Panel>
      </Card>

      <Caveat>
        In this test, live and test are two slices of one run rather than two separate
        deployments &ndash; so the comparison assumes both see the same kind of traffic. A
        real test environment usually does not, and that is what would make the two numbers
        diverge.
      </Caveat>

      <Provenance />
    </div>
  );
}
