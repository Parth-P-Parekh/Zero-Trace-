"""Independent privacy-invariant sweep: does any sensitive literal reach any store/log?"""
import sys, os, json, glob, tempfile, io, logging
sys.path.insert(0,'/root/zt')
os.environ["ZT_FAIL"]="closed"; os.environ["ZT_PART_A"]="1"; os.environ["ZT_REDIS_URL"]=""
home=tempfile.mkdtemp(prefix="ztpriv-"); os.environ["ZT_HOME"]=home; os.environ["ZT_LEDGER_DIR"]=home+"/ledger"
LOG=io.StringIO(); logging.basicConfig(stream=LOG, level=logging.DEBUG, force=True)
from fastapi.testclient import TestClient
from gateway.app import create_app
A="718190937865"
SECRETS={"aadhaar":A,"pan":"ABCPZ1234C","key":"sk-ant-api03-"+"Z"*30+"QQQQ",
         "dsn":"postgres://svc:Pr0dRunb00k@10.0.4.11:5432/revenue",
         "pw":"Pr0dRunb00k!2026","aws":"AKIAIOSFODNN7EXAMPLE"}
app=create_app()
with TestClient(app) as c:
    for k,v in SECRETS.items():
        c.post("/v1/prompt/check", json={"text":f"context {k}: {v}", "session_id":"s1"})
        c.post("/v1/messages", json={"model":"m","messages":[{"role":"user","content":v}]})
# sweep everything on disk under ZT_HOME + captured logs
blobs={}
for p in glob.glob(os.path.join(home,"**","*"), recursive=True):
    if os.path.isfile(p):
        try: blobs[p]=open(p,'rb').read().decode('utf-8','replace')
        except Exception: pass
blobs["<captured logs>"]=LOG.getvalue()
print(f"scanned {len(blobs)} artefacts under {home}")
bad=[]
for name,txt in blobs.items():
    for k,v in SECRETS.items():
        if v in txt: bad.append((name,k))
print("FILES:", [os.path.relpath(p,home) for p in blobs if p!="<captured logs>"][:20])
if bad:
    print("!! LEAKS FOUND:")
    for n,k in bad: print("   ",k,"in",n)
else:
    print("PRIVACY INVARIANT HOLDS: no sensitive literal in any store or log")
