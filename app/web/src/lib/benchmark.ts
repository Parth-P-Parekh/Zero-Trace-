/**
 * The measured run, typed.
 *
 * `data/benchmark.json` and `data/samples.json` are written by
 * `test_dashboard/publish.py` from a real pass of 5,000,000 synthetic payloads
 * through the actual gateway pipeline - `extract_spans`, the detector pack,
 * `Checker`, `StubPolicyClient`, `plan_redaction`, `verify_dispatch`. Nothing in
 * this file computes a product claim; it reads numbers the run produced.
 *
 * **Where a number was not measured, this returns `null` and the view says so.**
 * That is the whole reason the console can be trusted about the numbers it does
 * show, and it is why there is no fallback value anywhere below.
 */
import raw from '@/data/benchmark.json';
import sampleRows from '@/data/samples.json';

// --------------------------------------------------------------------- types --

export interface RunMeta {
  generated_at: string;
  records: number;
  spans_scanned: number;
  bytes_scanned: number;
  wall_seconds: number;
  records_per_second: number;
  workers: number;
  engines: string;
  corpus_seed: number;
  note: string;
}

export interface Quantiles {
  p50: number; p90?: number; p95: number; p99: number; p999?: number;
  mean: number; max: number;
}

/** The async pass: the real `Checker.check()`, worker-thread hop included. */
export interface AsyncQuantiles {
  records: number; p50_us: number; p95_us: number; p99_us: number;
  max_us: number; mean_us: number;
}

export interface DetectorRow {
  entityClass: string;
  /** Records that were generated carrying this class. */
  expected: number;
  found: number;
  missed: number;
  /** null when the corpus never planted this class. */
  recall: number | null;
  /** Measured against the families generated with nothing in them. */
  precision: number | null;
  f1: number | null;
  falsePositives: number;
  /** Isolated cost of one scan carrying this class. null for composed scanners. */
  runtimeUs: number | null;
  detectors: string[];
  /** Times this class appeared across the whole run, planted or not. */
  observed: number;
}

export interface EvasionRow {
  family: string;
  variant: string;
  records: number;
  detectionRate: number;
  blockRate: number;
  /** Pre-bucketed to a design-system ramp stop, so the drawn cell stays on the ramp. */
  ramp: number;
}

export interface HourRow {
  hour: number; total: number; blocked: number; redacted: number;
  clean: number; share: number;
}

export interface EnvironmentRow {
  actions: Record<string, number>;
  records: number;
  would_block: number;
  would_redact: number;
  allowed: number;
  intervention_rate: number;
  mode: 'enforce' | 'shadow';
}

export interface SampleFinding {
  span_path: string;
  class: string;
  confidence: number;
  stage: string;
  start: number;
  end: number;
  length: number;
  detector: string;
  advisory: boolean;
  origin: string;
  leg: string;
}

export interface SampleRow {
  id: string;
  scenario: string;
  variant: string;
  minute: number;
  actor: { id: string; role: string; groups: string[]; unregistered: boolean };
  workload: string;
  harness: string;
  channel: string;
  env: string;
  provider: string;
  route: string;
  leg: string;
  status: 'clean' | 'redacted' | 'blocked';
  action: string;
  verdict: string;
  rule_index: number | null;
  latency_us: number;
  degraded: string | null;
  cache_hits: number;
  cache_misses: number;
  readonly_skipped: number;
  findings: SampleFinding[];
}

interface Benchmark {
  meta: RunMeta;
  latency: Quantiles;
  latencyAsync: AsyncQuantiles;
  throughput: { spans_per_record: number; bytes_per_record: number; mb_per_second: number };
  outcomes: {
    status: Record<string, number>;
    action: Record<string, number>;
    verdict: Record<string, number>;
    findings_total: number;
    advisory_findings: number;
    redactions_verified: number;
    verify_failures: number;
    overlapping_redactions: number;
    readonly_findings_skipped: number;
    cache_hits: number;
    cache_misses: number;
  };
  integrity: {
    credential_records: number;
    credential_not_blocked: number;
    credential_block_rate: number;
    tool_definition_enforced: number;
    quiet_records: number;
    quiet_false_positive_records: number;
    false_positive_rate: number;
  };
  status: { clean: number; redacted: number; blocked: number; total: number };
  actions: Record<string, number>;
  verdicts: Record<string, number>;
  byClass: Array<{ entityClass: string; count: number; share: number }>;
  byFamily: Array<{ family: string; count: number; share: number }>;
  byStage: Record<string, number>;
  byOrigin: Record<string, number>;
  byConfidence: Record<string, number>;
  bySpanPath: Record<string, number>;
  byDetector: Record<string, number>;
  detectors: DetectorRow[];
  evasion: EvasionRow[];
  collisions: {
    records: number; rate: number; reached_the_splice: number;
    pairs: Record<string, number>;
  };
  degraded: Record<string, number>;
  degradedFormats: Record<string, number>;
  coverage: {
    harness: Record<string, number>;
    route: Record<string, number>;
    provider: Record<string, number>;
    channel: Record<string, number>;
    workload: Record<string, number>;
  };
  environments: Record<string, EnvironmentRow>;
  byActorRole: Record<string, number>;
  scenarios: Record<string, number>;
  scenarioEnforcement: Record<string, { records: number; enforced: number; rate: number | null }>;
  hours: HourRow[];
}

export const run = raw as unknown as Benchmark;
export const samples = sampleRows as unknown as SampleRow[];

// ----------------------------------------------------------------- selectors --

/** The six ramp stops. Every drawn fill in the console resolves to one of these. */
export const RAMP = [1.0, 0.72, 0.52, 0.36, 0.22, 0.11] as const;

export function rampStop(fraction: number): number {
  return RAMP.reduce((best, stop) =>
    Math.abs(stop - fraction) < Math.abs(best - fraction) ? stop : best);
}

/** Total findings that may drive an action - advisory classes excluded. */
export function enforceableFindings(): number {
  return run.outcomes.findings_total - run.outcomes.advisory_findings;
}

/** Values that got a labelled token where a shape-preserving one is claimed. */
export function formatDegradedTotal(): number {
  return Object.values(run.degradedFormats).reduce((a, b) => a + b, 0);
}

/**
 * The classes whose recall the obfuscation scanner drags down. Named rather than
 * inferred: every one of these is at 1.0 on a plain value and below it only
 * because the corpus also spaces, wraps and pads that same value.
 */
export function weakestDetectors(limit = 5): DetectorRow[] {
  return run.detectors
    .filter((d) => d.recall !== null && d.recall < 1)
    .slice(0, limit);
}

export function noisiestDetectors(limit = 5): DetectorRow[] {
  return [...run.detectors]
    .filter((d) => d.precision !== null && d.precision < 1)
    .sort((a, b) => (a.precision ?? 1) - (b.precision ?? 1))
    .slice(0, limit);
}

/** Sample rows, newest first by the minute bucket they were generated in. */
export function sampleFeed(): SampleRow[] {
  return [...samples].sort((a, b) => b.minute - a.minute);
}

export function sampleById(id: string): SampleRow | undefined {
  return samples.find((s) => s.id === id);
}

/** A stable clock label from a minute-of-day bucket. */
export function clock(minute: number): string {
  const h = Math.floor(minute / 60) % 24;
  const m = minute % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}
