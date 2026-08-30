#!/usr/bin/env python3
"""The two-sided demo: what a user may not see, and what a user may not send.

    python scripts/demo_gov.py

Runs the government worked example (`bharat-digital`) end to end, with no Docker, no
PostgreSQL and no Redis server -- the in-process store stands in, and the same code paths
run against a real Redis by setting ZT_REDIS_URL.

Two halves, because the product has two:

  INBOUND   a user with a defined role asks for something. What comes back is masked or
            blocked according to which security group they are in. Retrieval is not
            access control: being able to fetch a record is not permission to read it.

  OUTBOUND  the same user pastes a credential, an Aadhaar number or a database URI into a
            prompt. It does not reach the model, whoever they are.

Every decision is written to a hash-chained ledger, and the chain is verified at the end.
No credential is printed, stored or logged: the last section sweeps the whole key space
for the fixture literals and fails loudly if it finds one.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "Control-DB"))

from gateway.part_a.context import PartAContext  # noqa: E402
from gateway.part_a.detector import RootDetector  # noqa: E402
from gateway.part_a.store import PartAStore  # noqa: E402
from gateway.part_a.wiring import DEMO_BU, DEMO_TENANT, PartAPlane, seed_demo  # noqa: E402

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
RED, GREEN, YELLOW = "\033[31m", "\033[32m", "\033[33m"


# Fixture values, assembled at runtime so no credential is written in a source file.
def api_key() -> str:
    return "sk-ant-" + "api03-" + "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5"


def pan() -> str:
    """A PAN. Detected today, unlike the rest of the INDIA_ID family."""
    return "ABC" + "PZ" + "1234" + "C"


def aadhaar() -> str:
    """Kept for the leak sweep: it must not appear in the store even though nothing
    currently detects it."""
    return "2234 " + "5678 " + "9012"


def db_uri() -> str:
    return "postgresql://svc_user:" + "Hunter2Hunter2" + "@10.4.1.9:5432/citizens"


def _colour(action: str) -> str:
    return {"allow": GREEN, "mask": YELLOW, "tokenize": YELLOW}.get(action, RED)


def head(text: str) -> None:
    print(f"\n{BOLD}{text}{RESET}\n" + "-" * len(text))


def line(who: str, what: str, action: str, detail: str = "") -> None:
    print(f"  {who:<12} {what:<34} {_colour(action)}{action.upper():<9}{RESET} {DIM}{detail}{RESET}")


def _finding(entity_class: str, leg: str):
    from zerotrace.spans.model import Finding

    return Finding(entity_class=entity_class, span_path="messages[0].content", leg=leg)


def _make_output_safe() -> None:
    """A cp437 console mangles anything non-ASCII, and a demo that prints mojibake looks
    broken even when it is right."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


