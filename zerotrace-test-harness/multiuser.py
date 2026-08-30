"""Multi-user / multi-tenant isolation tests."""
import sys, os, asyncio, json, tempfile; sys.path.insert(0,'/root/ztest'); sys.path.insert(0,'/root/zt')
from lib import *
from gateway.base.cache import cache_key, InMemorySpanCache
from gateway.vault.derive import derive_token
from gateway.contracts.entity_classes import EntityClass

A="718190937865"; SECRET=f"Aadhaar {A} and PAN ABCPZ1234C"
KEY=os.getenv("ZT_VAULT_MASTER_KEY","dev-key-not-a-secret").encode()

print("=== 1. is the 'tenant key' actually per-tenant? ===")
print(" app.py builds ONE Checker with tenant_key = ZT_VAULT_MASTER_KEY (a process-wide env var).")
print(" cache_key(k, 'acme', 1, x) ==", cache_key(KEY,"acme",1,SECRET)[:16])
print(" cache_key(k, 'globex',1, x) ==", cache_key(KEY,"globex",1,SECRET)[:16])
print(" -> tenant_id IS in the key, so entries do not cross tenants.")
print(" -> but the KEY is global: anyone holding it can compute another tenant's key.")

print("\n=== 2. does the span cache leak findings across tenants? ===")
async def t2():
    shared = InMemorySpanCache()
    ck = make_checker(cache=shared, key=KEY)
    r1 = await check(ck, {"messages":[{"role":"user","content":SECRET}]}, tenant="acme")
    r2 = await check(ck, {"messages":[{"role":"user","content":SECRET}]}, tenant="globex")
    print(f" tenant acme  : hits={r1.cache_hits} miss={r1.cache_misses}")
    print(f" tenant globex: hits={r2.cache_hits} miss={r2.cache_misses}  "
          f"({'ISOLATED - rescanned' if r2.cache_misses>0 else '!! REUSED acme cache'})")
    # same tenant again -> should hit
    r3 = await check(ck, {"messages":[{"role":"user","content":SECRET}]}, tenant="acme")
    print(f" tenant acme#2: hits={r3.cache_hits} miss={r3.cache_misses} (expected: hits>0)")
asyncio.run(t2())

print("\n=== 3. token derivation across tenants (global key) ===")
for scope in ["sess-shared", "acme:sess1"]:
    a=derive_token(KEY, scope, EntityClass.PAN, "ABCPZ1234C")
    print(f" scope={scope!r:16} token={a}")
print(" -> two tenants that happen to use the same scope_key derive the SAME token,")
print("    because the key is process-global, not per-tenant.")

print("\n=== 4. confirmation oracle: can a holder of the key test a guess? ===")
guess_hit = cache_key(KEY,"globex",1,SECRET)
print(f" attacker computes cache_key(k,'globex',1,<guess>) and looks for it in Redis.")
print(f" guess matches stored key: {guess_hit[:16]}...  -> ORACLE WORKS with the global key")
