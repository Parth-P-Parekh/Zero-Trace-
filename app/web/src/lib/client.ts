/**
 * The seam between the views and the data plane.
 *
 * Today every function returns a fixture. When the FastAPI gateway from CODE-01
 * exists, each body becomes a `fetch` against the endpoint named in its comment
 * and **no view changes**, because the return types are already the contract.
 *
 * Endpoints are quoted from PROD-01 §8 / CODE-01 §15.
 */
import {
  COUNTERFACTUAL, COVERAGE, DETECTORS, ESCALATION_CURVE, EXCEPTIONS,
  LEDGER, LICENCE, PAYLOADS, POLICY_VERSIONS, REQUESTS, STUBS,
} from './fixtures';
import type {
  CoverageReport, Counterfactual, Detector, EscalationPoint, HarnessCoverageSnapshot,
  LedgerHead, Licence, PayloadLeg, PolicyException, PolicyVersion, RequestRecord,
  StubNotice,
} from './types';

/** GET /api/requests */
export function listRequests(): RequestRecord[] {
  return REQUESTS;
}

/** GET /api/requests/:id */
export function getRequest(id: string): RequestRecord | undefined {
  return REQUESTS.find((r) => r.id === id);
}

/** GET /api/requests/:id/diff — span paths, classes and offsets only. */
export function getPayload(id: string): PayloadLeg[] {
  return PAYLOADS[id] ?? [];
}

/** GET /api/detectors */
export function listDetectors(): Detector[] {
  return DETECTORS;
}

/** Derived from the benchmark runs. EV-NOV-03. */
export function escalationCurve(): EscalationPoint[] {
  return ESCALATION_CURVE;
}

/** GET /api/policies */
export function listPolicyVersions(): PolicyVersion[] {
  return POLICY_VERSIONS;
}

export function activePolicy(): PolicyVersion {
  return POLICY_VERSIONS.find((p) => p.active) ?? POLICY_VERSIONS[0];
}

export function listExceptions(): PolicyException[] {
  return EXCEPTIONS;
}

/** GET /api/coverage */
export function getCoverage(): CoverageReport {
  return COVERAGE;
}

/** GET /v1/coverage — gateway traversals only; never presented as a bypass ratio. */
export async function getHarnessCoverage(): Promise<HarnessCoverageSnapshot | null> {
  const base = process.env.ZT_GATEWAY_URL?.replace(/\/$/, '');
  if (!base) return null;
  try {
    const response = await fetch(`${base}/v1/coverage`, { cache: 'no-store' });
    if (!response.ok) return null;
    return await response.json() as HarnessCoverageSnapshot;
  } catch {
    return null;
  }
}

/** GET /api/impact/counterfactual?window= */
export function getCounterfactual(): Counterfactual {
  return COUNTERFACTUAL;
}

export function getLedger(): LedgerHead {
  return LEDGER;
}

/** GET /api/licence */
export function getLicence(): Licence {
  return LICENCE;
}

export function getStub(key: keyof typeof STUBS): StubNotice {
  return STUBS[key];
}

/** Aggregates the traffic view's four numbers from the same records the table shows. */
export function trafficSummary() {
  const rows = listRequests();
  const redacted = rows.filter((r) => r.status === 'redacted').length;
  const blocked = rows.filter((r) => r.status === 'blocked').length;
  const findings = rows.reduce((n, r) => n + r.findings.length, 0);
  const inbound = rows.reduce((n, r) => n + r.findings.filter((f) => f.leg === 'inbound').length, 0);
  const latencies = rows.map((r) => r.latencyMs).sort((a, b) => a - b);
  const p95 = latencies[Math.max(0, Math.ceil(latencies.length * 0.95) - 1)];
  return { total: rows.length, redacted, blocked, findings, inbound, p95 };
}
