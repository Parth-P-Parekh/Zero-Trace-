'use client';

import { useState } from 'react';
import { Badge, Button, Card, Icon, StatusDot, Tag, Tooltip } from '@/ds';
import { PageHead, SectionLabel } from '@/components/Chrome';
import { classToken } from '@/lib/format';
import { ACTION_LATTICE } from '@/lib/types';
import type { PolicyException, PolicyVersion } from '@/lib/types';

export function PolicyView({
  active,
  versions,
  exceptions,
}: {
  active: PolicyVersion;
  versions: PolicyVersion[];
  exceptions: PolicyException[];
}) {
  const [selected, setSelected] = useState(active.version);
  const shown = versions.find((v) => v.version === selected) ?? active;
  const pending = exceptions.filter((e) => !e.approvedBy);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 'var(--page-max)' }}>
      <PageHead
        title="One policy file, inherited down"
        sub="Policy is org-scoped. A business unit may narrow an action, never widen it - the resolver takes the stronger of the two and refuses a weaker override at publish time."
        right={
          <div style={{ display: 'flex', gap: 8 }}>
            <Button variant="secondary" size="sm" icon="copy">Copy YAML</Button>
            <Button size="sm" icon="check">Publish new version</Button>
          </div>
        }
      />

      <Card pad={20}>
        <SectionLabel>The action lattice</SectionLabel>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {ACTION_LATTICE.map((a, i) => (
            <span key={a} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <Tag mono>{a}</Tag>
              {i < ACTION_LATTICE.length - 1 ? (
                <span style={{ color: 'var(--text-faint)' }} aria-hidden>→</span>
              ) : null}
            </span>
          ))}
          <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)', marginLeft: 8 }}>
            weaker to stronger. An override may move right, never left.
          </span>
        </div>
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1.6fr) minmax(0,1fr)', gap: 12, alignItems: 'start' }}>
        {/* The live policy is what governs every decision on every other screen. Dark card. */}
        <Card tone="dark" pad={0}>
          <div
            style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '14px 20px',
              boxShadow: 'inset 0 -1px 0 var(--border-on-dark)',
            }}
          >
            <StatusDot state={shown.active ? 'clean' : 'idle'} size={6} live={shown.active} />
            <span style={{ font: 'var(--type-label)', color: 'var(--ink-inverse)' }}>
              policy v{shown.version}
            </span>
            <span className="zt-mono-sm" style={{ color: 'var(--text-on-dark-quiet)' }}>
              {shown.active ? 'active' : 'superseded'} · {shown.createdBy}
            </span>
            <span style={{ flex: 1 }} />
            <Tooltip label="Copy to clipboard">
              <span style={{ color: 'rgba(242,242,240,0.52)', display: 'inline-flex' }}>
                <Icon name="copy" size={14} />
              </span>
            </Tooltip>
          </div>
          <pre
            className="zt-mono-sm"
            style={{
              margin: 0, padding: 20, overflowX: 'auto', color: 'var(--text-on-dark-body)',
              lineHeight: 1.62, tabSize: 2,
            }}
          >
            {shown.yaml}
          </pre>
        </Card>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Card pad={20}>
            <SectionLabel>Versions</SectionLabel>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {versions.map((v) => {
                const on = v.version === selected;
                return (
                  <button
                    key={v.version}
                    onClick={() => setSelected(v.version)}
                    style={{
                      display: 'flex', flexDirection: 'column', gap: 3, alignItems: 'flex-start',
                      textAlign: 'left', padding: '10px 12px', border: 0, cursor: 'pointer',
                      borderRadius: 'var(--r-6)', background: on ? 'rgba(17,17,17,0.05)' : 'transparent',
                      boxShadow: on ? 'inset 1px 0 0 var(--ink)' : 'none',
                      transition: 'var(--t-hover)',
                    }}
                  >
                    <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="zt-mono-sm" style={{ color: 'var(--ink)' }}>v{v.version}</span>
                      {v.active ? <Badge status="clean" tone="clean">Active</Badge> : null}
                    </span>
                    <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>{v.note}</span>
                    <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>
                      {v.createdBy} · {new Date(v.createdAt).toISOString().slice(11, 16)}
                    </span>
                  </button>
                );
              })}
            </div>
          </Card>

          <Card pad={20}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <span className="zt-eyebrow">Exceptions</span>
              <span style={{ flex: 1 }} />
              {pending.length ? (
                <Badge status="redacted" tone="redacted">{pending.length} awaiting approval</Badge>
              ) : null}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {exceptions.map((e) => (
                <div key={e.id} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Tag mono>{classToken(e.entityClass)}</Tag>
                    <span className="zt-mono-sm" style={{ color: 'var(--text-faint)' }}>{e.scope.direction}</span>
                  </div>
                  <p style={{ margin: 0, font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>{e.reason}</p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <StatusDot state={e.approvedBy ? 'clean' : 'redacted'} size={6} />
                    <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>
                      {e.approvedBy
                        ? `Raised by ${e.requestedBy}, approved by ${e.approvedBy}`
                        : `Raised by ${e.requestedBy}, awaiting a second person`}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <p style={{ margin: '16px 0 0', font: 'var(--type-body-sm)', color: 'var(--text-quiet)' }}>
              An exception cannot be approved by the person who raised it. The database refuses it.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
