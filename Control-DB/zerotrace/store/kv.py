"""The key-value substrate Part A runs on.

Part A was written against PostgreSQL. The decision is now Redis, natively, with no
Docker — so persistence goes through this narrow interface instead of SQLAlchemy.

Two implementations, and the second is not a toy:

* `RedisKV` — redis-py asyncio, the real thing.
* `MemoryKV` — the same semantics in-process, so the suite and a laptop demo need no
  server at all. It is the store's counterpart to the policy cache's existing
  `in_process_dict` fallback, and like that one its use is announced rather than silent.

**Why an interface rather than calling redis-py directly.** The ledger's correctness
depends on read-modify-write being atomic under a lock. Naming that requirement in one
place, with two implementations that both have to satisfy the same tests, is what stops
the in-memory path drifting into something weaker than the real one — which would make
every test that uses it a lie.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Protocol


class KV(Protocol):
    """The operations Part A's Redis store needs. Deliberately small."""

    async def incr(self, key: str) -> int: ...
    async def rpush(self, key: str, value: str) -> int: ...
    async def lrange(self, key: str, start: int, stop: int) -> list[str]: ...
    async def llen(self, key: str) -> int: ...
    async def hset_many(self, key: str, mapping: dict[str, str]) -> None: ...
    async def hgetall(self, key: str) -> dict[str, str]: ...
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str) -> None: ...
    async def sadd(self, key: str, value: str) -> None: ...
    async def smembers(self, key: str) -> set[str]: ...
    async def delete(self, key: str) -> None: ...
    async def keys(self, pattern: str) -> list[str]: ...
    async def acquire(self, key: str, token: str, ttl_ms: int) -> bool: ...
    async def release(self, key: str, token: str) -> None: ...


class TenantLock:
    """A mutual-exclusion lock scoped to one tenant's ledger.

    It replaces PostgreSQL's advisory lock, and it exists for the same reason: a row lock
    on the previous record cannot protect two concurrent *first* appends, because neither
    of them sees a previous record. Without this, two racing appends would both hash onto
    genesis and the chain would fork silently — which the verifier would later report as
    tampering, on a ledger nobody tampered with.
    """

    __slots__ = ("_kv", "_key", "_token", "_ttl_ms", "_poll_s", "_timeout_s")

    def __init__(self, kv: KV, key: str, *, ttl_ms: int = 10_000,
                 timeout_s: float = 10.0, poll_s: float = 0.01) -> None:
        self._kv = kv
        self._key = key
        self._token = uuid.uuid4().hex
        self._ttl_ms = ttl_ms
        self._timeout_s = timeout_s
        self._poll_s = poll_s

    async def __aenter__(self) -> "TenantLock":
        deadline = time.monotonic() + self._timeout_s
        while True:
            if await self._kv.acquire(self._key, self._token, self._ttl_ms):
                return self
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"could not acquire the ledger lock {self._key!r} within "
                    f"{self._timeout_s}s; another writer is holding it"
                )
            await asyncio.sleep(self._poll_s)

    async def __aexit__(self, *exc: object) -> None:
        await self._kv.release(self._key, self._token)


