import sys, os, json, tempfile; sys.path.insert(0,'/root/zt')
# 1. ledger tamper detection
from gateway.ledger.chain import Ledger, JsonlLedgerStore, LedgerTampering
d=tempfile.mkdtemp(); st=JsonlLedgerStore(d); lg=Ledger(st)
import asyncio
async def go():
    for i in range(5): await lg.append("t","e",{"i":i})
asyncio.run(go())
p=os.path.join(d,"t.jsonl"); lines=open(p).read().splitlines()
print("=== ledger ===")
try: lg.verify("t"); print(" clean chain verifies: OK")
except Exception as e: print(" clean chain FAILED:", e)
rec=json.loads(lines[2]); rec["payload"]["i"]=999; lines[2]=json.dumps(rec)
open(p,"w").write("\n".join(lines)+"\n")
try: lg.verify("t"); print(" !! TAMPERED chain still verifies -- BROKEN")
except LedgerTampering as e: print(" tampered chain rejected: OK")
except Exception as e: print(" tampered chain raised:", type(e).__name__)
# truncation
lines2=lines[:3]; open(p,"w").write("\n".join(lines2)+"\n")
try: lg.verify("t"); print(" !! TRUNCATED chain verifies (no anchor) -- expected weakness")
except Exception as e: print(" truncated chain rejected:", type(e).__name__)

# 2. escalation blindness
print("\n=== escalation features ===")
from gateway.intel.features import EscalationFeatures
import dataclasses
fields = [f.name for f in dataclasses.fields(EscalationFeatures)] if dataclasses.is_dataclass(EscalationFeatures) else list(EscalationFeatures.__annotations__)
print(" fields:", fields)
types = {f.name: str(f.type) for f in dataclasses.fields(EscalationFeatures)} if dataclasses.is_dataclass(EscalationFeatures) else {}
freetext=[k for k,v in types.items() if v=="str" and k in ("text","span_text","value","content","raw")]
print(" free-text field present:", freetext or "NONE -> blindness enforced structurally")
