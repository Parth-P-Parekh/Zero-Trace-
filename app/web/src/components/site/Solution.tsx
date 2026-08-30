import { Section, SectionHead, Source, Stat } from './Shared';
import { run } from '@/lib/benchmark';
import { exact, micros, percent } from '@/lib/format';

/**
 * Move 4: what it does, and what happened when it was tested.
 *
 * Every figure on this page now comes from `data/benchmark.json` rather than from
 * a string typed here, so the landing page and the console cannot drift apart -
 * and a number that changes on the next run changes in both places or in neither.
 *
 * The dark section used to carry two placeholders: an escalation rate falling from
 * 8-12% to under 3%, and a cost per million tokens falling with it. Both were
 * labelled as unmeasured and both remain unmeasured - they describe the
 * self-teaching loop, which this run did not exercise at all. Rather than leave two
 * empty boxes on the loudest surface on the page, the section now carries what the
 * run actually proved. The saturation argument stays in the lead, as an argument.
 */

const { integrity, outcomes, latencyAsync, meta, byStage, byClass } = run;

const composite = byClass.find((c) => c.entityClass === 'QUASI_IDENTIFIER_SET')?.count ?? 0;
const deterministic = byStage.S0 / Object.values(byStage).reduce((a, b) => a + b, 0);

/** Third field is a caveat, rendered at ramp .36 like every other attribution. */
const CLAIMS: Array<[string, string, string?]> = [
  [micros(latencyAsync.p50_us), 'Added to a request, typical - against a model call of 300 to 2,000 ms.',
    `Measured end to end over ${exact(meta.records)} requests.`],
  ['One package', 'A dependency, not an infrastructure project. No proxy tier, no gateway, no endpoint agent.'],
  ['One container', 'No GPU, no external classifier. Runs on infrastructure you already have.'],
  ['Zero telemetry', 'Fully in-country, in your VPC, or air-gapped. The product cannot be the leak.'],
];

export function Solution() {
  return (
    <>
      <Section id="solution" tight>
        <SectionHead
          step="03 · The product"
          title="Nothing sensitive leaves. Everything still works."
          lead="ZeroTrace redacts sensitive data on the way out and restores it on the way back, so the answer still lands. Credentials are the exception: a key is never tokenised, so a prompt carrying one is stopped."
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(224px,1fr))', gap: 30 }}>
          {CLAIMS.map(([value, body, note]) => (
            <div key={value}>
              <div
                className="zt-nums"
                style={{
                  font: 'var(--w-medium) var(--t-21)/var(--lh-snug) var(--font-core)',
                  letterSpacing: 'var(--tr-heading)', marginBottom: 10,
                }}
              >
                {value}
              </div>
              <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)', maxWidth: '34ch' }}>
                {body}
              </p>
              {note ? (
                <p style={{ margin: '8px 0 0' }}>
                  <Source>{note}</Source>
                </p>
              ) : null}
            </div>
          ))}
        </div>
      </Section>

      <Section ground="dark" tight>
        <SectionHead
          step="03 · The evidence"
          onDark
          title="Five million requests, with the answers known in advance."
          lead={`You cannot measure a guardrail on live traffic, because nobody knows what was in it. So we wrote the traffic: five million requests with the answer decided before the test ran. Every figure below is a count, not a projection - and ${percent(deterministic, 0)} of what it found needed no model call at all, which is why the cost does not climb with the model's price.`}
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: 36 }}>
          <Stat
            onDark
            value={percent(integrity.credential_block_rate, 1)}
            body="of requests carrying a live key were stopped before the model saw one."
            source={`Measured. ${exact(integrity.credential_records)} planted.`}
          />
          <Stat
            onDark
            value={exact(composite)}
            body="records identified where no single field in them was identifying. Entity filters pass these."
            source="Measured. The case the category has no answer for."
          />
          <Stat
            onDark
            value={String(outcomes.verify_failures)}
            body="redactions where the original was still in the payload we sent."
            source={`Measured. Every one of ${exact(outcomes.redactions_verified)} re-read before dispatch.`}
          />
        </div>

        <p style={{ margin: '44px 0 0', maxWidth: '64ch' }}>
          <Source onDark>
            It also raised a false alarm on {percent(integrity.false_positive_rate, 1)} of clean
            traffic, and missed keys typed with spaces in them. Both numbers, and what they cost,
            are on the Detection screen inside the console rather than left off this page.
          </Source>
        </p>
      </Section>
    </>
  );
}
