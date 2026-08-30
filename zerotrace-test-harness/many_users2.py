"""N *different* users, each with their own unique transcript (no cross-user cache reuse)."""
import sys, os, time, tempfile, threading, statistics; sys.path.insert(0,'/root/zt')
h=tempfile.mkdtemp(prefix="ztmany2-")
os.environ.update(ZT_HOME=h, ZT_LEDGER_DIR=h+"/ledger", ZT_REDIS_URL="", ZT_PART_A="0",
                  ZT_FAIL="closed", ZT_NO_DAEMON="1")
from fastapi.testclient import TestClient
from gateway.app import create_app
CODE=open('/root/zt/gateway/base/scanner.py').read()
def payload_for(u):           # unique per user -> no shared cache entries
    return "".join(f"user{u} turn{i}: {CODE[i*40:(i*40)+1200]}\n" for i in range(30))
app=create_app()
with TestClient(app) as c:
    c.post("/v1/prompt/check", json={"text":"warm"})
    print(f"{'users':>6} {'wall':>10} {'p50':>9} {'p95':>9} {'max':>9}  degraded  blocked")
    for n in (1,4,16,32,64):
        out=[]; lock=threading.Lock()
        def work(i):
            t=time.perf_counter()
            r=c.post("/v1/prompt/check", json={"text":payload_for(i),"session_id":f"s{i}"},
                     headers={"x-zerotrace-actor":f"user{i}","x-zerotrace-tenant":"acme"})
            with lock: out.append(((time.perf_counter()-t)*1000, r.json()))
        t0=time.perf_counter()
        ts=[threading.Thread(target=work,args=(i,)) for i in range(n)]
        [t.start() for t in ts]; [t.join() for t in ts]
        wall=(time.perf_counter()-t0)*1000
        lats=sorted(x[0] for x in out)
        deg=sum(1 for x in out if x[1].get("degraded"))
        blk=sum(1 for x in out if not x[1].get("allow"))
        print(f"{n:>6} {wall:9.1f}ms {lats[len(lats)//2]:8.1f}ms {lats[max(0,int(n*0.95)-1)]:8.1f}ms "
              f"{lats[-1]:8.1f}ms  {deg:>5}/{n}  {blk:>5}/{n}"
              + ("   <<< FALSE BLOCKS" if blk else ""))
