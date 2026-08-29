/**
 * Fixtures shaped to the contract in `types.ts`.
 *
 * No backend exists yet — CODE-01 is a plan, not code. These stand in for it and
 * are deliberately shaped like real traffic from the benchmark corpus (CODE-01
 * §18): the credential cases, the compositional case with no flaggable entity,
 * the inbound clearance case, one degraded request, one unregistered workload.
 *
 * Every value here is synthetic. No fixture contains a real secret, and no
 * fixture field can hold an original value — see the note in `types.ts`.
 */
import type {
  Actor, CoverageReport, Counterfactual, Detector, EscalationPoint, Licence, LedgerHead,
  PayloadLeg, PolicyException, PolicyVersion, RequestRecord, StubNotice,
} from './types';

const ACTORS: Record<string, Actor> = {
  supportAgent: {
    id: 'act_01hq3', label: 'priya.n', role: 'support_agent',
    groups: ['support', 'payments-bu'], idpSubject: 'a41f9c02-support',
  },
  checkoutSvc: {
    id: 'act_01hq7', label: 'checkout-api', role: 'service',
    groups: ['payments-bu'], workloadId: 'spiffe://acme.internal/ns/payments/sa/checkout',
  },
  clinicalSvc: {
    id: 'act_01hq9', label: 'care-assist', role: 'service',
    groups: ['clinical-bu'], workloadId: 'spiffe://acme.internal/ns/clinical/sa/assist',
  },
  analyst: {
    id: 'act_01hqb', label: 'r.menon', role: 'analyst',
    groups: ['analytics'], idpSubject: 'b8827de1-analyst',
  },
  unknown: {
    id: 'act_unreg_7', label: 'batch-exporter', role: 'unregistered',
    groups: [], workloadId: 'spiffe://acme.internal/ns/default/sa/batch-exporter',
    unregistered: true,
  },
};

