"""Two users on one host: does the login file bleed between them?"""
import sys, os, json, subprocess, tempfile; sys.path.insert(0,'/root/zt')
h=tempfile.mkdtemp(prefix="ztshared-")
base={**os.environ,"ZT_HOME":h,"ZT_LEDGER_DIR":h+"/ledger","ZT_REDIS_URL":"",
      "ZT_PART_A":"1","ZT_FAIL":"closed","ZT_NO_DAEMON":"1","PYTHONPATH":"/root/zt"}
PAN="ABCPZ1234C"; TEXT=f"look up customer record {PAN}"
def run(code, env=base):
    return subprocess.run([sys.executable,"-c",code],env=env,capture_output=True,text=True)
def hook(env=base):
    r=subprocess.run([sys.executable,"/root/zt/hooks/zt_check.py"],env=env,
        input=json.dumps({"prompt":TEXT,"session_id":"s","cwd":"/tmp"}),capture_output=True,text=True)
    return "ALLOWED" if r.returncode==0 else "DENIED"

run("""
import asyncio,sys; sys.path.insert(0,'/root/zt')
from gateway.part_a.session import plane; from gateway.part_a.wiring import seed_demo
asyncio.run(seed_demo(plane()))""")

print("ZT_HOME =", h, "(the default is ~/.zerotrace -- one path per OS user)\n")
run("""
import sys; sys.path.insert(0,'/root/zt')
from gateway.part_a.session import login
from gateway.part_a.wiring import DEMO_TENANT
login("s.iyer", DEMO_TENANT)""")
print("alice runs `zerotrace login s.iyer` (citizen-services)")
print("  alice sends the citizen prompt      ->", hook())
print("  BOB, same host, same ZT_HOME, sends ->", hook(), " <- bob inherits alice's clearance")
print("  session.json contents:", open(os.path.join(h,"session.json")).read().strip())
print("  file mode:", oct(os.stat(os.path.join(h,"session.json")).st_mode & 0o777))
print()
# does anything bind the session to the OS user or to a credential?
print("bob overrides nothing -- there is no per-user key, token or password in the file.")
print("bob can also just write it himself:")
open(os.path.join(h,"session.json"),"w").write(json.dumps({"tenant":"bharat-digital","actor":"p.rao"}))
print("  after `echo '{...p.rao...}' > session.json` ->", hook(), "as the director")