class MemoryKV:
    """In-process KV with the same semantics. No server required."""

    def __init__(self) -> None:
        self._h: dict[str, dict[str, str]] = {}
        self._l: dict[str, list[str]] = {}
        self._s: dict[str, set[str]] = {}
        self._v: dict[str, str] = {}
        self._locks: dict[str, tuple[str, float]] = {}
        # One process-wide mutex. Redis is single-threaded per command; this is the
        # equivalent guarantee, and without it the async interleaving in the tests would
        # not be a faithful stand-in.
        self._mutex = asyncio.Lock()

    async def incr(self, key: str) -> int:
        async with self._mutex:
            value = int(self._v.get(key, "0")) + 1
            self._v[key] = str(value)
            return value

    async def rpush(self, key: str, value: str) -> int:
        async with self._mutex:
            self._l.setdefault(key, []).append(value)
            return len(self._l[key])

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        async with self._mutex:
            items = self._l.get(key, [])
            return items[start:] if stop == -1 else items[start : stop + 1]

    async def llen(self, key: str) -> int:
        async with self._mutex:
            return len(self._l.get(key, []))

    async def hset_many(self, key: str, mapping: dict[str, str]) -> None:
        async with self._mutex:
            self._h.setdefault(key, {}).update(mapping)

    async def hgetall(self, key: str) -> dict[str, str]:
        async with self._mutex:
            return dict(self._h.get(key, {}))

    async def get(self, key: str) -> str | None:
        async with self._mutex:
            return self._v.get(key)

    async def set(self, key: str, value: str) -> None:
        async with self._mutex:
            self._v[key] = value

    async def sadd(self, key: str, value: str) -> None:
        async with self._mutex:
            self._s.setdefault(key, set()).add(value)

    async def smembers(self, key: str) -> set[str]:
        async with self._mutex:
            return set(self._s.get(key, set()))

    async def delete(self, key: str) -> None:
        async with self._mutex:
            self._h.pop(key, None)
            self._l.pop(key, None)
            self._s.pop(key, None)
            self._v.pop(key, None)

    async def keys(self, pattern: str) -> list[str]:
        import fnmatch

        async with self._mutex:
            everything = set(self._h) | set(self._l) | set(self._s) | set(self._v)
            return sorted(k for k in everything if fnmatch.fnmatch(k, pattern))

    async def acquire(self, key: str, token: str, ttl_ms: int) -> bool:
        async with self._mutex:
            held = self._locks.get(key)
            if held is not None and held[1] > time.monotonic():
                return False
            self._locks[key] = (token, time.monotonic() + ttl_ms / 1000)
            return True

    async def release(self, key: str, token: str) -> None:
        async with self._mutex:
            held = self._locks.get(key)
            # Only the holder releases. A lock that expired and was taken by someone else
            # must not be deleted by the previous owner finishing late.
            if held is not None and held[0] == token:
                self._locks.pop(key, None)