export const REQUESTS: RequestRecord[] = [
  {
    id: 'req_01JQ7F3M', ts: '14:02:11', actor: ACTORS.supportAgent, workload: 'support-copilot',
    upstreamModel: 'hive-core', path: '/v1/chat/completions', action: 'block', status: 'blocked',
    compositeRisk: 0.42, latencyMs: 24, escalated: false, policyVersion: 7,
    ledgerId: 'led_01JQ7F3M4K', mode: 'enforce', ruleFired: 1,
    latencyByStage: { S0: 2.1, S1: 5.4, S2: 11.8, S3: 3.1, S4: 0.9, S5: 0, S6: 0 },
    findings: [
      { id: 'f_9001', leg: 'outbound', spanPath: 'messages[1].content', entityClass: 'RAZORPAY_KEY',
        confidence: 0.99, start: 118, end: 142, length: 24, stage: 'S0', action: 'block' },
      { id: 'f_9002', leg: 'outbound', spanPath: 'messages[1].content', entityClass: 'PAN',
        confidence: 0.97, start: 212, end: 222, length: 10, token: 'AAAPZ7781C', stage: 'S0', action: 'tokenize' },
      { id: 'f_9003', leg: 'outbound', spanPath: 'messages[1].content', entityClass: 'PERSON',
        confidence: 0.94, start: 38, end: 50, length: 12, token: '⟨PERSON_a41⟩', stage: 'S2', action: 'tokenize' },
    ],
  },
  {
    id: 'req_01JQ7F2X', ts: '14:01:48', actor: ACTORS.analyst, workload: 'analytics-notebook',
    upstreamModel: 'hive-core', path: '/v1/chat/completions', action: 'tokenize', status: 'redacted',
    compositeRisk: 0.78, latencyMs: 31, escalated: true, policyVersion: 7,
    ledgerId: 'led_01JQ7F2XB1', mode: 'enforce', ruleFired: 4,
    latencyByStage: { S0: 2.4, S1: 6.1, S2: 14.2, S3: 6.0, S4: 1.1, S5: 1.2, S6: 0 },
    findings: [
      { id: 'f_9010', leg: 'outbound', spanPath: 'messages[0].content$json.pincode', entityClass: 'PINCODE',
        confidence: 0.99, start: 0, end: 6, length: 6, token: '411052', stage: 'S1', action: 'tokenize' },
      { id: 'f_9011', leg: 'outbound', spanPath: 'messages[0].content$json.dob', entityClass: 'DOB',
        confidence: 0.95, start: 0, end: 10, length: 10, token: '1988-04-17', stage: 'S1', action: 'tokenize' },
      { id: 'f_9012', leg: 'outbound', spanPath: 'messages[0].content$json.gender', entityClass: 'GENDER',
        confidence: 0.97, start: 0, end: 6, length: 6, stage: 'S1', action: 'allow' },
      { id: 'f_9013', leg: 'outbound', spanPath: 'messages[0].content$json.employer', entityClass: 'EMPLOYER',
        confidence: 0.86, start: 0, end: 18, length: 18, token: '⟨ORG_7kq⟩', stage: 'S2', action: 'tokenize' },
    ],
  },
  {
    id: 'req_01JQ7F1P', ts: '14:00:52', actor: ACTORS.clinicalSvc, workload: 'care-assist',
    upstreamModel: 'hive-core', path: '/v1/messages', action: 'mask', status: 'redacted',
    compositeRisk: 0.31, latencyMs: 38, escalated: false, policyVersion: 7,
    ledgerId: 'led_01JQ7F1PD9', mode: 'enforce', ruleFired: 5,
    latencyByStage: { S0: 2.0, S1: 5.2, S2: 18.4, S3: 2.8, S4: 1.0, S5: 1.4, S6: 7.2 },
    findings: [
      { id: 'f_9020', leg: 'outbound', spanPath: 'messages[0].content', entityClass: 'PERSON',
        confidence: 0.92, start: 24, end: 36, length: 12, token: '⟨PERSON_c07⟩', stage: 'S2', action: 'tokenize' },
      { id: 'f_9021', leg: 'inbound', spanPath: 'content[0].text', entityClass: 'MEDICAL',
        confidence: 0.88, start: 142, end: 198, length: 56, stage: 'S2', action: 'mask' },
    ],
  },
  {
    id: 'req_01JQ7F0D', ts: '13:59:30', actor: ACTORS.checkoutSvc, workload: 'checkout-api',
    upstreamModel: 'hive-core', path: '/v1/chat/completions', action: 'allow', status: 'clean',
    compositeRisk: 0.08, latencyMs: 19, escalated: false, policyVersion: 7,
    ledgerId: 'led_01JQ7F0DA2', mode: 'enforce', findings: [],
    latencyByStage: { S0: 1.9, S1: 4.8, S2: 0, S3: 2.1, S4: 0.8, S5: 0, S6: 6.4 },
  },
  {
    id: 'req_01JQ7EZ8', ts: '13:58:03', actor: ACTORS.supportAgent, workload: 'support-copilot',
    upstreamModel: 'hive-core', path: '/v1/chat/completions', action: 'tokenize', status: 'redacted',
    compositeRisk: 0.22, latencyMs: 44, escalated: false, policyVersion: 7,
    ledgerId: 'led_01JQ7EZ8F4', mode: 'enforce', degraded: 'S2', ruleFired: 3,
    latencyByStage: { S0: 2.2, S1: 6.0, S2: 25.0, S3: 3.4, S4: 1.0, S5: 1.1, S6: 5.9 },
    findings: [
      { id: 'f_9030', leg: 'outbound', spanPath: 'messages[2].tool_result$json.customer.phone',
        entityClass: 'PHONE', confidence: 0.91, start: 0, end: 10, length: 10, token: '9812207734',
        stage: 'S1', action: 'tokenize' },
    ],
  },
  {
    id: 'req_01JQ7EY1', ts: '13:56:41', actor: ACTORS.unknown, workload: 'batch-exporter',
    upstreamModel: 'hive-core', path: '/v1/embeddings', action: 'mask', status: 'redacted',
    compositeRisk: 0.55, latencyMs: 27, escalated: true, policyVersion: 7,
    ledgerId: 'led_01JQ7EY1C8', mode: 'enforce',
    latencyByStage: { S0: 2.0, S1: 5.1, S2: 12.9, S3: 4.2, S4: 1.0, S5: 1.3, S6: 0 },
    findings: [
      { id: 'f_9040', leg: 'outbound', spanPath: 'input[14]', entityClass: 'EMAIL',
        confidence: 0.96, start: 0, end: 22, length: 22, stage: 'S0', action: 'mask' },
      { id: 'f_9041', leg: 'outbound', spanPath: 'input[31]', entityClass: 'ADDRESS',
        confidence: 0.79, start: 0, end: 34, length: 34, stage: 'S2', action: 'mask' },
    ],
  },
  {
    id: 'req_01JQ7EX6', ts: '13:55:12', actor: ACTORS.checkoutSvc, workload: 'checkout-api',
    upstreamModel: 'hive-core', path: '/v1/chat/completions', action: 'tokenize', status: 'redacted',
    compositeRisk: 0.19, latencyMs: 22, escalated: false, policyVersion: 7,
    ledgerId: 'led_01JQ7EX6E3', mode: 'enforce', ruleFired: 2,
    latencyByStage: { S0: 2.1, S1: 5.0, S2: 0, S3: 2.0, S4: 0.9, S5: 1.0, S6: 6.1 },
    findings: [
      { id: 'f_9050', leg: 'outbound', spanPath: 'messages[1].content', entityClass: 'EMPLOYEE_ID',
        confidence: 1.0, start: 64, end: 75, length: 11, token: 'ACM-7719-DQ',
        detectorId: 'det_synth_41', stage: 'S0', action: 'tokenize' },
    ],
  },
  {
    id: 'req_01JQ7EW2', ts: '13:53:47', actor: ACTORS.analyst, workload: 'analytics-notebook',
    upstreamModel: 'hive-core', path: '/v1/chat/completions', action: 'allow', status: 'clean',
    compositeRisk: 0.11, latencyMs: 18, escalated: false, policyVersion: 7,
    ledgerId: 'led_01JQ7EW2A7', mode: 'enforce', findings: [],
    latencyByStage: { S0: 1.8, S1: 4.6, S2: 0, S3: 1.9, S4: 0.8, S5: 0, S6: 5.8 },
  },
  {
    id: 'req_01JQ7EV9', ts: '13:52:20', actor: ACTORS.supportAgent, workload: 'support-copilot',
    upstreamModel: 'hive-core', path: '/v1/chat/completions', action: 'block', status: 'blocked',
    compositeRisk: 0.28, latencyMs: 21, escalated: false, policyVersion: 7,
    ledgerId: 'led_01JQ7EV9B5', mode: 'enforce', ruleFired: 1,
    latencyByStage: { S0: 2.0, S1: 5.3, S2: 8.9, S3: 2.4, S4: 0.9, S5: 0, S6: 0 },
    findings: [
      { id: 'f_9060', leg: 'outbound', spanPath: 'messages[3].content', entityClass: 'AWS_ACCESS_KEY',
        confidence: 1.0, start: 202, end: 222, length: 20, stage: 'S0', action: 'block' },
    ],
  },
  {
    id: 'req_01JQ7EU4', ts: '13:50:58', actor: ACTORS.clinicalSvc, workload: 'care-assist',
    upstreamModel: 'hive-core', path: '/v1/messages', action: 'allow', status: 'clean',
    compositeRisk: 0.06, latencyMs: 20, escalated: false, policyVersion: 7,
    ledgerId: 'led_01JQ7EU4D1', mode: 'enforce', findings: [],
    latencyByStage: { S0: 1.9, S1: 4.7, S2: 0, S3: 1.8, S4: 0.8, S5: 0, S6: 6.0 },
  },
  {
    id: 'req_01JQ7ET7', ts: '13:49:33', actor: ACTORS.analyst, workload: 'analytics-notebook',
    upstreamModel: 'hive-core', path: '/v1/chat/completions', action: 'tokenize', status: 'redacted',
    compositeRisk: 0.64, latencyMs: 35, escalated: true, policyVersion: 7,
    ledgerId: 'led_01JQ7ET7C2', mode: 'enforce', ruleFired: 4,
    latencyByStage: { S0: 2.3, S1: 5.8, S2: 15.1, S3: 5.4, S4: 1.0, S5: 1.2, S6: 0 },
    findings: [
      { id: 'f_9070', leg: 'outbound', spanPath: 'messages[0].content$json.pincode', entityClass: 'PINCODE',
        confidence: 0.98, start: 0, end: 6, length: 6, stage: 'S1', action: 'tokenize' },
      { id: 'f_9071', leg: 'outbound', spanPath: 'messages[0].content$json.employer', entityClass: 'EMPLOYER',
        confidence: 0.83, start: 0, end: 21, length: 21, stage: 'S2', action: 'tokenize' },
    ],
  },
  {
    id: 'req_01JQ7ES1', ts: '13:48:04', actor: ACTORS.checkoutSvc, workload: 'checkout-api',
    upstreamModel: 'hive-core', path: '/v1/chat/completions', action: 'allow', status: 'clean',
    compositeRisk: 0.04, latencyMs: 17, escalated: false, policyVersion: 6,
    ledgerId: 'led_01JQ7ES1A9', mode: 'enforce', findings: [],
    latencyByStage: { S0: 1.7, S1: 4.5, S2: 0, S3: 1.7, S4: 0.8, S5: 0, S6: 5.7 },
  },
];

