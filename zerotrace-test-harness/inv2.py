import sys, os, asyncio, json, secrets; sys.path.insert(0,'/root/ztest'); sys.path.insert(0,'/root/zt')
from lib import *
from gateway.vault.derive import derive_token, CredentialNeverTokenized
from gateway.contracts.entity_classes import EntityClass
K=b"k"*32
print("=== token determinism / scope ===")
a=derive_token(K,"sess1",EntityClass.PAN,"ABCPZ1234C")
b=derive_token(K,"sess1",EntityClass.PAN,"ABCPZ1234C")
c=derive_token(K,"sess2",EntityClass.PAN,"ABCPZ1234C")
print(" same scope  :", a, b, "STABLE" if a==b else "!! UNSTABLE")
print(" other scope :", c, "DIFFERENT" if a!=c else "!! SAME ACROSS SCOPES")
print(" case/space  :", derive_token(K,"s",EntityClass.PAN," abcpz1234c "), "vs", derive_token(K,"s",EntityClass.PAN,"ABCPZ1234C"))
try:
    derive_token(K,"s",EntityClass.ANTHROPIC_KEY,"sk-ant-x"); print(" !! credential tokenised")
except CredentialNeverTokenized: print(" credential tokenisation refused: OK")
print(" no undo_token in module:", not hasattr(sys.modules['gateway.vault.derive'],'undo_token'))

print("\n=== brute-force resistance of a small domain ===")
# 10-digit phone: can an attacker with the tenant key + a token recover the original?
import time, itertools
target = derive_token(K,"s",EntityClass.PAN,"ABCPZ1234C")
t=time.perf_counter(); tried=0
# PAN space is ~ 26^5 * 10^4 * 26 -- sample only, measure rate
import random
random.seed(1)
while time.perf_counter()-t < 2.0:
    v = "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(5))+ \
        "".join(random.choice("0123456789") for _ in range(4))+random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    tried+=1
    if derive_token(K,"s",EntityClass.PAN,v)==target: print("  FOUND", v); break
rate=tried/2.0
print(f"  derivations/sec (pure python): {rate:,.0f}")
for name, space in [("PHONE 10-digit (India, 6-9 lead)", 4*10**9),
                    ("PAN", 26**5*10**4*26), ("AADHAAR (Verhoeff-valid)", 8*10**10)]:
    print(f"  {name:34} space={space:>18,}  exhaustive at this rate = {space/rate/86400:,.1f} days (1 core)")
