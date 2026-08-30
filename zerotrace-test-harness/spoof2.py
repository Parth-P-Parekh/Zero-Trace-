"""Part A gated path: seed inside the app's own loop, then spoof."""
import sys, os, json, tempfile; sys.path.insert(0,'/root/zt')
h=tempfile.mkdtemp(prefix="ztspoof2-")
os.environ.update(ZT_HOME=h, ZT_LEDGER_DIR=h+"/ledger", ZT_REDIS_URL="",
                  ZT_PART_A="1", ZT_FAIL="closed", ZT_NO_DAEMON="1")
from fastapi.testclient import TestClient
from gateway.app import create_app
app=create_app()
A="718190937865"
with TestClient(app) as c:
    # seed through the running app's own plane
    import anyio
    from gateway.part_a.wiring import seed_demo
    pl = app.state.part_a
    anyio.from_thread  # noqa
    import asyncio
    loop = asyncio.new_event_loop()
    loop.run_until_complete(seed_demo(pl))
    def go(label, hdr, text=f"Citizen: Aadhaar {A}, pincode 560103"):
        r=c.post("/v1/messages", json={"model":"claude-3","messages":[{"role":"user","content":text}]}, headers=hdr)
        try: b=r.json()
        except Exception: b={}
        err = b.get("error",{}).get("type") if isinstance(b.get("error"),dict) else None
        txt = ""
        if isinstance(b.get("content"),list) and b["content"]: txt=b["content"][0].get("text","")[:60]
        return f"{label:44} HTTP {r.status_code}  err={err}  {txt}"
    print("=== /v1/messages with Part A on ===")
    print(go("no headers", {}))
    print(go("actor=vendor.dev tenant=...contractors", {"x-zerotrace-actor":"vendor.dev","x-zerotrace-tenant":"bharat-digital-contractors"}))
    print(go("actor=s.iyer tenant=bharat-digital", {"x-zerotrace-actor":"s.iyer","x-zerotrace-tenant":"bharat-digital"}))
    print(go("actor=p.rao (director)", {"x-zerotrace-actor":"p.rao","x-zerotrace-tenant":"bharat-digital"}))
    print(go("INVENTED actor 'ceo.god'", {"x-zerotrace-actor":"ceo.god","x-zerotrace-tenant":"bharat-digital"}))
    print(go("INVENTED tenant", {"x-zerotrace-actor":"x","x-zerotrace-tenant":"nope-inc"}))
    print()
    print("=== ordinary prompt, same identities (does clearance let it through?) ===")
    for lbl,hdr in [("s.iyer (citizen-services)",{"x-zerotrace-actor":"s.iyer","x-zerotrace-tenant":"bharat-digital"}),
                    ("vendor.dev",{"x-zerotrace-actor":"vendor.dev","x-zerotrace-tenant":"bharat-digital-contractors"})]:
        print(" ", go(lbl,hdr))