class RedisKV:
    """redis-py asyncio, decoding to str."""

    #: Compare-and-delete. Releasing without checking the token would let a writer whose
    #: lock had expired delete a lock now held by someone else.
    _RELEASE = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
      return redis.call('del', KEYS[1])
    else
      return 0
    end
    """

    def __init__(self, client: object) -> None:
        self._r = client
        self._release_sha: str | None = None

    async def incr(self, key: str) -> int:
        return int(await self._r.incr(key))

    async def rpush(self, key: str, value: str) -> int:
        return int(await self._r.rpush(key, value))

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        return [_s(v) for v in await self._r.lrange(key, start, stop)]

    async def llen(self, key: str) -> int:
        return int(await self._r.llen(key))

    async def hset_many(self, key: str, mapping: dict[str, str]) -> None:
        await self._r.hset(key, mapping=mapping)

    async def hgetall(self, key: str) -> dict[str, str]:
        raw = await self._r.hgetall(key)
        return {_s(k): _s(v) for k, v in raw.items()}

    async def get(self, key: str) -> str | None:
        value = await self._r.get(key)
        return None if value is None else _s(value)

    async def set(self, key: str, value: str) -> None:
        await self._r.set(key, value)

    async def sadd(self, key: str, value: str) -> None:
        await self._r.sadd(key, value)

    async def smembers(self, key: str) -> set[str]:
        return {_s(v) for v in await self._r.smembers(key)}

    async def delete(self, key: str) -> None:
        await self._r.delete(key)

    async def keys(self, pattern: str) -> list[str]:
        return sorted(_s(k) for k in await self._r.keys(pattern))

    async def acquire(self, key: str, token: str, ttl_ms: int) -> bool:
        return bool(await self._r.set(key, token, nx=True, px=ttl_ms))

    async def release(self, key: str, token: str) -> None:
        if self._release_sha is None:
            self._release_sha = await self._r.script_load(self._RELEASE)
        await self._r.evalsha(self._release_sha, 1, key, token)


def _s(value: object) -> str:
    return value.decode() if isinstance(value, (bytes, bytearray)) else str(value)


class FileKV:
    """A KV that survives the process, without a server.

    The hook runs as a fresh interpreter on every prompt, so `MemoryKV` cannot hold a
    seeded tenant or a policy between two of them -- everything would vanish the moment
    the process exited, and a control plane that forgets its own tenants is not one you
    can test locally.

    This is a single JSON file under ZT_HOME. It is not a database and does not pretend to
    be: every operation reads and rewrites the whole file. That is fine for a laptop with
    one operator and a handful of tenants, and it is wrong for anything else -- set
    ZT_REDIS_URL and use `RedisKV` for a real deployment.

    Writes go to a temporary file and are then renamed, so a crash mid-write leaves the
    previous state rather than a truncated one. A ledger that can be half-written is a
    ledger whose verifier reports tampering nobody did.
    """

    __slots__ = ("_path", "_lock")

    def __init__(self, path: str | Path | None = None) -> None:
        import os as _os

        home = Path(_os.environ.get("ZT_HOME") or (Path.home() / ".zerotrace"))
        self._path = Path(path) if path else home / "store.json"
        self._lock = asyncio.Lock()

    # -- file --

    def _read(self) -> dict:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"h": {}, "l": {}, "s": {}, "v": {}, "locks": {}}

    def _write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(self._path)

    # -- operations --

    async def incr(self, key: str) -> int:
        async with self._lock:
            d = self._read()
            value = int(d["v"].get(key, 0)) + 1
            d["v"][key] = value
            self._write(d)
            return value

    async def rpush(self, key: str, value: str) -> int:
        async with self._lock:
            d = self._read()
            d["l"].setdefault(key, []).append(value)
            self._write(d)
            return len(d["l"][key])

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        items = self._read()["l"].get(key, [])
        return items[start:] if stop == -1 else items[start : stop + 1]

    async def llen(self, key: str) -> int:
        return len(self._read()["l"].get(key, []))

    async def hset_many(self, key: str, mapping: dict[str, str]) -> None:
        async with self._lock:
            d = self._read()
            d["h"].setdefault(key, {}).update(mapping)
            self._write(d)

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self._read()["h"].get(key, {}))

    async def get(self, key: str) -> str | None:
        value = self._read()["v"].get(key)
        return None if value is None else str(value)

    async def set(self, key: str, value: str) -> None:
        async with self._lock:
            d = self._read()
            d["v"][key] = value
            self._write(d)

    async def sadd(self, key: str, value: str) -> None:
        async with self._lock:
            d = self._read()
            members = set(d["s"].get(key, []))
            members.add(value)
            d["s"][key] = sorted(members)
            self._write(d)

    async def smembers(self, key: str) -> set[str]:
        return set(self._read()["s"].get(key, []))

    async def delete(self, key: str) -> None:
        async with self._lock:
            d = self._read()
            for bucket in ("h", "l", "s", "v"):
                d[bucket].pop(key, None)
            self._write(d)

    async def keys(self, pattern: str) -> list[str]:
        import fnmatch

        d = self._read()
        everything = set(d["h"]) | set(d["l"]) | set(d["s"]) | set(d["v"])
        return sorted(k for k in everything if fnmatch.fnmatch(k, pattern))

    async def acquire(self, key: str, token: str, ttl_ms: int) -> bool:
        async with self._lock:
            d = self._read()
            held = d["locks"].get(key)
            if held is not None and held[1] > time.time():
                return False
            d["locks"][key] = [token, time.time() + ttl_ms / 1000]
            self._write(d)
            return True

    async def release(self, key: str, token: str) -> None:
        async with self._lock:
            d = self._read()
            held = d["locks"].get(key)
            if held is not None and held[0] == token:
                d["locks"].pop(key, None)
                self._write(d)
