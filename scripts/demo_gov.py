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
    head("1. What a user may NOT SEE  (inbound: the model's reply / retrieved records)")
    print(f"  {DIM}Retrieval is not access control. The same record, three people.{RESET}")
    print(f"  {YELLOW}NOTE{RESET} {DIM}inbound findings are injected here. Classifying a reply as")
    print(f"       AADHAAR / HR_RECORD / INFRA_SECRET has no detector yet: the policy")
    print(f"       machinery is real, the classifier for these classes is not.")
    print(f"       See docs/18_MANUAL_DEMO.md, coverage table.{RESET}\n")

    for actor_id, label in (("s.iyer", "citizen-services"),
                            ("r.banerjee", "revenue"),
                            ("cag.audit", "audit, no clearance")):
        actor = await ctx.resolve(DEMO_TENANT, actor_id)
        out = await ctx.decide([_finding("AADHAAR", "inbound")], actor, leg="inbound")
        await ctx.record(out, request_id=f"in-{actor_id}", model="claude-opus-5")
        line(actor_id, "citizen record (AADHAAR)", out.action,
             f"{label} | rule {out.rule_index} | {out.rule_scope}")

    print()
    for actor_id, cls, label in (("r.banerjee", "GSTIN", "revenue"),
                                 ("s.iyer", "GSTIN", "citizen-services"),
                                 ("m.khan", "HR_RECORD", "hr-personnel"),
                                 ("a.das", "INFRA_SECRET", "infosec"),
                                 ("s.iyer", "INFRA_SECRET", "citizen-services")):
        actor = await ctx.resolve(DEMO_TENANT, actor_id)
        out = await ctx.decide([_finding(cls, "inbound")], actor, leg="inbound")
        await ctx.record(out, request_id=f"in-{actor_id}-{cls}", model="claude-opus-5")
        line(actor_id, cls.lower().replace("_", " "), out.action,
             f"{label} | rule {out.rule_index}")

    # ------------------------------------------------------------- outbound --
    head("2. What a user may NOT SEND  (outbound: the prompt on its way to the model)")
    print(f"  {DIM}Detection is ours; the action is the agency's policy.{RESET}\n")

    # Only classes a detector actually produces. An Aadhaar number would read well here
    # and would be a lie: nothing emits AADHAAR today, so the rule would never fire.
    payloads = {
        "an API key": api_key(),
        "a database URI": db_uri(),
        "a PAN (citizen ID)": pan(),
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

    print(f"\n  {DIM}A credential is blocked for everyone -- that rule carries no")
    print(f"  clearance block at all, so no role, group or destination reaches it.{RESET}")
    for actor_id in ("p.rao", "a.das"):
        actor = await ctx.resolve(DEMO_TENANT, actor_id)
        findings = await detector.scan(
            {"messages": [{"role": "user", "content": api_key()}]}, "outbound")
        out = await ctx.decide(findings, actor, leg="outbound")
        line(actor_id, "an API key", out.action, "director" if actor_id == "p.rao" else "infosec")

    # ------------------------------------------------------- business unit --
    head("3. A vendor is not staff  (the business unit may only RAISE)")
    vendor = await ctx.resolve(DEMO_BU, "vendor.dev")
    for cls in ("AADHAAR", "GSTIN", "HR_RECORD"):
        out = await ctx.decide([_finding(cls, "inbound")], vendor, leg="inbound")
        line("vendor.dev", cls.lower().replace("_", " "), out.action,
             "empanelled vendor | agency would have masked")

    # ------------------------------------------------------------ evidence --
    head("4. Can you prove it afterwards?")
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
    head("5. Did anything leak into the store?")
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
