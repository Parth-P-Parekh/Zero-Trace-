/**
 * The API contract, transcribed from PROD-01 §7–§8 and CODE-01 §15.
 *
 * These types are the seam. The views read them and nothing else, so when the
 * FastAPI data plane lands, `client.ts` swaps its fetcher and no view changes.
 *
 * The invariant that shapes every type here: **a finding carries a span path, a
 * class and offsets - never the value.** There is no field on any type below
 * that could hold a sensitive original, and adding one would be a product bug,
 * not a feature.
 */

/** Which direction the payload was travelling. Both legs are inspected. */
export type Leg = 'outbound' | 'inbound';

/** The action lattice, ordered by how much of the original reaches the far side. */
export type Action = 'allow' | 'warn' | 'tokenize' | 'mask' | 'block';

/** Ordered weakest to strongest. A business unit may move up this list, never down. */
export const ACTION_LATTICE: readonly Action[] = ['allow', 'warn', 'tokenize', 'mask', 'block'];

/** Pipeline stages. S7 is async and never on the hot path. */
export type Stage = 'S0' | 'S1' | 'S2' | 'S3' | 'S4' | 'S5' | 'S6' | 'S7';

/** Per-stage budgets in ms, from CODE-01 §6. S7 is off the hot path. */
export const STAGE_BUDGET_MS: Record<Exclude<Stage, 'S7'>, number> = {
  S0: 3,
  S1: 8,
  S2: 25,
  S3: 10,
  S4: 2,
  S5: 5,
  S6: 8,
};

export const STAGE_LABEL: Record<Stage, string> = {
  S0: 'Deterministic',
  S1: 'Contextual',
  S2: 'Entity NER',
  S3: 'Compositional',
  S4: 'Policy',
  S5: 'Redact + mint',
  S6: 'Inbound scan',
  S7: 'Adjudicator',
};

/** Detected entity classes. Credentials are never tokenized - policy sends them to block. */
export type EntityClass =
  | 'RAZORPAY_KEY' | 'OPENAI_KEY' | 'AWS_ACCESS_KEY' | 'GITHUB_TOKEN' | 'JWT' | 'PRIVATE_KEY' | 'DB_URI'
  | 'PAN' | 'AADHAAR_FORMAT' | 'CREDIT_CARD' | 'IFSC' | 'GSTIN' | 'UPI_VPA'
  | 'PERSON' | 'ADDRESS' | 'PHONE' | 'EMAIL' | 'MEDICAL' | 'SALARY'
  | 'PINCODE' | 'DOB' | 'GENDER' | 'EMPLOYER'
  | 'EMPLOYEE_ID';

/** Classes that are credentials. Shown blocked, never tokenized. */
export const CREDENTIAL_CLASSES: readonly EntityClass[] = [
  'RAZORPAY_KEY', 'OPENAI_KEY', 'AWS_ACCESS_KEY', 'GITHUB_TOKEN', 'JWT', 'PRIVATE_KEY', 'DB_URI',
];

/** Who made the request. Resolved from the IdP or the mesh - never a developer key. */
export interface Actor {
  id: string;
  label: string;
  /** From the enterprise directory, not from us. */
  role: string;
  /** SCIM-synced. Inbound clearance reads these. */
  groups: string[];
  /** OIDC/SAML subject for people. */
  idpSubject?: string;
  /** SPIFFE ID for services. */
  workloadId?: string;
  /** True when no directory entry matched and `unregistered_workload` policy applied. */
  unregistered?: boolean;
}

export interface Finding {
  id: string;
  leg: Leg;
  /** e.g. `messages[2].tool_result.customer.pan`. Safe to display and to log. */
  spanPath: string;
  entityClass: EntityClass;
  confidence: number;
  /** Character offsets within the span. Never the text. */
  start: number;
  end: number;
  /** Length of the original run, so the mask can be drawn at true width. */
  length: number;
  /** The token that replaced it, e.g. `⟨PERSON_a41⟩`. Not reversible. */
  token?: string;
  detectorId?: string;
  stage: Stage;
  action: Action;
  adjudicated?: boolean;
  /** Set when an approved exception lowered the action. */
  exceptionApplied?: string;
}

/** One inspected request, both legs. */
export interface RequestRecord {
  id: string;
  ts: string;
  actor: Actor;
  workload: string;
  upstreamModel: string;
  path: string;
  action: Action;
  status: 'clean' | 'redacted' | 'blocked';
  findings: Finding[];
  compositeRisk: number | null;
  latencyMs: number;
  latencyByStage: Partial<Record<Stage, number>>;
  escalated: boolean;
  policyVersion: number;
  /** The stage that failed open, when one did. Surfaced, never hidden. */
  degraded?: Stage;
  ledgerId: string;
  mode: 'shadow' | 'enforce';
  /** The rule index that produced the action, for the decision diff. */
  ruleFired?: number;
}

