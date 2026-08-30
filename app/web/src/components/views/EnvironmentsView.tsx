'use client';

/**
 * Environments - production enforces, staging observes.
 *
 * Shadow mode is the only safe way to put a blocking control in front of traffic
 * nobody has characterised yet, and the number that decides whether to promote it
 * is "what would this have stopped". So the two environments are shown as one
 * comparison rather than two dashboards: same policy, same detectors, same
 * decisions, and the only difference is whether the decision was applied.
 *
 * The dark card is spent on the promotion question, because that is the decision
 * this screen exists to support and nothing else on it is a decision at all.
 */
import { Badge, Card, StatusDot } from '@/ds';
import { BarSeries, RatioBar } from '@/components/console/Draw';
import { Caveat, Figure, Headline, Pair, Panel, Provenance } from '@/components/console/Frame';
import { run } from '@/lib/benchmark';
import { compact, exact, percent } from '@/lib/format';

const ORDER = ['production', 'staging'] as const;

export function EnvironmentsView() {
  const envs = run.environments;
  const prod = envs.production;
  const stage = envs.staging;
  const delta = stage ? stage.intervention_rate - prod.intervention_rate : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 'var(--page-max)' }}>
      {/* Grid lives in `.zt-split` in globals.css, not inline: an inline
          grid-template-columns beats the media query and the two columns never
          collapsed on a narrow screen. */}
      <div className="zt-split">
        <div>
          {/* The two rates are the same to within a rounding place, so stating them as
              a comparison read as a mistake. What the equality means is the finding. */}
          <Headline
            sub={`Both run the same detector pack and the same policy. Staging decides every
                  payload and records the decision; it simply does not apply it. The rates
                  agreeing is what says the shadow traffic resembles the real thing - which
                  is the only condition under which promoting it is a review rather than a
                  gamble.`}
          >
            Staging and production decide alike, to within{' '}
            <Figure>{Math.abs(delta * 100).toFixed(2)}</Figure> of a percentage point.
          </Headline>
        </div>

        <Card tone="dark" pad={24}>
          <Panel title="Promotion" onDark>
            <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap', marginBottom: 22 }}>
              <Pair
                value={`${delta >= 0 ? '+' : ''}${(delta * 100).toFixed(2)} pp`}
                of="staging vs production"
                onDark
                size={33}
              />
              <Pair
                value={exact((stage?.would_block ?? 0) + (stage?.would_redact ?? 0))}
                of="payloads it would have touched"
                onDark
              />
            </div>
            <p
              style={{
                margin: 0, font: 'var(--type-body-sm)',
                color: 'var(--text-on-dark-body)', maxWidth: '50ch',
              }}
            >
              A shadow environment whose intervention rate matches production is one whose
              traffic looks like production, and promoting it changes nothing an operator
              has not already seen. A gap in either direction is the thing to explain before
              switching enforcement on.
            </p>
          </Panel>
        </Card>
      </div>

      {/* -- the two, side by side ------------------------------------------------ */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(340px,1fr))', gap: 20 }}>
        {ORDER.filter((name) => envs[name]).map((name) => {
          const env = envs[name];
          const enforcing = env.mode === 'enforce';
          return (
            <Card key={name} pad={22}>
              <div
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  gap: 12, marginBottom: 20,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                  <StatusDot state={enforcing ? 'clean' : 'info'} size={6} live={enforcing} />
                  <span className="zt-mono-sm" style={{ color: 'var(--text-body)' }}>{name}</span>
                </div>
                <Badge
                  status={enforcing ? 'clean' : 'info'}
                  tone={enforcing ? 'clean' : 'info'}
                >
                  {enforcing ? 'Enforcing' : 'Shadow'}
                </Badge>
              </div>

              <div style={{ display: 'flex', gap: 26, flexWrap: 'wrap', marginBottom: 22 }}>
                <Pair value={compact(env.records)} of="payloads" />
                <Pair
                  value={exact(env.would_block)}
                  of={enforcing ? 'blocked' : 'would be blocked'}
                />
                <Pair
                  value={exact(env.would_redact)}
                  of={enforcing ? 'redacted' : 'would be redacted'}
                />
              </div>

              <RatioBar
                total={env.records}
                segments={[
                  { label: 'Allowed', value: env.allowed, stop: 0.22 },
                  { label: enforcing ? 'Redacted' : 'Would redact', value: env.would_redact, stop: 0.52 },
                  { label: enforcing ? 'Blocked' : 'Would block', value: env.would_block, stop: 1.0 },
                ]}
              />

              {/* Both cards carry a closing sentence. Only staging had one before, and
                  the pair sat side by side with a block of dead space under production. */}
              <p
                style={{
                  margin: '20px 0 0', font: 'var(--type-body-sm)',
                  color: 'var(--text-quiet)', maxWidth: '52ch',
                }}
              >
                {enforcing
                  ? `Every decision here was applied. A blocked payload never reached the
                     model and a redacted one was verified in the dispatched bytes before it
                     was sent, so the counts above are of things that happened rather than
                     of things that were decided.`
                  : `Nothing here was stopped or rewritten. The decisions were made and
                     written to the ledger, which is the entire point of running in shadow -
                     the record says what would have happened, so promotion is a review
                     rather than a gamble.`}
              </p>
            </Card>
          );
        })}
      </div>

      {/* -- where the two differ, by action ------------------------------------- */}
      <Card pad={22}>
        <Panel
          title="Decisions by environment"
          note="The same lattice in both. Staging’s counts are decisions recorded, not actions applied."
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
            {ORDER.filter((n) => envs[n]).map((name) => (
              <div key={name}>
                <div
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                    marginBottom: 10,
                  }}
                >
                  <span className="zt-mono-sm" style={{ color: 'var(--text-body)' }}>{name}</span>
                  <span className="zt-mono-sm zt-nums" style={{ color: 'var(--text-quiet)' }}>
                    {exact(envs[name].records)} payloads
                  </span>
                </div>
                <BarSeries
                  rows={Object.entries(envs[name].actions)
                    .sort((a, b) => b[1] - a[1])
                    .map(([action, n]) => ({ label: action, value: n, mono: true }))}
                  format={compact}
                  max={envs[name].records}
                />
              </div>
            ))}
          </div>
        </Panel>
      </Card>

      <Caveat>
        Environment is a property of the payload in this run, not of a separate deployment -
        both slices went through one gateway process with one detector pack. A real staging
        environment differs in the traffic it sees, and this comparison is only as good as
        the assumption that the two populations are alike.
      </Caveat>

      <Provenance scope="Environments" />
    </div>
  );
}
