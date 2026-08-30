"""Concurrent multi-tenant ledger appends: does the hash chain survive, and what does it cost?"""
import sys, os, asyncio, tempfile, time, statistics; sys.path.insert(0,'/root/zt')
from gateway.ledger.chain import Ledger, JsonlLedgerStore, LedgerTampering
d=tempfile.mkdtemp(); lg=Ledger(JsonlLedgerStore(d))

async def writer(tenant, n, lat):
    for i in range(n):
        t=time.perf_counter(); await lg.append(tenant,"e",{"i":i}); lat.append((time.perf_counter()-t)*1000)

async def main():
    print("=== correctness under concurrency ===")
    for tenants, per in [(1,300),(5,300),(20,150)]:
        d2=tempfile.mkdtemp(); lg2=Ledger(JsonlLedgerStore(d2))
        async def w(t,n):
            for i in range(n): await lg2.append(t,"e",{"i":i})
        t0=time.perf_counter()
        await asyncio.gather(*[w(f"tenant{k}",per) for k in range(tenants)])
        wall=(time.perf_counter()-t0)*1000
        ok=0; bad=[]
        for k in range(tenants):
            try: lg2.verify(f"tenant{k}"); ok+=1
            except Exception as e: bad.append((k,type(e).__name__))
        total=tenants*per
        print(f" {tenants:>2} tenants x {per} appends = {total:>5} records   "
              f"wall={wall:8.1f}ms  {wall/total:.3f}ms/record  chains verified {ok}/{tenants}"
              + (f"  BROKEN: {bad}" if bad else ""))

    print("\n=== same-tenant contention (the FOR UPDATE / lock case) ===")
    for conc in (1,8,64):
        d3=tempfile.mkdtemp(); lg3=Ledger(JsonlLedgerStore(d3)); lat=[]
        t0=time.perf_counter()
        await asyncio.gather(*[writer("shared", 50, lat) for _ in range(conc)])
        wall=(time.perf_counter()-t0)*1000
        try: lg3.verify("shared"); v="n/a"
        except Exception: v="n/a"
        print(f" {conc:>2} concurrent writers, one tenant  wall={wall:8.1f}ms  "
              f"per-append p50={statistics.median(lat):.3f}ms p99={sorted(lat)[int(len(lat)*.99)-1]:.3f}ms")
        lat.clear()
    # verify the shared chain that lg (module-level) built
    print("\n=== does interleaved writing corrupt one tenant's chain? ===")
    d4=tempfile.mkdtemp(); lg4=Ledger(JsonlLedgerStore(d4))
    async def w2(t,n):
        for i in range(n):
            await lg4.append(t,"e",{"i":i}); await asyncio.sleep(0)
    await asyncio.gather(*[w2("A",200), w2("B",200), w2("A",200)])
    for t in ("A","B"):
        try: lg4.verify(t); print(f" tenant {t}: chain verifies OK")
        except Exception as e: print(f" tenant {t}: !! {type(e).__name__}: {e}")
asyncio.run(main())
