"""Dummy RAG + inbound clearance, end to end, across every seeded actor."""
import sys, os, asyncio, tempfile
sys.path.insert(0,'/root/zt'); sys.path.insert(0,'/root/ztest/rag')
os.environ["ZT_HOME"] = tempfile.mkdtemp(prefix="ztrag-")
os.environ["ZT_REDIS_URL"] = ""
os.environ["ZT_NO_DAEMON"] = "1"
from corpus import retrieve
from gateway.part_a.session import plane
from gateway.part_a.wiring import DEMO_TENANT, DEMO_ACTORS, seed_demo
from gateway.part_a.retrieval import RetrievalGuard

QUERY = "salary aadhaar patient credentials records"

async def main():
    pl = plane()
    await seed_demo(pl)
    ctx = await pl.context() if hasattr(pl,'context') else pl
    docs = retrieve(QUERY)
    print(f"retriever returned {len(docs)} docs for: {QUERY!r}\n")
    guard = RetrievalGuard(ctx)
    for actor_id,(role,groups) in DEMO_ACTORS.items():
        actor = await pl.store.get_actor(
            "bharat-digital-contractors" if role=="contractor" else DEMO_TENANT, actor_id)
        res = await guard.filter(docs, actor)
        vis = [d["id"] for d in res.visible]
        wh  = [(v.document_id, ",".join(v.classes), v.action) for v in res.withheld]
        print(f"--- {actor_id:11} role={role:10} groups={groups}")
        print(f"    visible ({len(vis)}): {vis}")
        for d,c,a in wh: print(f"    withheld: {d:24} {c:28} -> {a}")
        # leak check: does the explanation contain any document body?
        exp = res.explain()
        leaked = [d["id"] for d in docs if d["text"][:40] in exp]
        if leaked: print("    !! EXPLANATION LEAKS CONTENT:", leaked)
        print()

asyncio.run(main())
