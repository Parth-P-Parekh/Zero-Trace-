"""Same actor, same prompt, two enforcement paths."""
import sys, os, json, subprocess, tempfile; sys.path.insert(0,'/root/zt')
h=tempfile.mkdtemp(prefix="zt2p-")
env={**os.environ, "ZT_HOME":h, "ZT_LEDGER_DIR":h+"/ledger", "ZT_REDIS_URL":"",
     "ZT_PART_A":"1", "ZT_FAIL":"closed", "ZT_NO_DAEMON":"1", "PYTHONPATH":"/root/zt"}
PAN="ABCPZ1234C"
TEXT=f"look up customer record {PAN}"

SEED="""
import asyncio,sys; sys.path.insert(0,'/root/zt')
from gateway.part_a.session import login, plane
from gateway.part_a.wiring import seed_demo, DEMO_TENANT
asyncio.run(seed_demo(plane())); login("s.iyer", DEMO_TENANT)
print("logged in as s.iyer (citizen-services)")
"""
print(subprocess.run([sys.executable,"-c",SEED],env=env,capture_output=True,text=True).stdout.strip())

# --- path 1: the Claude Code hook
hook = subprocess.run([sys.executable, "/root/zt/hooks/zt_check.py"], env=env,
    input=json.dumps({"prompt":TEXT,"session_id":"s1","cwd":"/tmp"}),
    capture_output=True, text=True)
print(f"\nPATH 1  hook (Claude Code)   rc={hook.returncode}  "
      f"{'ALLOWED' if hook.returncode==0 else 'DENIED'}  {hook.stdout.strip()[:90]}{hook.stderr.strip()[:90]}")

# --- path 2: HTTP (browser extension / /v1/messages)
P2="""
import sys,os,json,asyncio; sys.path.insert(0,'/root/zt')
from fastapi.testclient import TestClient
from gateway.app import create_app
from gateway.part_a.wiring import seed_demo
app=create_app()
with TestClient(app) as c:
    asyncio.new_event_loop().run_until_complete(seed_demo(app.state.part_a))
    r=c.post("/v1/prompt/check", json={"text":%r,"session_id":"s1"},
             headers={"x-zerotrace-actor":"s.iyer","x-zerotrace-tenant":"bharat-digital"})
    b=r.json(); print("ALLOWED" if b.get("allow") else "DENIED", b.get("classes"), str(b.get("reason"))[:70])
""" % TEXT
p2=subprocess.run([sys.executable,"-c",P2],env=env,capture_output=True,text=True)
print(f"PATH 2  HTTP (extension)     {p2.stdout.strip().splitlines()[-1] if p2.stdout.strip() else p2.stderr.strip()[-200:]}")
