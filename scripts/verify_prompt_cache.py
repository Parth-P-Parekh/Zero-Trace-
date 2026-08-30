#!/usr/bin/env python3
"""Opt-in, billable proof that a repeated Responses prefix produces a cache hit.

Run against ZeroTrace, not directly against the provider.  No key or model name is
embedded and the key is never printed.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("ZT_CACHE_MODEL", "")
    base = os.environ.get("ZT_GATEWAY_URL", "http://127.0.0.1:8080").rstrip("/")
    if not api_key or not model:
        print("Set OPENAI_API_KEY and ZT_CACHE_MODEL. This check makes billable calls.",
              file=sys.stderr)
        return 2

    # A deliberately long, stable prefix. Only the final user turn differs from the
    # cacheable instructions in real use; repeating it here makes the proof unambiguous.
    stable = "ZeroTrace prompt-cache conformance prefix. " * 320
    payload = {
        "model": model,
        "instructions": stable,
        "input": "Reply with the single word ok.",
        "prompt_cache_key": "zerotrace-live-cache-conformance-v1",
        "stream": False,
    }
    cached = []
    responses_url = f"{base}/responses" if base.endswith("/v1") else f"{base}/v1/responses"
    for _ in range(2):
        request = urllib.request.Request(
            responses_url, data=json.dumps(payload).encode(), method="POST",
            headers={
                "authorization": f"Bearer {api_key}",
                "content-type": "application/json",
                "x-zerotrace-harness": "cache-conformance",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.load(response)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            print(f"cache verification failed: {exc}", file=sys.stderr)
            return 1
        details = (result.get("usage", {}).get("input_tokens_details", {}) or {})
        cached.append(int(details.get("cached_tokens", 0) or 0))

    if cached[1] <= 0:
        print(f"FAIL: provider reported cached_tokens={cached}", file=sys.stderr)
        return 1
    print(f"PASS: provider reported cached_tokens={cached} through {base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
