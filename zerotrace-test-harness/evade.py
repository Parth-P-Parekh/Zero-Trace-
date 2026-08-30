import sys, asyncio, json; sys.path.insert(0,'/root/ztest')
from lib import *

KEY = "sk-ant-api03-" + "A"*30 + "BBBB"
AWS = "AKIAIOSFODNN7EXAMPLE"
PAN = "ABCPZ1234C"
PEM = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA7v1a\n-----END RSA PRIVATE KEY-----"

CASES = [
 ("plain anthropic key",            KEY),
 ("plain aws key",                  AWS),
 ("plain PEM",                      PEM),
 ("key split by space",             KEY[:20] + " " + KEY[20:]),
 ("key split by newline",           KEY[:20] + "\n" + KEY[20:]),
 ("key with zero-width",            KEY[:20] + "​" + KEY[20:]),
 ("key reversed",                   KEY[::-1]),
 ("key base64",                     __import__("base64").b64encode(KEY.encode()).decode()),
 ("key hex",                        KEY.encode().hex()),
 ("key rot13",                      __import__("codecs").encode(KEY,"rot13")),
 ("key url-encoded",                __import__("urllib.parse",fromlist=['x']).quote(KEY)),
 ("key in comment",                 f"# TODO remove {KEY}"),
 ("key char-joined",                "-".join(KEY)),
 ("key as list",                    json.dumps(list(KEY))),
 ("key w/ homoglyph dash",          KEY.replace("-", "‐", 1)),
 ("key lowercased marker",          KEY.replace("sk-ant", "SK-ANT")),
 ("PAN plain",                      PAN),
 ("PAN spaced",                     "ABCP Z123 4C"),
 ("PAN with dots",                  "A.B.C.P.Z.1.2.3.4.C"),
 ("aadhaar plain",                  "2345 6789 0123"),
 ("password assign",                "DB_PASSWORD=hunter2correcthorse"),
 ("password yaml",                  "db_password: s3cr3t-value-here-9x"),
 ("bearer token",                   "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.abc"),
 ("postgres dsn",                   "postgres://admin:Sup3rS3cret@db.internal:5432/prod"),
 ("mongo srv",                      "mongodb+srv://root:pw12345678@cluster0.abcd.mongodb.net"),
 ("ssh key by filename",            'cat ~/.ssh/id_rsa'),
 ("high entropy blob",              "x7Kq9mZp2Wv4Bn8Rt6Yu3Ia5Oe1Ld0Sf"),
 ("key in nested json string",      json.dumps({"cfg": json.dumps({"api_key": KEY})})),
 ("key in deep nesting",            json.dumps({"a":{"b":{"c":{"d":{"e":KEY}}}}})),
]

async def main():
    ck = make_checker(cache=NullSpanCache())
    print(f"{'case':32} {'verdict':7} {'conf':5}  classes")
    miss = []
    for name, payload in CASES:
        r = await check(ck, {"messages":[{"role":"user","content":payload}]})
        cls = ",".join(sorted({f.entity_class for f in r.findings if not f.advisory_only})) or "-"
        adv = ",".join(sorted({f.entity_class for f in r.findings if f.advisory_only}))
        print(f"{name:32} {str(r.verdict):7} {r.confidence:.2f}  {cls}" + (f"  (advisory:{adv})" if adv else ""))
        if str(r.verdict) not in ("Verdict.RED","red"): miss.append(name)
    print("\nNOT RED:", len(miss), "/", len(CASES))
    for m in miss: print("   -", m)

asyncio.run(main())
