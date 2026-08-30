# Part A Root Integration Design

## Goal

Patch the completed Part A control and evidence layer into the root full-stack product.

The root `gateway/` package owns the final HTTP request path.

## Ownership

The root product keeps these components:

- Provider-compatible routes.
- Detector and scanner pipelines.
- Checker orchestration.
- JSON span extraction.
- Redaction and verification.
- Vault integration.
- Claude, Codex, browser, extension, and console integrations.

Part A supplies these components:

- Tenant, actor, and session resolution.
- Organisation and business-unit policy storage and inheritance.
- Policy publish validation and action-lattice enforcement.
- PostgreSQL request and finding records.
- Redis policy caching.
- Dual `ctl` and `dp` ledger chains.
- Policy-row hash binding and cross-anchors.
- Control-plane policy APIs.

## Adapter boundary

The root runtime uses a production adapter package.

The adapter implements the root policy and evidence protocols.

It calls Part A services directly in process.

It does not use an HTTP sidecar.

The root VOCAB-01 contract is canonical.

Part A persistence records use the same class names.

The integration must not copy or fork the vocabulary.

## Request flow

1. The root route receives a provider request.
2. The Part A identity service resolves the tenant, actor, and session.
3. The root detector finds sensitive spans.
4. The Part A policy adapter resolves organisation and business-unit policy.
5. The root checker calculates decisions.
6. The root redactor applies and verifies payload changes.
7. Part A stores the request, findings, policy hashes, and `dp` ledger evidence in one transaction.
8. The root gateway sends only the verified serialized payload upstream.
9. The same detector, policy, redaction, verification, and evidence process applies to the inbound response.
10. A failed security-core operation stops unsafe dispatch.

## Persistence rules

The database can store:

- Entity class and family.
- JSON path.
- Span offsets and lengths.
- Organisation and business-unit policy versions and row hashes.
- Intended and applied actions.
- Payload hashes.
- Degradation reasons.

The database, logs, Redis, ledger, and evidence files must not store:

- Sensitive literals.
- Original sensitive payloads.
- Recoverable redaction tokens.
- Reverse token mappings.

## Failure rules

PostgreSQL failure causes a fail-closed response before upstream dispatch.

Redis failure uses the local policy cache and records `policy_cache_local`.

A ledger write failure stops the related side effect.

A detector, redaction, or dispatch verification failure stops upstream dispatch.

The development identity-header mode remains marked as spoofable.

## Compatibility rules

The root `gateway/` public provider routes remain compatible.

The root console and attach tools remain compatible.

The Part A standalone data-plane route is removed from the production path after the root adapter passes the integration gate.

Part A migrations and control-plane behavior remain authoritative for Part A data.

The root JSONL ledger can remain only for an explicit local development mode.

## Verification

The integration gate runs the root product with native isolated PostgreSQL and Redis processes.

It uses a deterministic local upstream.

The gate covers:

- Registered and unregistered actors.
- Organisation and business-unit decisions.
- Outbound and inbound findings.
- Shadow and enforce modes.
- Block, mask, and tokenize-to-mask behavior.
- Redis and PostgreSQL restart behavior.
- Both ledger chains, cross-anchors, and policy-row hashes.
- Root detector, redaction, provider-route, and attach compatibility.
- Direct manual HTTP requests.
- Privacy scans of logs, database rows, and evidence files.
