import sys, asyncio, json, statistics, time; sys.path.insert(0,'/root/ztest')
from lib import *
CODE = open('/root/zt/gateway/base/scanner.py').read()

def convo(n, chunk=900):
    m=[]
    for i in range(n):
        m += [{"role":"user","content":f"turn {i} "+CODE[:400]},
              {"role":"user","content":[{"type":"tool_result","tool_use_id":f"t{i}","content":CODE[:chunk]}]}]
    return {"messages":m}

SMALL = convo(2)
HUGE  = convo(40, chunk=9000)   # ~360KB agentic payload

async def main():
    ck = make_checker(cache=NullSpanCache(), ceiling=50.0)
    # baseline: small request alone
    lat=[]
    for _ in range(20):
        t=time.perf_counter(); await ck.check(tree_of(SMALL),"t"); lat.append((time.perf_counter()-t)*1000)
    base = statistics.median(lat)
    print(f"baseline small request alone         p50={base:6.2f}ms  p95={sorted(lat)[18]:6.2f}ms")

    # small requests concurrent with one huge request
    async def hog():
        return await ck.check(tree_of(HUGE),"t")
    async def small():
        t=time.perf_counter(); r=await ck.check(tree_of(SMALL),"t"); return (time.perf_counter()-t)*1000, r
    h = asyncio.create_task(hog())
    await asyncio.sleep(0.001)
    results = await asyncio.gather(*[small() for _ in range(20)])
    hr = await h
    lats=[r[0] for r in results]
    print(f"small requests DURING a 360KB scan   p50={statistics.median(lats):6.2f}ms  "
          f"p95={sorted(lats)[18]:6.2f}ms  max={max(lats):6.2f}ms")
    print(f"   -> head-of-line penalty: {statistics.median(lats)/base:.1f}x")
    print(f"   huge request: {hr.latency_ms:.1f}ms degraded={hr.degraded} verdict={hr.verdict}")

    # parallel load
    print()
    for conc in (1,4,16,64):
        t=time.perf_counter()
        rs = await asyncio.gather(*[ck.check(tree_of(SMALL),"t") for _ in range(conc)])
        wall=(time.perf_counter()-t)*1000
        p95=sorted(r.latency_ms for r in rs)[max(0,int(conc*0.95)-1)]
        print(f"concurrency={conc:>3}  wall={wall:8.2f}ms  per-req p95={p95:7.2f}ms  "
              f"degraded={sum(1 for r in rs if r.degraded)}/{conc}")

asyncio.run(main())
