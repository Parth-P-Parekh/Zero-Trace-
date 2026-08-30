import sys, asyncio, json, random, statistics, time; sys.path.insert(0,'/root/ztest')
from lib import *
random.seed(11)

CODE = open('/root/zt/gateway/base/scanner.py').read()

def turn(i, big=False):
    body = CODE[: (8000 if big else 900)]
    return [
      {"role":"user","content":f"turn {i}: please refactor the scanner, here is context\n{body[:400]}"},
      {"role":"assistant","content":[{"type":"tool_use","id":f"t{i}","name":"Read","input":{"file_path":"gateway/base/scanner.py"}}]},
      {"role":"user","content":[{"type":"tool_result","tool_use_id":f"t{i}","content":body}]},
    ]

def convo(n, big=False):
    m=[]
    for i in range(n): m += turn(i, big)
    return {"model":"claude-x","system":"You are a coding agent."*20,"messages":m}

async def run(label, payload, cache, repeats=5):
    ck = make_checker(cache=cache, ceiling=50.0)
    lat=[]; res=None
    for _ in range(repeats):
        t=time.perf_counter(); res=await check(ck,payload); lat.append((time.perf_counter()-t)*1000)
    raw=len(json.dumps(payload))
    print(f"{label:38} bytes={raw:>8}  spans={len(tree_of(payload)):>4}  "
          f"p50={statistics.median(lat):7.2f}ms  max={max(lat):7.2f}ms  "
          f"hits={res.cache_hits} miss={res.cache_misses} degraded={res.degraded}")
    return statistics.median(lat)

async def main():
    print("=== COLD CACHE (first request of a session) ===")
    for n in (1,5,10,20,30):
        await run(f"cold {n:>2}-turn transcript", convo(n), NullSpanCache(), repeats=3)
    await run("cold 30-turn BIG tool results", convo(30,big=True), NullSpanCache(), repeats=3)

    print("\n=== WARM CACHE (turn N of a growing session) ===")
    cache = InMemorySpanCache()
    ck = make_checker(cache=cache, ceiling=50.0)
    for n in (1,5,10,20,30,50):
        p = convo(n)
        t=time.perf_counter(); r=await ck.check(tree_of(p),"t1"); ms=(time.perf_counter()-t)*1000
        print(f"warm turn {n:>3}   bytes={len(json.dumps(p)):>8}  {ms:7.2f}ms  "
              f"hits={r.cache_hits} miss={r.cache_misses} ratio={r.cache_hits/max(1,r.cache_hits+r.cache_misses):.0%} degraded={r.degraded}")

    print("\n=== BUDGET VERDICT ===")
    cold30 = await run("cold 30-turn (repeat for verdict)", convo(30), NullSpanCache(), repeats=5)
    print(f"claim: green path p95 < 10ms | measured cold p50 = {cold30:.2f}ms -> "
          + ("PASS" if cold30 < 10 else "FAIL"))

asyncio.run(main())