/** The payload as the inspector renders it - masked spans only, never originals. */
export interface PayloadSpan {
  text?: string;
  mask?: string;
  length?: number;
  type?: EntityClass;
}

export interface PayloadLeg {
  leg: Leg;
  method?: string;
  path: string;
  model: string;
  lines: Array<string | PayloadSpan[]>;
  status: 'clean' | 'redacted' | 'blocked';
  latency: string;
}

export interface Detector {
  id: string;
  name: string;
  kind: 'regex' | 'checksum' | 'entropy' | 'heuristic' | 'ner' | 'composite';
  pattern: string;
  entityClass: EntityClass;
  /** `synthesized` detectors carry provenance - the finding that produced them. */
  source: 'seed' | 'synthesized';
  originFindingId?: string;
  /** Set for synthesized detectors: when it was written, and from what. */
  writtenAt?: string;
  precision: number;
  recall: number;
  runtimeUs: number;
  status: 'active' | 'quarantined' | 'rejected' | 'rolled_back';
  createdAt: string;
  /** Why a candidate was quarantined or rejected, in the validator's words. */
  reason?: string;
}

/** One point on the escalation curve - N1's proof that the system gets cheaper. */
export interface EscalationPoint {
  run: number;
  label: string;
  escalationRate: number;
  p95Ms: number;
  costPaisePerMillion: number;
  activeDetectors: number;
}

export interface PolicyVersion {
  version: number;
  yaml: string;
  createdBy: string;
  createdAt: string;
  active: boolean;
  note?: string;
}

export interface PolicyException {
  id: string;
  entityClass: EntityClass;
  scope: { spanPathPrefix?: string; destination?: string; direction?: Leg };
  reason: string;
  requestedBy: string;
  /** Null until an approver signs off. Never equal to `requestedBy` - enforced in the schema. */
  approvedBy: string | null;
  createdAt: string;
  expiresAt: string;
}

export type CoverageVerdict = 'via_zerotrace' | 'direct_egress' | 'blocked_at_boundary';

export interface CoverageEvent {
  id: string;
  ts: string;
  workload: string;
  dstDomain: string;
  bytes: number | null;
  verdict: CoverageVerdict;
}

export interface CoverageReport {
  /** 0–1. The number a CISO asks for before any other. */
  ratio: number;
  viaZeroTrace: number;
  directEgress: number;
  blockedAtBoundary: number;
  windowLabel: string;
  events: CoverageEvent[];
  /** True while the monitor runs on the demo network rather than cloud flow logs. */
  demoNetwork: boolean;
}

export interface HarnessCoverageRow {
  harness: string;
  route: string;
  provider: string;
  channel: string;
  requests: number;
  allowed: number;
  blocked: number;
  failed: number;
  last_seen: string;
}

export interface HarnessCoverageSnapshot {
  scope: 'gateway_observed_only';
  direct_egress_visible: false;
  denominator_available: false;
  started_at: string;
  generated_at: string;
  total_requests: number;
  unclassified_requests: number;
  harnesses: HarnessCoverageRow[];
}

export type LicenceTier = 'pov' | 'platform' | 'enterprise' | 'sovereign';

export interface UsageDay {
  day: string;
  tokensOut: number;
  tokensIn: number;
  leaksPrevented: number;
  escalations: number;
}

export interface Licence {
  tier: LicenceTier;
  tierLabel: string;
  businessUnits: number;
  licensedTokens: number;
  tokensUsed: number;
  mode: 'shadow' | 'enforce';
  periodEnd: string;
  usage: UsageDay[];
  /** Counts and hashes only. Written to disk before transmission. */
  signedCounter: {
    day: string;
    tokensOut: number;
    tokensIn: number;
    leaksPrevented: number;
    ledgerHead: string;
    signature: string;
  };
}

export interface LedgerHead {
  height: number;
  head: string;
  verifiedAt: string;
  intact: boolean;
}

/** Counterfactual: what would have left if ZeroTrace had been off. */
export interface Counterfactual {
  windowLabel: string;
  spans: number;
  classes: number;
  byClass: Array<{ entityClass: EntityClass; spans: number }>;
}

/** A capability that is designed but not built. Every one is labelled in the UI. */
export interface StubNotice {
  capability: string;
  detail: string;
}