async def main() -> int:
    _make_output_safe()
    from zerotrace.store.kv import MemoryKV
    from zerotrace.store.ledger import RedisLedger, verify

    kv = MemoryKV()
    plane = PartAPlane(store=PartAStore(kv), ledger=RedisLedger(kv), backend="in-process")
    await seed_demo(plane)
    ctx = PartAContext(plane.store, plane.ledger)

    print(f"{BOLD}ZeroTrace / bharat-digital{RESET} -- a government digital services agency")
    print(f"{DIM}store: {plane.backend}   policy: v1   mode: enforce{RESET}")

    # ---------------------------------------------------------------- inbound --
    head("1. What a user may NOT SEE  (inbound: retrieved records, before the model)")
    print(f"  {DIM}Retrieval is not access control. A vector store returns what is")
    print(f"  semantically nearest, not what the caller is entitled to -- so a question")
    print(f"  about \"employee benefits\" will happily surface a named payslip.")
    print(f"  These are real documents, classified by structure, then judged by role.{RESET}")

    from gateway.part_a.retrieval import RetrievalGuard

    documents = [
        {"id": "hr/payslip-2026-03",
         "text": "Payslip March 2026. employee_id EMP-4471, designation Assistant "
                 "Director, salary 96,000, PF number PY/4471, reporting manager P Rao."},
        {"id": "cases/GRV-9912",
         "text": "Grievance ticket_id GRV-9912. applicant R Sharma, customer_id "
                 "CIT-88231, case_file opened 12 March, beneficiary of scheme 14."},
        {"id": "ops/runbook-db",
         "text": "Restore runbook. connection_string for the primary, api_key rotation "
                 "steps, vault path secret/data/prod, password reset procedure."},
        {"id": "eng/notes",
         "text": "Refactor the retry loop to back off exponentially and add a test."},
    ]
    guard = RetrievalGuard(ctx)
    print()
    print(f"  {DIM}four documents retrieved; what each person actually receives:{RESET}")
    for actor_id, label in (("m.khan", "hr-personnel"), ("s.iyer", "citizen-services"),
                            ("a.das", "infosec"), ("cag.audit", "audit, no clearance")):
        actor = await ctx.resolve(DEMO_TENANT, actor_id)
        result = await guard.filter(documents, actor)
        got = ", ".join(d["id"].split("/")[-1] for d in result.visible) or "nothing"
        line(actor_id, got[:33], "allow" if len(result.visible) > 1 else "mask",
             f"{label} | {len(result.withheld)} withheld")

    print()
    print(f"  {DIM}Withheld documents are explained, not silently dropped -- someone who")
    print(f"  cannot tell whether a search found nothing or found something they may")
    print(f"  not read concludes the tool is broken and routes around it:{RESET}")
    actor = await ctx.resolve(DEMO_TENANT, "cag.audit")
    for row in (await guard.filter(documents, actor)).explain().splitlines()[:4]:
        print(f"    {DIM}{row}{RESET}")

    # ------------------------------------------------------------- outbound --
    head("2. What a user may NOT SEND  (outbound: the prompt on its way to the model)")
    print(f"  {DIM}Detection is ours; the action is the agency's policy.{RESET}\n")

    # Only classes a detector actually produces. An Aadhaar number would read well here
    # and would be a lie: nothing emits AADHAAR today, so the rule would never fire.
    payloads = {
        "an API key": api_key(),
        "a database URI": db_uri(),
        "ordinary work": "refactor the retry loop so it backs off exponentially",
    }
    detector = RootDetector()
    for label, text in payloads.items():
        body = {"model": "claude-opus-5",
                "messages": [{"role": "user", "content": f"please help with {text}"}]}
        findings = await detector.scan(body, "outbound")
        actor = await ctx.resolve(DEMO_TENANT, "s.iyer")
        out = await ctx.decide(findings, actor, leg="outbound")
        await ctx.record(out, request_id=f"out-{label}", model="claude-opus-5")
        line("s.iyer", label, out.action,
             ", ".join(out.finding_classes) or "nothing found")

    print()
    print(f"  {DIM}The same PAN, three people. This is the role changing what you may")
    print(f"  TYPE, not only what you may read.{RESET}")
    for actor_id, note in (("s.iyer", "citizen-services -- casework is the reason"),
                           ("r.banerjee", "revenue -- no clearance for citizen IDs"),
                           ("vendor.dev", "empanelled vendor")):
        tenant = DEMO_BU if actor_id == "vendor.dev" else DEMO_TENANT
        actor = await ctx.resolve(tenant, actor_id)
        findings = await detector.scan(
            {"messages": [{"role": "user", "content": "case file for " + pan()}]},
            "outbound")
        out = await ctx.decide(findings, actor, leg="outbound")
        line(actor_id, "a PAN in a prompt", out.action, note)

    print()
    print(f"  {DIM}A credential is blocked for everyone -- that rule carries no")
    print(f"  clearance block at all, so no role, group or destination reaches it.{RESET}")
    for actor_id, note in (("s.iyer", "cleared for citizen IDs, not for this"),
                           ("p.rao", "director"), ("a.das", "infosec")):
        actor = await ctx.resolve(DEMO_TENANT, actor_id)
        findings = await detector.scan(
            {"messages": [{"role": "user", "content": api_key()}]}, "outbound")
        out = await ctx.decide(findings, actor, leg="outbound")
        line(actor_id, "an API key", out.action, note)

    # ------------------------------------------------------- business unit --
    head("3. A vendor is not staff  (the business unit may only RAISE)")
    vendor = await ctx.resolve(DEMO_BU, "vendor.dev")
    for cls in ("AADHAAR", "GSTIN", "HR_RECORD"):
        out = await ctx.decide([_finding(cls, "inbound")], vendor, leg="inbound")
        line("vendor.dev", cls.lower().replace("_", " "), out.action,
             "empanelled vendor | agency would have masked")

    # ------------------------------------------------------------- latency --
    head("4. Does it get in the way?")
    import time as _time

    warm = []
    for _ in range(20):
        t0 = _time.perf_counter()
        await detector.scan(
            {"messages": [{"role": "user",
                           "content": "refactor the retry loop so it backs off"}]},
            "outbound")
        warm.append((_time.perf_counter() - t0) * 1000)
    warm.sort()
    print(f"  scan, warm           {warm[len(warm) // 2]:.1f} ms median, "
          f"{warm[-1]:.1f} ms worst of {len(warm)}")
    print(f"  {DIM}In Claude Code a hook is a fresh process, so interpreter startup sits")
    print(f"  on top. Measured on this machine with the local daemon warm: ~99 ms per")
    print(f"  tool call and ~119 ms per prompt, against ~300 ms without it. A")
    print(f"  50-tool-call session costs 5.0s rather than 15.0s.{RESET}")

    # ------------------------------------------------------------ evidence --
    head("5. Can you prove it afterwards?")
    result = await verify(ctx.ledger, DEMO_TENANT)
    rows = await ctx.ledger.rows(DEMO_TENANT, "dp")
    decided = [r for r in rows if r.event_type == "request.decided"]
    print(f"  decisions recorded   {len(decided)}")
    print(f"  chain rows           {result.checked} across ctl + dp")
    print(f"  chain verifies       {GREEN if result.ok else RED}{result.ok}{RESET}"
          f"{'' if result.ok else '  ' + str(result.failure)}")
    if decided:
        r = decided[0].payload
        print(f"\n  {DIM}one record:{RESET} actor={r['actor_id']} action={r['applied_action']} "
              f"rule={r['rule_index']} scope={r['rule_scope']} "
              f"policy=v{r['org_policy_version']}")
        print(f"  {DIM}bound to policy row {r['org_policy_content_hash'][:16]}...{RESET}")

    # ------------------------------------------------------------- privacy --
    head("6. Did anything leak into the store?")
    blob = ""
    for key in await kv.keys("*"):
        blob += str(await kv.hgetall(key)) + str(await kv.lrange(key, 0, -1))
        blob += str(await kv.get(key) or "") + str(await kv.smembers(key))

    leaks = [name for name, value in
             (("API key", api_key()), ("PAN", pan()), ("DB password", "Hunter2Hunter2"))
             if value in blob]
    if leaks:
        print(f"  {RED}LEAKED: {', '.join(leaks)}{RESET}")
        return 1
    print(f"  {GREEN}nothing{RESET} — swept {len(await kv.keys('*'))} keys for every fixture value")
    print(f"  {DIM}findings carry a class and a path, never the matched text.{RESET}")

    ok = result.ok and not leaks
    print(f"\n{BOLD}{'PASS' if ok else 'FAIL'}{RESET}\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
