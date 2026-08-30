"""N users in one tenant, hitting the real app concurrently."""
import sys, os, json, time, statistics, tempfile, threading; sys.path.insert(0,'/root/zt')
h=tempfile.mkdtemp(prefix="ztmany-")
os.environ.update(ZT_HOME=h, ZT_LEDGER_DIR=h+"/ledger", ZT_REDIS_URL="", ZT_PART_A="0",
                  ZT_FAIL="closed", ZT_NO_DAEMON="1")
from fastapi.testclient import TestClient
from gateway.app import create_app

CODE=open('/root/zt/gateway/base/scanner.py').read()
PROMPT="please review this and suggest improvements\n"+CODE[:1500]
BIG=("turn: "+CODE[:1200]+"\n")*30  # ~a 30-turn Claude Code transcript

app=create_app()
with TestClient(app) as c:
    def one(actor, TEXT=PROMPT):
        t=time.perf_counter()
        r=c.post("/v1/prompt/check", json={"text":TEXT,"session_id":f"s-{actor}"},
                 headers={"x-zerotrace-actor":f"user{actor}","x-zerotrace-tenant":"acme"})
        return (time.perf_counter()-t)*1000, r.status_code, r.json()
    # warm
    one(0)
    print(f"{'users':>6} {'wall':>9} {'p50':>8} {'p95':>8} {'max':>8}  degraded  blocked")
    for n in (1,2,4,8,16,32,64):
        out=[]; lock=threading.Lock()
        def work(i):
            r=one(i)
            with lock: out.append(r)
        t0=time.perf_counter()
        ts=[threading.Thread(target=work,args=(i,)) for i in range(n)]
        [t.start() for t in ts]; [t.join() for t in ts]
        wall=(time.perf_counter()-t0)*1000
        lats=sorted(x[0] for x in out)
        deg=sum(1 for x in out if x[2].get("degraded"))
        blocked=sum(1 for x in out if not x[2].get("allow"))
        print(f"{n:>6} {wall:8.1f}ms {lats[len(lats)//2]:7.1f}ms "
              f"{lats[max(0,int(n*0.95)-1)]:7.1f}ms {lats[-1]:7.1f}ms  "
              f"{deg:>5}/{n}  {blocked:>5}/{n}" + ("   <<< false blocks" if blocked else ""))

    print("\n=== same, but each user sends a ~36KB Claude Code transcript ===")
    print(f"{'users':>6} {'wall':>9} {'p50':>8} {'p95':>8} {'max':>8}  degraded  blocked")
    for n in (1,4,16,32,64):
        out=[]; lock=threading.Lock()
        def work(i):
            r=one(i, BIG)
            with lock: out.append(r)
        t0=time.perf_counter()
        ts=[threading.Thread(target=work,args=(i,)) for i in range(n)]
        [t.start() for t in ts]; [t.join() for t in ts]
        wall=(time.perf_counter()-t0)*1000
        lats=sorted(x[0] for x in out)
        deg=sum(1 for x in out if x[2].get("degraded"))
        blocked=sum(1 for x in out if not x[2].get("allow"))
        print(f"{n:>6} {wall:8.1f}ms {lats[len(lats)//2]:7.1f}ms "
              f"{lats[max(0,int(n*0.95)-1)]:7.1f}ms {lats[-1]:7.1f}ms  "
              f"{deg:>5}/{n}  {blocked:>5}/{n}" + ("   <<< FALSE BLOCKS" if blocked else ""))