/** Payload legs for the inspector, keyed by request id. Masked spans only. */
export const PAYLOADS: Record<string, PayloadLeg[]> = {
  req_01JQ7F3M: [
    {
      leg: 'outbound', method: 'POST', path: '/v1/chat/completions', model: 'hive-core',
      status: 'blocked', latency: '24 ms',
      lines: [
        '{ "model": "hive-core", "messages": [',
        '  { "role": "system", "content": "You are a support triage assistant." },',
        ['  { "role": "user", "content": "Customer ', { mask: 'Priya Sharma', length: 12, type: 'PERSON' }, ' says her'],
        ['    refund failed. Key on the account is ', { mask: 'rzp_live_A1b2C3d4E5f6G7', length: 24, type: 'RAZORPAY_KEY' }, ','],
        ['    PAN ', { mask: 'ABCPZ1234C', length: 10, type: 'PAN' }, '. Draft a reply." }'],
        '] }',
      ],
    },
  ],
  req_01JQ7F1P: [
    {
      leg: 'outbound', method: 'POST', path: '/v1/messages', model: 'hive-core',
      status: 'redacted', latency: '31 ms',
      lines: [
        '{ "model": "hive-core", "messages": [',
        ['  { "role": "user", "content": "Summarise ', { mask: 'Arjun Mehta', length: 12, type: 'PERSON' }, "'s"],
        '    last three visits." }',
        '] }',
      ],
    },
    {
      leg: 'inbound', method: 'RESPONSE', path: '/v1/messages', model: 'hive-core',
      status: 'redacted', latency: '7 ms',
      lines: [
        '{ "content": [ { "type": "text", "text":',
        '  "Three visits in the last 90 days. Two routine, one referral.',
        ['   Referral note: ', { mask: 'suspected early-stage cardiomyopathy', length: 56, type: 'MEDICAL' }],
        '   Follow-up scheduled." } ] }',
      ],
    },
  ],
};

