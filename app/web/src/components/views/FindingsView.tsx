'use client';

/**
 * Findings - what is actually in the traffic.
 *
 * Traffic counts payloads; this counts the things inside them. The two are
 * different questions and were sharing a screen, which is why neither was
 * answerable: a request is blocked once, but it can carry six findings across
 * four span paths and three stages, and the second fact is the one that tells a
 * security team what their organisation is doing.
 *
 * The dark card is spent on the advisory split. A third of all findings cannot
 * enforce on their own, and a console that showed 3.6M findings without saying
 * so would be overstating the product by 41% on its own front page.
 */
import { useState } from 'react';
import { Card, SegmentedControl, Tag, Tooltip } from '@/ds';
import { BarSeries, RatioBar } from '@/components/console/Draw';
import { Caveat, Figure, Headline, Pair, Panel, Provenance } from '@/components/console/Frame';
import { enforceableFindings, formatDegradedTotal, run } from '@/lib/benchmark';
import { classToken, compact, exact, percent } from '@/lib/format';

const ORIGIN_COPY: Record<string, string> = {
  user: 'What the user typed or pasted',
  system: 'Developer instructions',
  tool_definition: 'Tool and skill schemas',
  tool_result: 'Data a tool returned',
  assistant: 'The model’s own turns',
  metadata: 'Model ids and protocol fields',
};

const FAMILY_COPY: Record<string, string> = {
  CREDENTIAL: 'Credentials',
  INDIA_ID: 'India identifiers',
  COMPOSITE: 'Records identified by their fields',
  LOW_CONFIDENCE: 'Advisory signals',
  CONTACT: 'Contact details',
  FINANCIAL: 'Financial',
  PERSON_DATA: 'Person data',
  SENSITIVE_CATEGORY: 'Sensitive categories',
};

