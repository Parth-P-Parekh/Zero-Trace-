'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Badge, Card, Icon, Input, Metric, SegmentedControl, StatusDot, Tabs, Tag, Tooltip, EmptyState,
} from '@/ds';
import { GridHead, PageHead } from '@/components/Chrome';
import { classToken, count, exact, ms, risk, shortPath, statusLabel } from '@/lib/format';
import type { RequestRecord } from '@/lib/types';

const COLUMNS = '76px 148px minmax(0,1fr) 172px 52px 104px 68px 18px';

export function TrafficView({
  rows,
  summary,
}: {
  rows: RequestRecord[];
  summary: { total: number; redacted: number; blocked: number; findings: number; inbound: number; p95: number };
}) {
  const [tab, setTab] = useState('all');
  const [range, setRange] = useState('24h');
  const [q, setQ] = useState('');

  const filtered = useMemo(
    () =>
      rows.filter((r) => {
        if (tab === 'redacted' && r.status !== 'redacted') return false;
        if (tab === 'blocked' && r.status !== 'blocked') return false;
        if (tab === 'inbound' && !r.findings.some((f) => f.leg === 'inbound')) return false;
        if (q) {
          const hay = `${r.workload} ${r.actor.label} ${r.path} ${r.findings.map((f) => f.entityClass).join(' ')}`;
          if (!hay.toLowerCase().includes(q.toLowerCase())) return false;
        }
        return true;
      }),
    [rows, tab, q],
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 'var(--page-max)' }}>
      <PageHead
        title="Every payload, both legs, before it moved"
        sub="Requests are intercepted in the egress path. No application here was modified to send them through."
        right={
          <SegmentedControl
            value={range}
            onChange={setRange}
            size="sm"
            items={[
              { value: '24h', label: 'Last 24h' },
              { value: '7d', label: '7 days' },
              { value: '30d', label: '30 days' },
            ]}
          />
        }
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 12 }}>
        <Card pad={18}>
          <Metric label="Payloads inspected" value="1.24M" note="both legs, last 24h" size="sm" />
        </Card>
        <Card pad={18}>
          <Metric label="Values redacted" value="8,411" note="across 27 detectors" size="sm" />
        </Card>
        <Card pad={18}>
          <Metric label="Requests blocked" value="12" note="credentials, no redaction strategy" size="sm" />
        </Card>
        <Card tone="dark" pad={18}>
          <Metric label="Added latency" value="48" unit="ms" note="p95, outbound + inbound" size="sm" onDark />
        </Card>
      </div>

      <Card pad={0}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '16px 16px 0' }}>
          <Tabs
            value={tab}
            onChange={setTab}
            style={{ flex: 1 }}
            items={[
              { value: 'all', label: 'All requests', count: rows.length },
              { value: 'redacted', label: 'Redacted', count: rows.filter((r) => r.status === 'redacted').length },
              { value: 'blocked', label: 'Blocked', count: rows.filter((r) => r.status === 'blocked').length },
              { value: 'inbound', label: 'Inbound leg', count: rows.filter((r) => r.findings.some((f) => f.leg === 'inbound')).length },
            ]}
          />
          <Input
            size="sm"
            icon="search"
            placeholder="Search workloads, paths and classes"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ width: 260, paddingBottom: 10 }}
          />
        </div>

        <div className="zt-table">
          <div>
            <GridHead
              columns={COLUMNS}
              cells={['Time', 'Workload', 'Path', 'Findings', 'Risk', 'Result', 'Latency', '']}
            />
            {filtered.length ? (
              filtered.map((r) => <TrafficRow key={r.id} row={r} />)
            ) : (
              <EmptyState
                icon="search"
                title="No requests match"
                description="Clear the search or widen the range."
              />
            )}
          </div>
        </div>

        <div
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 16px', boxShadow: 'inset 0 1px 0 var(--border-hairline)',
          }}
        >
          <span className="zt-eyebrow">
            {count(filtered.length)} of {exact(1243904)} requests
          </span>
          <span className="zt-mono-sm" style={{ color: 'var(--text-quiet)' }}>
            policy v7 · enforce
          </span>
        </div>
      </Card>
    </div>
  );
}

function TrafficRow({ row }: { row: RequestRecord }) {
  const classes = Array.from(new Set(row.findings.map((f) => f.entityClass)));
  const shown = classes.slice(0, 2);
  const rest = classes.length - shown.length;
  const hasInbound = row.findings.some((f) => f.leg === 'inbound');

  return (
    <Link
      href={`/traffic/${row.id}`}
      style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}
    >
      <div
        className="zt-row"
        style={{
          display: 'grid', gridTemplateColumns: COLUMNS, gap: 12, alignItems: 'center',
          minHeight: 'var(--row-h)', padding: '0 16px',
          boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
          transition: 'background-color var(--d-fast) var(--ease-out)',
        }}
      >
        <span className="zt-mono-sm" style={{ color: 'var(--text-quiet)' }}>{row.ts}</span>

        <span style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
          <span style={{ font: 'var(--type-body-sm)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {row.workload}
          </span>
          <span className="zt-mono-sm" style={{ color: row.actor.unregistered ? 'var(--signal-redacted)' : 'var(--text-faint)' }}>
            {row.actor.unregistered ? 'unregistered' : row.actor.label}
          </span>
        </span>

        <span
          className="zt-mono-sm"
          style={{ color: 'var(--text-body)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
        >
          {row.path}
        </span>

        <span style={{ display: 'flex', gap: 4, alignItems: 'center', minWidth: 0 }}>
          {shown.length === 0 ? (
            <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-faint)' }}>—</span>
          ) : (
            shown.map((c) => (
              <Tag key={c} mono>{classToken(c)}</Tag>
            ))
          )}
          {rest > 0 ? (
            <span className="zt-mono-sm" style={{ color: 'var(--text-quiet)' }}>+{rest}</span>
          ) : null}
          {hasInbound ? (
            <Tooltip label="A finding on the inbound leg">
              <span style={{ display: 'inline-flex', color: 'var(--text-faint)' }}>
                <Icon name="arrow-up-right" size={14} />
              </span>
            </Tooltip>
          ) : null}
        </span>

        <span
          className="zt-mono-sm zt-nums"
          style={{ color: (row.compositeRisk ?? 0) > 0.6 ? 'var(--ink)' : 'var(--text-faint)' }}
        >
          {risk(row.compositeRisk)}
        </span>

        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <StatusDot state={row.status} size={6} />
          <span style={{ font: 'var(--type-body-sm)' }}>{statusLabel(row.status)}</span>
          {row.degraded ? (
            <Tooltip label={`${row.degraded} failed open — result is incomplete`}>
              <span style={{ display: 'inline-flex', color: 'var(--signal-info)' }}>
                <Icon name="clock" size={14} />
              </span>
            </Tooltip>
          ) : null}
        </span>

        <span className="zt-mono-sm zt-nums" style={{ color: 'var(--text-quiet)' }}>{ms(row.latencyMs)}</span>

        <span style={{ color: 'var(--text-faint)', display: 'inline-flex' }}>
          <Icon name="chevron-right" size={14} />
        </span>
      </div>
    </Link>
  );
}
