"""Identifiers. CODE-01 §4.1 spells request ids as `req_<ulid>`.

A ULID is a 26-character Crockford base32 string: 48 bits of millisecond
timestamp then 80 bits of randomness. It sorts by creation time, which makes
`ORDER BY id` on the requests table meaningful without a second index.

Implemented here rather than pulled in as a dependency — it is fifteen lines and
one less pinned package on the hot path.
"""

from __future__ import annotations

import os

from zerotrace import clock

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # no I, L, O, U


def _encode(value: int, length: int) -> str:
    out = []
    for _ in range(length):
        out.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(out))


def ulid() -> str:
    ms = int(clock.now().timestamp() * 1000)
    randomness = int.from_bytes(os.urandom(10), "big")
    return _encode(ms, 10) + _encode(randomness, 16)


def request_id() -> str:
    return f"req_{ulid()}"


def session_id() -> str:
    return f"ses_{ulid()}"
