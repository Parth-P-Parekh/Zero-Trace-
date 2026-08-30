import sys, asyncio, json; sys.path.insert(0,'/root/ztest')
from lib import *
A = "718190937865"      # Verhoeff-valid
CASES = [
 ("aadhaar bare 12-digit",        A),
 ("aadhaar spaced 4-4-4",         f"{A[:4]} {A[4:8]} {A[8:]}"),
 ("aadhaar labelled",             f"Aadhaar: {A}"),
 ("aadhaar in json",              json.dumps({"aadhaar": A})),
 ("aadhaar hyphenated",           f"{A[:4]}-{A[4:8]}-{A[8:]}"),
 ("aadhaar in sentence",          f"the applicant's uid is {A} and he lives in Pune"),
 ("pan labelled",                 "PAN: ABCPZ1234C"),
 ("pan in json",                  json.dumps({"pan":"ABCPZ1234C"})),
 ("credit card",                  "4111111111111111"),
 ("credit card spaced",           "4111 1111 1111 1111"),
 ("ifsc",                         "HDFC0001234"),
 ("upi vpa",                      "rajesh.kumar@okhdfcbank"),
 ("phone labelled",               "phone: 9876543210"),
 ("email",                        "rajesh.kumar@example.com"),
 ("composite record",             "pincode 560103, DOB 1994-03-11, female, employer Acme"),
]
async def main():
    ck = make_checker(cache=NullSpanCache())
    for name,p in CASES:
        r = await check(ck, {"messages":[{"role":"user","content":p}]})
        cls = ",".join(sorted({f.entity_class for f in r.findings if not f.advisory_only})) or "-"
        adv = ",".join(sorted({f.entity_class for f in r.findings if f.advisory_only}))
        print(f"{name:28} {str(r.verdict):18} {r.confidence:.2f}  {cls}" + (f" (adv:{adv})" if adv else ""))
asyncio.run(main())