export const DETECTORS: Detector[] = [
  {
    id: 'det_synth_41', name: 'acme employee id', kind: 'regex', pattern: 'ACM-[0-9]{4}-[A-Z]{2}',
    entityClass: 'EMPLOYEE_ID', source: 'synthesized', originFindingId: 'f_8841',
    writtenAt: '2026-08-29T14:32:00Z', precision: 1.0, recall: 0.94, runtimeUs: 310,
    status: 'active', createdAt: '2026-08-29T14:32:00Z',
  },
  {
    id: 'det_seed_01', name: 'razorpay live key', kind: 'regex', pattern: 'rzp_(live|test)_[A-Za-z0-9]{14,}',
    entityClass: 'RAZORPAY_KEY', source: 'seed', precision: 1.0, recall: 1.0, runtimeUs: 140,
    status: 'active', createdAt: '2026-08-29T09:00:00Z',
  },
  {
    id: 'det_seed_02', name: 'aws access key', kind: 'regex', pattern: '(AKIA|ASIA)[0-9A-Z]{16}',
    entityClass: 'AWS_ACCESS_KEY', source: 'seed', precision: 1.0, recall: 1.0, runtimeUs: 120,
    status: 'active', createdAt: '2026-08-29T09:00:00Z',
  },
  {
    id: 'det_seed_03', name: 'pan', kind: 'checksum', pattern: '[A-Z]{5}[0-9]{4}[A-Z]',
    entityClass: 'PAN', source: 'seed', precision: 0.99, recall: 0.98, runtimeUs: 220,
    status: 'active', createdAt: '2026-08-29T09:00:00Z',
  },
  {
    id: 'det_seed_04', name: 'aadhaar format', kind: 'checksum', pattern: '[2-9][0-9]{3}\\s?[0-9]{4}\\s?[0-9]{4}',
    entityClass: 'AADHAAR_FORMAT', source: 'seed', precision: 0.98, recall: 0.96, runtimeUs: 340,
    status: 'active', createdAt: '2026-08-29T09:00:00Z',
  },
  {
    id: 'det_seed_05', name: 'upi vpa', kind: 'regex', pattern: '[\\w.\\-]{2,256}@[a-zA-Z]{2,64}',
    entityClass: 'UPI_VPA', source: 'seed', precision: 0.91, recall: 0.99, runtimeUs: 180,
    status: 'active', createdAt: '2026-08-29T09:00:00Z',
  },
  {
    id: 'det_synth_44', name: 'partner contract number', kind: 'regex', pattern: 'CN-[0-9]{2}-[0-9]{6}',
    entityClass: 'EMPLOYEE_ID', source: 'synthesized', originFindingId: 'f_8902',
    writtenAt: '2026-08-29T15:14:00Z', precision: 0.97, recall: 0.61, runtimeUs: 290,
    status: 'quarantined', createdAt: '2026-08-29T15:14:00Z',
    reason: 'Recall improvement below threshold on the full corpus. Held for the next hourly pass.',
  },
  {
    id: 'det_synth_45', name: 'internal ticket ref', kind: 'regex', pattern: '[A-Z]{2,4}-[0-9]+',
    entityClass: 'EMPLOYEE_ID', source: 'synthesized', originFindingId: 'f_8911',
    writtenAt: '2026-08-29T15:41:00Z', precision: 0.62, recall: 0.88, runtimeUs: 260,
    status: 'rejected', createdAt: '2026-08-29T15:41:00Z',
    reason: 'Precision regression of 3.1% on the full corpus, over the 0.5% ceiling. Matched JIRA keys in code blocks.',
  },
];

