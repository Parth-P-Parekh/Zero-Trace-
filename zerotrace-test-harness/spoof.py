"""Privilege escalation over HTTP headers, with Part A on."""
import sys, os, json, tempfile; sys.path.insert(0,'/root/zt')
h=tempfile.mkdtemp(prefix="ztspoof-")
os.environ.update(ZT_HOME=h, ZT_LEDGER_DIR=h+"/ledger", ZT_REDIS_URL="",
                  ZT_PART_A="1", ZT_FAIL="closed", ZT_NO_DAEMON="1")
from fastapi.testclient import TestClient
from gateway.app import create_app
import asyncio
from gateway.part_a.session import plane
from gateway.part_a.wiring import seed_demo
asyncio.get_event_loop_policy().new_event_loop().run_until_complete(seed_demo(plane()))

A="718190937865"
PROMPT=f"Citizen record: Aadhaar {A}, pincode 560103"
app=create_app()
with TestClient(app) as c:
    def go(label, headers):
        r=c.post("/v1/prompt/check", json={"text":PROMPT,"session_id":"s"}, headers=headers)
        b=r.json()
        return f"{label:46} allow={str(b.get('allow')):5} classes={b.get('classes')} reason={str(b.get('reason'))[:44]}"
    print("=== the same citizen prompt, different asserted identities ===")
    print(go("no headers (anonymous)", {}))
    print(go("claims to be vendor.dev (contractor)", {"x-zerotrace-actor":"vendor.dev","x-zerotrace-tenant":"bharat-digital-contractors"}))
    print(go("claims to be s.iyer (citizen-services)", {"x-zerotrace-actor":"s.iyer","x-zerotrace-tenant":"bharat-digital"}))
    print(go("claims to be p.rao (director)", {"x-zerotrace-actor":"p.rao","x-zerotrace-tenant":"bharat-digital"}))
    print(go("INVENTED actor 'ceo.god'", {"x-zerotrace-actor":"ceo.god","x-zerotrace-tenant":"bharat-digital"}))
    print(go("self-asserted groups header", {"x-zerotrace-actor":"vendor.dev","x-zerotrace-groups":"citizen-services,revenue,hr-personnel,infosec"}))
    print(go("INVENTED tenant 'my-own-tenant'", {"x-zerotrace-actor":"x","x-zerotrace-tenant":"my-own-tenant"}))
    print()
    print("=== does a credential survive any identity? ===")
    for hdr,lbl in [({}, "anonymous"), ({"x-zerotrace-actor":"p.rao","x-zerotrace-tenant":"bharat-digital"},"director"),
                    ({"x-zerotrace-groups":"infosec"},"claims infosec group")]:
        r=c.post("/v1/prompt/check", json={"text":"key sk-ant-api03-"+"A"*30+"BBBB"}, headers=hdr)
        print(f"  {lbl:22} allow={r.json().get('allow')} classes={r.json().get('classes')}")
