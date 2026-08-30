import sys, random, string; sys.path.insert(0,'/root/zt')
from gateway.vault.derive import derive_token, format_token
from gateway.contracts.entity_classes import EntityClass
K=b"k"*32
print("token width:", len(derive_token(K,"s",EntityClass.PERSON,"x")), "->", derive_token(K,"s",EntityClass.PERSON,"x"))
random.seed(3)
names=[f"{random.choice(['Priya','Rajesh','Meena','Amit','Sunita','Vikram'])} "
       f"{random.choice(['Sharma','Kumar','Iyer','Das','Rao','Khan'])}{i}" for i in range(2000)]
seen={}; first=None; collisions=0
for i,n in enumerate(names,1):
    t=derive_token(K,"sess1",EntityClass.PERSON,n)
    if t in seen:
        collisions+=1
        if first is None: first=(i,n,seen[t],t)
    else: seen[t]=n
print(f"distinct values hashed : {len(names)}")
print(f"distinct tokens        : {len(seen)}")
print(f"COLLISIONS             : {collisions}")
if first: print(f"first collision at value #{first[0]}: {first[1]!r} and {first[2]!r} both -> {first[3]}")
import math
space=32**3
print(f"\ntoken space = 32^3 = {space:,}  (3 base32 chars)")
print(f"50% collision probability at ~{int(math.sqrt(2*space*math.log(2)))} distinct values in one scope")
