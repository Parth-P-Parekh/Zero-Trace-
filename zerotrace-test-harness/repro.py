import sys, json, asyncio; sys.path.insert(0,'/root/ztest'); sys.path.insert(0,'/root/zt')
from lib import *
from gateway.redact import plan_redaction, apply_redaction
from gateway.contracts.types import Decision, Action
A="718190937865"
PAYLOADS = {
 "1 record":  f"Citizen 0: Aadhaar {A}, name Person0, pincode 560100",
 "2 records": f"Citizen 0: Aadhaar {A}, pincode 560100 ; Citizen 1: Aadhaar {A}, pincode 560101",
 "aadhaar+pan":"Aadhaar "+A+" and PAN ABCPZ1234C",
 "just aadhaar": A,
}
async def m():
    ck=make_checker(cache=NullSpanCache())
    for name,txt in PAYLOADS.items():
        tree=tree_of({"messages":[{"role":"user","content":txt}]})
        r=await ck.check(tree,"t")
        fs=[(f.entity_class.value,f.start,f.end,f.detector_name) for f in r.findings]
        dec=Decision(action=Action.TOKENIZE, rule_index=0, policy_version=1)
        plan=plan_redaction(tree,list(r.findings),dec,tenant_key=b"k"*32,scope_key="s")
        try:
            body=apply_redaction(tree,plan); out="OK  "+json.loads(body)["messages"][0]["content"][:70]
        except Exception as e: out=f"CRASH {type(e).__name__}: {e}"
        print(f"\n{name}\n  findings={fs}\n  redactions={len(plan.redactions)}\n  {out}")
asyncio.run(m())