/** Runs 1 to 3 of the benchmark. The line falls — this is EV-NOV-03. */
export const ESCALATION_CURVE: EscalationPoint[] = [
  { run: 1, label: 'Run 1', escalationRate: 0.114, p95Ms: 62, costPaisePerMillion: 81, activeDetectors: 24 },
  { run: 2, label: 'Run 2', escalationRate: 0.071, p95Ms: 55, costPaisePerMillion: 68, activeDetectors: 26 },
  { run: 3, label: 'Run 3', escalationRate: 0.038, p95Ms: 48, costPaisePerMillion: 58, activeDetectors: 27 },
];

export const POLICY_VERSIONS: PolicyVersion[] = [
  {
    version: 7, createdBy: 'a.kulkarni', createdAt: '2026-08-29T13:20:00Z', active: true,
    note: 'Added inbound clearance rule for clinical classes.',
    yaml: `version: 7
org: acme                          # policy is org-scoped; business units inherit
business_unit: payments            # a BU override may narrow, never widen
mode: enforce
default: mask
unregistered_workload: mask        # a service nobody onboarded is still covered
promotion: auto                    # auto | approve
fail: closed                       # declared per environment, never implicit

rules:
  - match: {class: [API_KEY, PRIVATE_KEY, JWT, DB_URI]}
    action: block                  # credentials are never tokenized
    notify: [security-oncall]

  - match: {class: [PAN, AADHAAR_FORMAT, CREDIT_CARD]}
    action: tokenize
    format_preserving: true

  - match: {class: [PERSON, ADDRESS, PHONE, EMAIL]}
    action: tokenize
    except:
      - actor_role: support_agent
        destination: on_prem_model
        action: allow

  - match: {composite_risk: ">0.6"}
    action: tokenize
    escalate: true

  - match: {direction: inbound, class: [MEDICAL, SALARY, PERSON, ADDRESS]}
    action: mask
    unless:
      - actor_role: [support_lead, dpo]
      - actor_group: clinical_staff
    reason: "retrieval and agent memory are not access control"

escalation:
  confidence_band: [0.35, 0.75]
  shadow_sample_rate: 0.15
  max_promotions_per_hour: 6`,
  },
  {
    version: 6, createdBy: 'a.kulkarni', createdAt: '2026-08-29T11:05:00Z', active: false,
    note: 'Outbound only. Superseded when the inbound leg went live.', yaml: '# version 6 — outbound rules only',
  },
  {
    version: 5, createdBy: 's.rao', createdAt: '2026-08-29T09:12:00Z', active: false,
    note: 'Initial enforce-mode policy for the payments business unit.', yaml: '# version 5',
  },
];

export const EXCEPTIONS: PolicyException[] = [
  {
    id: 'exc_204', entityClass: 'PERSON', scope: { spanPathPrefix: 'messages[0].content', direction: 'outbound' },
    reason: 'Public figure names in a media-monitoring prompt were tokenized, breaking the summary.',
    requestedBy: 'r.menon', approvedBy: 'a.kulkarni',
    createdAt: '2026-08-29T12:40:00Z', expiresAt: '2026-09-28T12:40:00Z',
  },
  {
    id: 'exc_205', entityClass: 'EMPLOYER', scope: { spanPathPrefix: 'messages[0].content$json', direction: 'outbound' },
    reason: 'Employer field is the tenant name in this workload, not a quasi-identifier.',
    requestedBy: 'r.menon', approvedBy: null,
    createdAt: '2026-08-29T14:18:00Z', expiresAt: '2026-09-28T14:18:00Z',
  },
];

