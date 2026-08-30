import sys, os, json; sys.path.insert(0,'/root/zt')
os.environ["ZT_FAIL"]="closed"; os.environ["ZT_PART_A"]="0"
from fastapi.testclient import TestClient
from gateway.app import create_app
A="718190937865"
app=create_app()
with TestClient(app) as c:
    print("healthz:", c.get("/healthz").status_code)
    tests = {
      "clean":           "please refactor this function",
      "anthropic key":   "my key is sk-ant-api03-"+"A"*30+"BBBB",
      "aadhaar+pincode": f"Citizen: Aadhaar {A}, pincode 560100",
      "aadhaar+pan":     f"Aadhaar {A} and PAN ABCPZ1234C",
      "db runbook":      "export DB_PASSWORD=Pr0dRunb00k!2026",
      "huge":            "x"*400_000,
    }
    for n,t in tests.items():
        r=c.post("/v1/prompt/check", json={"text":t,"session_id":"s1"})
        try: b=r.json()
        except Exception: b=r.text[:200]
        print(f"{n:18} HTTP {r.status_code}  allow={b.get('allow') if isinstance(b,dict) else '?'} "
              f"classes={b.get('classes') if isinstance(b,dict) else ''} "
              f"lat={b.get('latency_ms') if isinstance(b,dict) else ''} deg={b.get('degraded') if isinstance(b,dict) else ''}")
    print()
    # the messages path (redaction path)
    for n,t in [("aadhaar+pan msg", f"Aadhaar {A} and PAN ABCPZ1234C")]:
        r=c.post("/v1/messages", json={"model":"claude-3","messages":[{"role":"user","content":t}]})
        print(f"{n:18} HTTP {r.status_code}  body={r.text[:300]}")
