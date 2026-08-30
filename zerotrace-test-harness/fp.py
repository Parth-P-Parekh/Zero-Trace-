"""False-positive sweep over ordinary developer material."""
import sys, asyncio, json, pathlib, subprocess; sys.path.insert(0,'/root/ztest')
from lib import *

samples = []
for p in list(pathlib.Path('/root/zt/gateway').rglob('*.py'))[:60]:
    samples.append((str(p.relative_to('/root/zt')), p.read_text(errors='ignore')[:4000]))
# plus common non-secret strings a coding agent handles constantly
EXTRA = [
 ("git sha",        "commit 9f2b1c4e8a7d6f5b3c2a1e0d9f8b7a6c5d4e3f21"),
 ("uuid",           "id: 550e8400-e29b-41d4-a716-446655440000"),
 ("base64 png",     "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="),
 ("npm integrity",  'sha512-Xz9kL2mPq8vRt4Yw6Bn1Cd3Ef5Gh7Ij9Kl0Mn2Op4Qr6St8Uv0Wx2Yz4Ab6Cd8Ef0Gh==' ),
 ("jwt in test",    "expected = 'eyJhbGciOiJub25lIn0.eyJhIjoxfQ.'"),
 ("docker digest",  "image@sha256:3f8a1b9c0d2e4f6a8b0c1d3e5f7a9b1c3d5e7f9a1b3c5d7e9f1a3b5c7d9e1f3a"),
 ("test aadhaar-ish","assert luhn('4111111111111111') is True"),
 ("lorem numbers",  "for i in range(123456789012): pass"),
 ("env var name",   "os.getenv('DB_PASSWORD')"),
 ("password prompt","print('Enter your password:')"),
 ("k8s secret ref", "valueFrom: {secretKeyRef: {name: db, key: password}}"),
]

async def main():
    ck = make_checker(cache=NullSpanCache())
    fp_files = []
    for name, text in samples:
        r = await check(ck, {"messages":[{"role":"user","content":text}]})
        enf = [f for f in r.findings if not f.advisory_only]
        if enf:
            fp_files.append((name, sorted({(f.entity_class, round(f.confidence,2), f.detector_name) for f in enf})))
    print(f"=== OWN SOURCE FILES: {len(fp_files)}/{len(samples)} flagged RED/AMBER ===")
    for n, c in fp_files[:15]: print(f"  {n:48} {c}")
    print()
    print("=== COMMON DEV STRINGS ===")
    for n, t in EXTRA:
        r = await check(ck, {"messages":[{"role":"user","content":t}]})
        enf = sorted({f.entity_class for f in r.findings if not f.advisory_only}) or ["-"]
        adv = sorted({f.entity_class for f in r.findings if f.advisory_only})
        flag = "  <== FP?" if enf != ["-"] else ""
        print(f"  {n:18} {str(r.verdict):18} {enf}{' adv:'+str(adv) if adv else ''}{flag}")

asyncio.run(main())
