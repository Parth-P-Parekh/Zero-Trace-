'use client';

/**
 * The escalation rate across benchmark runs. Drawn, not charted - a polyline over
 * a ramp-derived horizontal gradient, which is the readme's one sanctioned
 * functional use of a gradient and happens to be the product's own argument:
 * the line falls as the system writes its own detectors.
 *
 * No chart library. At three to six points a library is more code than the shape.
 */
import type { EscalationPoint } from '@/lib/types';
import { percent } from '@/lib/format';

const W = 560;
const H = 150;
const PAD = { top: 16, right: 16, bottom: 26, left: 34 };

export function EscalationCurve({ points }: { points: EscalationPoint[] }) {
  if (points.length < 2) return null;

  const max = Math.max(...points.map((p) => p.escalationRate));
  const ceil = Math.ceil((max * 100) / 4) * 4 / 100;
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const x = (i: number) => PAD.left + (i / (points.length - 1)) * innerW;
  const y = (v: number) => PAD.top + innerH - (v / ceil) * innerH;

  const line = points.map((p, i) => `${x(i)},${y(p.escalationRate)}`).join(' ');
  const area = `${PAD.left},${PAD.top + innerH} ${line} ${PAD.left + innerW},${PAD.top + innerH}`;
  const first = points[0];
  const last = points[points.length - 1];
  const drop = 1 - last.escalationRate / first.escalationRate;

  return (
    <div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        height={H}
        role="img"
        aria-label={`Escalation rate falls from ${percent(first.escalationRate)} on run 1 to ${percent(last.escalationRate)} on run ${last.run}.`}
        style={{ display: 'block', overflow: 'visible' }}
      >
        <defs>
          <linearGradient id="zt-drain-fill" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#F2F2F0" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#F2F2F0" stopOpacity="0.04" />
          </linearGradient>
        </defs>

        {[0, 0.5, 1].map((t) => (
          <g key={t}>
            <line
              x1={PAD.left} x2={PAD.left + innerW}
              y1={PAD.top + innerH * t} y2={PAD.top + innerH * t}
              stroke="rgba(242,242,240,0.11)" strokeWidth="1"
            />
            <text
              x={PAD.left - 8} y={PAD.top + innerH * t + 4}
              textAnchor="end" fill="rgba(242,242,240,0.36)"
              style={{ font: 'var(--type-mono-sm)' }}
            >
              {Math.round(ceil * (1 - t) * 100)}%
            </text>
          </g>
        ))}

        <polygon points={area} fill="url(#zt-drain-fill)" />
        <polyline
          points={line}
          fill="none"
          stroke="#F2F2F0"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {points.map((p, i) => (
          <g key={p.run}>
            <circle
              cx={x(i)} cy={y(p.escalationRate)} r={i === points.length - 1 ? 4 : 3}
              fill={i === points.length - 1 ? '#F2F2F0' : '#0B0B0B'}
              stroke="#F2F2F0" strokeWidth="1.5"
            />
            <text
              x={x(i)} y={H - 8} textAnchor="middle"
              fill="rgba(242,242,240,0.52)" style={{ font: 'var(--type-mono-sm)' }}
            >
              {p.label}
            </text>
          </g>
        ))}
      </svg>

      <p
        style={{
          margin: '14px 0 0', font: 'var(--type-body-sm)',
          color: 'var(--text-on-dark-body)', maxWidth: '54ch',
        }}
      >
        Escalation fell {percent(drop, 0)} across three runs on the same corpus, from{' '}
        {percent(first.escalationRate)} to {percent(last.escalationRate)}. Each fall is a detector
        the adjudicator taught the hot path, so the same traffic now resolves without a model call.
      </p>
    </div>
  );
}