export const COVERAGE: CoverageReport = {
  ratio: 0.987, viaZeroTrace: 1243904, directEgress: 2, blockedAtBoundary: 16341,
  windowLabel: 'last 24h', demoNetwork: true,
  events: [
    { id: 'cov_9001', ts: '13:57:12', workload: 'batch-exporter', dstDomain: 'api.openai.com', bytes: null, verdict: 'direct_egress' },
    { id: 'cov_9002', ts: '11:04:38', workload: 'ml-scratch-01', dstDomain: 'api.anthropic.com', bytes: null, verdict: 'direct_egress' },
    { id: 'cov_9003', ts: '13:57:12', workload: 'batch-exporter', dstDomain: 'api.openai.com', bytes: 0, verdict: 'blocked_at_boundary' },
    { id: 'cov_9004', ts: '12:22:07', workload: 'support-copilot', dstDomain: 'api.openai.com', bytes: 0, verdict: 'blocked_at_boundary' },
  ],
};

export const LICENCE: Licence = {
  tier: 'platform', tierLabel: 'Platform', businessUnits: 3,
  licensedTokens: 250_000_000, tokensUsed: 188_412_000,
  mode: 'enforce', periodEnd: '2027-08-29',
  usage: [
    { day: 'Mon', tokensOut: 18_400_000, tokensIn: 9_100_000, leaksPrevented: 1204, escalations: 812 },
    { day: 'Tue', tokensOut: 21_100_000, tokensIn: 10_400_000, leaksPrevented: 1388, escalations: 744 },
    { day: 'Wed', tokensOut: 19_800_000, tokensIn: 9_900_000, leaksPrevented: 1291, escalations: 690 },
    { day: 'Thu', tokensOut: 24_200_000, tokensIn: 12_100_000, leaksPrevented: 1607, escalations: 611 },
    { day: 'Fri', tokensOut: 26_900_000, tokensIn: 13_400_000, leaksPrevented: 1744, escalations: 540 },
    { day: 'Sat', tokensOut: 8_100_000, tokensIn: 4_000_000, leaksPrevented: 502, escalations: 190 },
    { day: 'Sun', tokensOut: 6_400_000, tokensIn: 3_200_000, leaksPrevented: 411, escalations: 158 },
  ],
  signedCounter: {
    day: '2026-08-29', tokensOut: 26_900_000, tokensIn: 13_400_000, leaksPrevented: 1744,
    ledgerHead: '9f2c41ab7de0',
    signature: 'sig_7c1e…a904',
  },
};

export const LEDGER: LedgerHead = {
  height: 1_260_247, head: '9f2c41ab7de0', verifiedAt: '14:02:19', intact: true,
};

export const COUNTERFACTUAL: Counterfactual = {
  windowLabel: 'last 24h', spans: 8411, classes: 19,
  byClass: [
    { entityClass: 'PERSON', spans: 3140 },
    { entityClass: 'EMAIL', spans: 1802 },
    { entityClass: 'PHONE', spans: 1244 },
    { entityClass: 'PAN', spans: 861 },
    { entityClass: 'ADDRESS', spans: 704 },
    { entityClass: 'RAZORPAY_KEY', spans: 312 },
    { entityClass: 'AADHAAR_FORMAT', spans: 219 },
    { entityClass: 'AWS_ACCESS_KEY', spans: 129 },
  ],
};

/** Designed, not built. Every surface that touches one of these says so. */
export const STUBS: Record<string, StubNotice> = {
  identity: {
    capability: 'SSO and SCIM',
    detail: 'Running against a seeded OIDC provider and a static group map. Directory sync is designed, not built.',
  },
  coverage: {
    capability: 'Cloud flow-log connectors',
    detail: 'Coverage is joined from this network’s own DNS and gateway logs. VPC flow-log connectors are post-hackathon.',
  },
  billing: {
    capability: 'Razorpay test mode',
    detail: 'Payment links are issued against Razorpay test credentials. No live key exists in this build.',
  },
  deployment: {
    capability: 'HA and air-gap',
    detail: 'Single node. The Helm chart, HA pair and air-gapped bundle are designed, not built.',
  },
};
