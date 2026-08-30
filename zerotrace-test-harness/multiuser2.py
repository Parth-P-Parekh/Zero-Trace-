"""Does the cache leak DECISIONS across actors? (SKEL-01 §B.5 rule 1)"""
import sys, os, asyncio, tempfile; sys.path.insert(0,'/root/zt')
os.environ["ZT_HOME"]=tempfile.mkdtemp(prefix="ztmu-"); os.environ["ZT_REDIS_URL"]=""
os.environ["ZT_NO_DAEMON"]="1"
sys.path.insert(0,'/root/ztest/rag')
from corpus import DOCS
from gateway.part_a.session import plane
from gateway.part_a.wiring import DEMO_TENANT, DEMO_ACTORS, seed_demo
from gateway.part_a.retrieval import RetrievalGuard

PAYSLIP=[d for d in DOCS if d["id"]=="doc-payslip-rkumar"]

async def main():
    pl=plane(); await seed_demo(pl); ctx=await pl.context()
    guard=RetrievalGuard(ctx)
    print("Same document, warm caches, actors interleaved (hr-personnel is cleared, others are not):")
    order=["m.khan","s.iyer","m.khan","cag.audit","m.khan","vendor.dev","m.khan"]
    for actor_id in order:
        role,groups=DEMO_ACTORS[actor_id]
        t="bharat-digital-contractors" if role=="contractor" else DEMO_TENANT
        actor=await pl.store.get_actor(t,actor_id)
        r=await guard.filter(PAYSLIP,actor)
        got = "VISIBLE" if r.visible else f"withheld({r.withheld[0].action})"
        flag=""
        if actor_id!="m.khan" and r.visible: flag="   <<< LEAK: uncleared actor saw it"
        print(f"  {actor_id:11} groups={str(groups):22} -> {got}{flag}")

    print("\nSame check run 200x alternating cleared/uncleared, looking for any inherited decision:")
    leaks=0
    cleared=await pl.store.get_actor(DEMO_TENANT,"m.khan")
    unclear=await pl.store.get_actor(DEMO_TENANT,"cag.audit")
    for i in range(200):
        a = cleared if i%2==0 else unclear
        r = await guard.filter(PAYSLIP,a)
        vis = bool(r.visible)
        if (i%2==0) != vis: leaks+=1
    print(f"  mismatches in 200 interleaved decisions: {leaks}  "
          f"({'PASS - decisions are recomputed per actor' if leaks==0 else '!! FAIL'})")
asyncio.run(main())
