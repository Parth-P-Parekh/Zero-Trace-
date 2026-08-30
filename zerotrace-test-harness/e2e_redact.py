"""Full outbound path: detect -> decide -> redact -> verify_dispatch, with adversarial payloads."""
import sys, json, asyncio; sys.path.insert(0,'/root/ztest'); sys.path.insert(0,'/root/zt')
from lib import *
from gateway.redact import plan_redaction, apply_redaction, verify_dispatch, DispatchVerificationError
from gateway.contracts.types import Decision, Action
import inspect
print(inspect.signature(plan_redaction))

A="718190937865"
CASES = {
 "two people, many records": {"messages":[{"role":"user","content":
    " ; ".join(f"Citizen {i}: Aadhaar {A}, name Person{i}, pincode 5601{i:02d}" for i in range(3))}]},
 "same value three places": {"messages":[
    {"role":"user","content":"look up PAN ABCPZ1234C"},
    {"role":"user","content":[{"type":"tool_result","tool_use_id":"t","content":json.dumps({"pan":"ABCPZ1234C"})}]},
    {"role":"user","content":"is ABCPZ1234C the same person?"}]},
 "unicode heavy": {"messages":[{"role":"user","content":"नाम: राजेश — PAN ABCPZ1234C — 🎉 done"}]},
}

async def main():
    ck = make_checker(cache=NullSpanCache())
    for name, payload in CASES.items():
        tree = tree_of(payload)
        r = await ck.check(tree, "t1")
        dec = Decision(action=Action.TOKENIZE, rule_index=0, policy_version=1)
        plan = plan_redaction(tree, list(r.findings), dec, tenant_key=b"k"*32, scope_key="sess1")
        body = apply_redaction(tree, plan)
        try:
            verify_dispatch(body, plan); vd="OK"
        except DispatchVerificationError as e: vd=f"FAIL: {e}"
        # independent check: is the original literal really gone?
        leaked=[]
        for red in plan.redactions:
            if red._original.encode() in body: leaked.append(red._original)
        # round trip parse
        try: json.loads(body); parses="parses"
        except Exception as e: parses=f"BROKEN JSON: {e}"
        toks = sorted({p.replacement for p in plan.redactions})
        print(f"\n--- {name}")
        print(f"    findings={len(r.findings)} redactions={len(plan.redactions)} verify={vd} {parses}")
        print(f"    tokens={toks}")
        print(f"    leaked originals in dispatched body: {leaked or 'NONE'}")
        if name=="same value three places":
            print(f"    referential stability: {'STABLE' if len(toks)==1 else '!! UNSTABLE '+str(toks)}")

asyncio.run(main())
