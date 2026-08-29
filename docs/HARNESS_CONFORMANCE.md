# Harness conformance

ZeroTrace treats provider transports as fixtures, not policy forks. Add a JSON file to
`gateway/conformance/` with the request shape, protected system/tool paths, cache
markers, expected origins, and representative SSE frames. Then run:

```text
python scripts/conformance.py
python -m pytest gateway/tests/test_transport_conformance.py -q
```

The suite fails by invariant name for:

- byte-identical no-op round trips;
- system, developer, tool, function, and user origin classification;
- protected system/tool definitions changing;
- cache markers moving;
- SSE frame changes; and
- a planted credential reaching the transport.

Request headers are forwarded by denylist. The gateway removes RFC hop-by-hop framing,
`Host`, `Content-Length`, and its own `X-ZeroTrace-*` control fields; unknown provider
headers and duplicates pass through. Response metadata is relayed with the equivalent
hop-by-hop filtering.

## Runtime coverage

`GET /v1/coverage` reports each harness, route, provider, channel, request count,
outcome, and last-seen time observed by the running gateway. Hooks send an explicit
`X-ZeroTrace-Harness`; proxy traffic falls back to User-Agent and route inference.

The response intentionally says `direct_egress_visible: false` and
`denominator_available: false`. A gateway can prove what traversed it, but only DNS,
firewall, or VPC flow logs can prove what bypassed it. Do not turn this endpoint into a
coverage percentage until that denominator is connected.

## Live prompt-cache proof

The structural suite proves cache fields and byte positions survive locally. The
billable proof is opt-in:

```text
OPENAI_API_KEY=... ZT_CACHE_MODEL=... python scripts/verify_prompt_cache.py
```

It sends the same long Responses prefix twice through `ZT_GATEWAY_URL` and fails unless
the second response reports a positive `usage.input_tokens_details.cached_tokens`.
Keys and model names are never embedded or printed.