export function FindingsView() {
  const [dim, setDim] = useState('class');
  const { outcomes, byClass, byFamily, byOrigin, byConfidence, bySpanPath } = run;
  const enforceable = enforceableFindings();
  const degradedFormats = formatDegradedTotal();

  const series =
    dim === 'class'
      ? byClass.map((c) => ({ label: classToken(c.entityClass), value: c.count, mono: true }))
      : dim === 'family'
        ? byFamily.map((f) => ({ label: FAMILY_COPY[f.family] ?? f.family, value: f.count, note: f.family.toLowerCase() }))
        : dim === 'origin'
          ? Object.entries(byOrigin).map(([o, n]) => ({ label: ORIGIN_COPY[o] ?? o, value: n, note: o }))
          : Object.entries(bySpanPath).map(([p, n]) => ({ label: p, value: n, mono: true }));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 'var(--page-max)' }}>
      {/* Grid lives in `.zt-split` in globals.css, not inline: an inline
          grid-template-columns beats the media query and the two columns never
          collapsed on a narrow screen. */}
      <div className="zt-split">
        <div>
          <Headline
            sub={`A payload is blocked once but can carry several findings, so this is a
                  larger number than the traffic count and a different question. Advisory
                  classes are separated because they may never drive an action alone.`}
          >
            <Figure>{exact(outcomes.findings_total)}</Figure> findings, of which{' '}
            <Figure>{exact(enforceable)}</Figure> could act.
          </Headline>

          <div style={{ marginTop: 26 }}>
            <RatioBar
              segments={[
                { label: 'Enforceable', value: enforceable, stop: 1.0 },
                { label: 'Advisory only', value: outcomes.advisory_findings, stop: 0.22 },
              ]}
            />
          </div>
        </div>

        <Card tone="dark" pad={24}>
          <Panel
            title="Advisory findings"
            onDark
            note="High-entropy strings: git SHAs, lockfile digests, base64 blobs. Reported and counted, never a reason to touch a request."
          >
            <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap' }}>
              <Pair
                value={percent(outcomes.advisory_findings / outcomes.findings_total, 1)}
                of="of all findings"
                onDark
                size={33}
              />
              <Pair value={compact(outcomes.advisory_findings)} of="raised" onDark />
              <Pair value="0" of="drove an action" onDark />
            </div>
            <p
              style={{
                margin: '22px 0 0', font: 'var(--type-body-sm)',
                color: 'var(--text-on-dark-body)', maxWidth: '52ch',
              }}
            >
              A coding payload is full of things that look like secrets. Routing them to a
              strict default is how a guardrail gets switched off in week one, so they
              corroborate other findings and feed the escalation queue instead.
            </p>
          </Panel>
        </Card>
      </div>

      {/* -- the distribution, switchable by dimension --------------------------- */}
      <Card pad={22}>
        <Panel
          title="Distribution"
          right={
            <SegmentedControl
              size="sm"
              value={dim}
              onChange={setDim}
              items={[
                { value: 'class', label: 'Class' },
                { value: 'family', label: 'Family' },
                { value: 'origin', label: 'Origin' },
                { value: 'path', label: 'Span path' },
              ]}
            />
          }
        >
          <BarSeries rows={series} format={compact} limit={14} />
        </Panel>
      </Card>

      {/* -- confidence and the enforcement threshold ----------------------------- */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: 20 }}>
        <Card pad={22}>
          <Panel
            title="Confidence"
            note="The band from 0.35 to 0.75 escalates rather than enforces. Detectors tuned into it are meant to be uncertain."
          >
            <BarSeries
              rows={Object.entries(byConfidence)
                .sort((a, b) => Number(b[0]) - Number(a[0]))
                .map(([c, n]) => ({
                  label: c,
                  value: n,
                  note: Number(c) >= 0.75 ? 'enforces' : 'escalates',
                  mono: true,
                }))}
              format={compact}
            />
          </Panel>
        </Card>

        <Card pad={22}>
          <Panel
            title="Read-only origins"
            note="Findings inside tool schemas and developer instructions. Detected and reported; a tool schema may never drive enforcement, whatever is written in it."
          >
            <div style={{ display: 'flex', gap: 26, flexWrap: 'wrap', marginBottom: 20 }}>
              <Pair value={exact(outcomes.readonly_findings_skipped)} of="reported, not rewritten" />
              <Pair value={exact(run.integrity.tool_definition_enforced)} of="drove a block" />
            </div>
            <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '52ch' }}>
              An AWS key in a tool description is almost always a documentation sample, and
              the person who wrote the prompt cannot remove it. Blocking them for it
              punishes the wrong person, and the way that ends is with the tool disabled.
            </p>
          </Panel>
        </Card>
      </div>

      <Caveat>
        <strong style={{ fontWeight: 'var(--w-medium)', color: 'var(--text-body)' }}>
          Person names, addresses and organisations are absent from this list because
          nothing detects them yet.
        </strong>{' '}
        Those classes need the S2 entity model, which is designed and not built - so the
        run could not plant them and this screen does not imply it found them. What stands
        in for the person-record case is{' '}
        <span className="zt-mono-sm">quasi_identifier_set</span>, which reached{' '}
        {exact(run.byClass.find((c) => c.entityClass === 'QUASI_IDENTIFIER_SET')?.count ?? 0)}{' '}
        records by their field structure rather than by naming anyone.
      </Caveat>

      {/* -- what the redaction could not preserve --------------------------------- */}
      <Card pad={22}>
        <Panel
          title="Redaction shortfall"
          note="Classes whose token should pass the same validator the original passed, and currently does not."
        >
          <div style={{ display: 'flex', gap: 26, flexWrap: 'wrap', marginBottom: 18 }}>
            <Pair value={exact(degradedFormats)} of="values given a labelled token" />
            <Pair value={exact(outcomes.redactions_verified)} of="redactions proven in the dispatched bytes" />
            <Pair value={exact(outcomes.verify_failures)} of="verification failures" />
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {Object.entries(run.degradedFormats).map(([cls, n]) => (
              <Tooltip key={cls} label={`${exact(n)} values`}>
                <span><Tag mono>{classToken(cls)}</Tag></span>
              </Tooltip>
            ))}
          </div>
          <p style={{ margin: '18px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-quiet)', maxWidth: '70ch' }}>
            A downstream service validating a PAN checksum breaks when the token in its place
            is not a PAN. These {exact(degradedFormats)} values were still redacted and the
            redaction was still verified - what they did not get is a shape the far side can
            parse. The gateway says so on every affected response in{' '}
            <span className="zt-mono-sm">X-ZeroTrace-Format-Degraded</span>.
          </p>
        </Panel>
      </Card>

      <Provenance scope="Findings" />
    </div>
  );
}
