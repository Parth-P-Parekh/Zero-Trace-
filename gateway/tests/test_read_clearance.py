"""The egress leg, on local files: may this person read this?

The prompt hook asks whether a secret may leave. This asks the question an access-control
system exists for, pointed at the retriever a coding agent actually has -- the filesystem.
The same ten documents, read by seven different people, come back differently.

The corpus these run against is generated rather than committed (`demo/corpus`), because
committing a register of Aadhaar-shaped numbers means putting them in a tool argument and
ZeroTrace's own hook refuses that. So the fixture builds it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway.part_a.context import PartAContext
from gateway.part_a.reading import (
    ReadDecision,
    Withheld,
    candidate_paths,
    classify_file,
)
from gateway.part_a.retrieval import RetrievalGuard
from gateway.part_a.store import PartAStore
from gateway.part_a.wiring import DEMO_BU, DEMO_TENANT, PartAPlane, seed_demo

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "demo" / "corpus" / "bharat-digital"


@pytest.fixture(scope="module", autouse=True)
def corpus():
    """Generate the demo corpus once, so these tests do not depend on a manual step."""
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from demo.corpus.generate import build

    build()
    return CORPUS


def doc(relative: str) -> dict:
    path = CORPUS / relative
    return {"id": relative, "text": path.read_text(encoding="utf-8")}


ALL = [
    "citizen-services/grievance-GRV-2291.md",
    "citizen-services/beneficiary-register-ward-14.csv",
    "revenue/gst-assessment-2025-26.md",
    "revenue/refund-register-Q3.csv",
    "hr-personnel/payslip-2026-03-EMP4471.md",
    "hr-personnel/appraisal-cycle-2025.md",
    "infosec/runbook-prod-restore.md",
    "infosec/pentest-2026-02.md",
    "public/scheme-14-faq.md",
    "public/circular-2026-11.md",
]


async def _actions_for(actor_id: str, tenant: str = DEMO_TENANT) -> dict[str, str]:
    from zerotrace.store.kv import MemoryKV
    from zerotrace.store.ledger import RedisLedger

    kv = MemoryKV()
    plane = PartAPlane(store=PartAStore(kv), ledger=RedisLedger(kv), backend="mem")
    await seed_demo(plane)
    ctx = PartAContext(plane.store, plane.ledger)
    actor = await ctx.resolve(tenant, actor_id)
    guard = RetrievalGuard(ctx, classifier=classify_file)
    result = await guard.filter([doc(r) for r in ALL], actor)
    return {v.document_id: v.action for v in result.verdicts}


# ------------------------------------------------------ the corpus is what it claims --

def test_every_restricted_document_classifies_into_its_own_group():
    """A corpus that classifies as nothing would make the whole demo a no-op.

    This is the test that would have caught the demo passing for the wrong reason: if
    the classifier stops recognising a payslip, every read is allowed and the matrix
    below still looks orderly, just uniformly permissive.
    """
    expected = {
        "citizen-services/grievance-GRV-2291.md": "CUSTOMER_DATA",
        "citizen-services/beneficiary-register-ward-14.csv": "CUSTOMER_DATA",
        "revenue/gst-assessment-2025-26.md": "FINANCIAL_RECORD",
        "revenue/refund-register-Q3.csv": "FINANCIAL_RECORD",
        "hr-personnel/payslip-2026-03-EMP4471.md": "HR_RECORD",
        "hr-personnel/appraisal-cycle-2025.md": "HR_RECORD",
        "infosec/runbook-prod-restore.md": "INFRA_SECRET",
        "infosec/pentest-2026-02.md": "SECURITY_FINDING",
    }
    for relative, entity_class in expected.items():
        classes = {f.entity_class for f in classify_file(doc(relative)["text"])}
        assert entity_class in classes, f"{relative} no longer classifies as {entity_class}"


def test_the_public_documents_classify_as_nothing():
    """The control case, and the one most likely to rot.

    A scheme FAQ says "applicant" and "grievance" because it is *about* a service, not
    because it is a record of one. When those words alone were enough for quorum this
    document was withheld from everybody, which teaches an operator that the tool simply
    says no -- and a tool that always says no is one people turn off.
    """
    for relative in ("public/scheme-14-faq.md", "public/circular-2026-11.md"):
        assert classify_file(doc(relative)["text"]) == []


def test_the_register_is_caught_by_value_even_though_it_is_a_bare_table():
    """A CSV export has no prose for the structural classifier to work with.

    It is a header row and five lines of fields, which is exactly the file an
    organisation most needs gated. The value detectors are what reach it, so this pins
    that they ran -- an earlier version silently returned no classes at all because
    `asyncio.run` cannot be called from inside a running loop.
    """
    classes = {f.entity_class for f in
               classify_file(doc("citizen-services/beneficiary-register-ward-14.csv")["text"])}
    assert "AADHAAR" in classes


# ------------------------------------------------------------------- the matrix --

async def test_each_group_reads_its_own_records_and_nobody_elses():
    citizen = await _actions_for("s.iyer")
    revenue = await _actions_for("r.banerjee")
    hr = await _actions_for("m.khan")

    assert citizen["citizen-services/grievance-GRV-2291.md"] == "allow"
    assert revenue["citizen-services/grievance-GRV-2291.md"] == "mask"
    assert hr["citizen-services/grievance-GRV-2291.md"] == "mask"

    assert revenue["revenue/gst-assessment-2025-26.md"] == "allow"
    assert citizen["revenue/gst-assessment-2025-26.md"] == "mask"

    assert hr["hr-personnel/payslip-2026-03-EMP4471.md"] == "allow"
    assert citizen["hr-personnel/payslip-2026-03-EMP4471.md"] == "mask"


async def test_the_infosec_documents_are_blocked_not_masked_for_everyone_else():
    """A masked secret is still a secret that was retrieved."""
    infosec = await _actions_for("a.das")
    citizen = await _actions_for("s.iyer")
    assert infosec["infosec/runbook-prod-restore.md"] == "allow"
    assert citizen["infosec/runbook-prod-restore.md"] == "block"
    assert citizen["infosec/pentest-2026-02.md"] == "block"


async def test_the_auditor_reads_no_content_at_all():
    audit = await _actions_for("cag.audit")
    for relative in ALL:
        if relative.startswith("public/"):
            continue
        assert audit[relative] in ("mask", "block"), relative


async def test_the_vendor_is_blocked_where_staff_are_only_masked():
    """The business unit may only raise, and this is what raising looks like."""
    vendor = await _actions_for("vendor.dev", tenant=DEMO_BU)
    assert vendor["citizen-services/grievance-GRV-2291.md"] == "block"
    assert vendor["revenue/gst-assessment-2025-26.md"] == "block"
    assert vendor["hr-personnel/payslip-2026-03-EMP4471.md"] == "block"


async def test_the_public_documents_reach_everyone_including_the_vendor():
    """Without this the demo proves only that the tool can say no."""
    for actor_id, tenant in (("s.iyer", DEMO_TENANT), ("cag.audit", DEMO_TENANT),
                             ("vendor.dev", DEMO_BU)):
        actions = await _actions_for(actor_id, tenant)
        assert actions["public/scheme-14-faq.md"] == "allow"
        assert actions["public/circular-2026-11.md"] == "allow"


# ------------------------------------------------- what counts as a read at all --

@pytest.mark.parametrize("tool,args", [
    ("Read", {"file_path": str(CORPUS / "infosec" / "runbook-prod-restore.md")}),
    ("Grep", {"pattern": "password",
              "path": str(CORPUS / "infosec" / "runbook-prod-restore.md")}),
    ("Bash", {"command": f'cat "{CORPUS / "infosec" / "runbook-prod-restore.md"}"'}),
    ("Bash", {"command": f'head -20 {CORPUS / "infosec" / "runbook-prod-restore.md"}'}),
    ("mcp__files__read_file",
     {"path": str(CORPUS / "infosec" / "runbook-prod-restore.md")}),
])
def test_the_paths_a_read_can_hide_in_are_all_found(tool, args):
    paths = candidate_paths(tool, args)
    assert any(p.name == "runbook-prod-restore.md" for p in paths), (
        f"{tool} route did not resolve the file"
    )


def test_a_directory_read_expands_to_the_files_under_it():
    """`grep -r infosec/` is a read of everything in it, whatever the call names."""
    paths = candidate_paths("Grep", {"pattern": "x", "path": str(CORPUS / "infosec")})
    assert {p.name for p in paths} == {"runbook-prod-restore.md", "pentest-2026-02.md"}


def test_a_command_that_only_mentions_a_path_is_not_a_read():
    """`ls` and `rm` name a file without putting its contents in front of the model.

    Gating them would be the kind of overreach that gets a security tool disabled.
    """
    target = str(CORPUS / "infosec" / "runbook-prod-restore.md")
    assert candidate_paths("Bash", {"command": f"ls -la {target}"}) == []
    assert candidate_paths("Bash", {"command": f"touch {target}"}) == []


def test_only_the_reading_half_of_a_compound_command_counts():
    """`ls x && cat y` is two commands, and only one of them is a read."""
    runbook = CORPUS / "infosec" / "runbook-prod-restore.md"
    faq = CORPUS / "public" / "scheme-14-faq.md"
    paths = candidate_paths("Bash", {"command": f"ls {faq} && cat {runbook}"})
    assert [p.name for p in paths] == ["runbook-prod-restore.md"]


def test_a_redirect_is_a_read_whatever_the_command_is():
    runbook = CORPUS / "infosec" / "runbook-prod-restore.md"
    paths = candidate_paths("Bash", {"command": f"while read l; do :; done < {runbook}"})
    assert any(p.name == "runbook-prod-restore.md" for p in paths)


def test_a_path_that_does_not_exist_is_not_a_candidate():
    """Judging a file we cannot open would mean guessing from the name."""
    assert candidate_paths("Read", {"file_path": str(CORPUS / "nope" / "missing.md")}) == []


# ---------------------------------------------------------- the refusal itself --

def test_the_refusal_names_the_rule_and_never_the_contents():
    """The reason string is read by the model. It is the last place to leak a file.

    Everything in it is either a fact about the policy -- which is public, it is in
    Control-DB/policies/ -- or the path the agent already asked for.
    """
    decision = ReadDecision(
        allow=False, actor="cag.audit", tenant=DEMO_TENANT, groups=("audit",),
        withheld=(Withheld(path="citizen-services/grievance-GRV-2291.md", action="mask",
                           classes=("CUSTOMER_DATA",), rule_index=0, rule_scope="org"),),
    )
    reason = decision.reason
    body = doc("citizen-services/grievance-GRV-2291.md")["text"]

    assert "cag.audit" in reason and "CUSTOMER_DATA" in reason and "rule 0" in reason
    # No line of the file's body may appear in the refusal.
    for line in body.splitlines():
        stripped = line.strip()
        if len(stripped) > 12:
            assert stripped not in reason


def test_the_refusal_tells_the_agent_not_to_route_around_it():
    """A model told only "denied" will helpfully try `cat` next."""
    decision = ReadDecision(
        allow=False, actor="s.iyer", tenant=DEMO_TENANT, groups=("citizen-services",),
        withheld=(Withheld(path="x", action="block", classes=("INFRA_SECRET",),
                           rule_index=4, rule_scope="org"),),
    )
    assert "another way" in decision.reason


# ------------------------------------------------------------------ the hook --

def test_the_hook_denies_a_read_the_actor_is_not_cleared_for(tmp_path, monkeypatch):
    """End to end through the hook, as Claude Code would call it."""
    import subprocess
    import sys

    home = tmp_path / "zt"
    home.mkdir()
    env = _hook_env(home)

    # Seed the store and log in as the auditor, who is cleared for nothing.
    subprocess.run([sys.executable, "-c", _SEED], cwd=ROOT, env=env, check=True,
                   capture_output=True, text=True, timeout=180)

    event = {
        "session_id": "read-clearance-test", "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": str(CORPUS / "hr-personnel" /
                                        "payslip-2026-03-EMP4471.md")},
    }
    result = subprocess.run(
        [sys.executable, str(ROOT / "hooks" / "zt_pretool.py"), "--claude"],
        input=json.dumps(event), capture_output=True, text=True, env=env, timeout=180,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "HR_RECORD" in result.stdout
    assert "cag.audit" in result.stdout
    # The refusal must not carry the payslip.
    assert "1,22,240" not in result.stdout + result.stderr


def test_the_hook_allows_a_read_the_actor_is_cleared_for(tmp_path):
    """The half of the demo that shows this is a policy and not a wall."""
    import subprocess
    import sys

    home = tmp_path / "zt"
    home.mkdir()
    env = _hook_env(home)
    subprocess.run([sys.executable, "-c", _SEED], cwd=ROOT, env=env, check=True,
                   capture_output=True, text=True, timeout=180)

    event = {
        "session_id": "read-clearance-test", "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": str(CORPUS / "public" / "circular-2026-11.md")},
    }
    result = subprocess.run(
        [sys.executable, str(ROOT / "hooks" / "zt_pretool.py"), "--claude"],
        input=json.dumps(event), capture_output=True, text=True, env=env, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == ""


def test_the_hook_is_silent_when_nobody_is_logged_in(tmp_path):
    """No role, no clearance layer -- and no cost, and no comment."""
    import subprocess
    import sys

    home = tmp_path / "zt-empty"
    home.mkdir()
    env = _hook_env(home)

    event = {
        "session_id": "read-clearance-test", "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": str(CORPUS / "infosec" / "runbook-prod-restore.md")},
    }
    result = subprocess.run(
        [sys.executable, str(ROOT / "hooks" / "zt_pretool.py"), "--claude"],
        input=json.dumps(event), capture_output=True, text=True, env=env, timeout=180,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def _hook_env(home: Path) -> dict:
    import os

    return {**os.environ, "ZT_HOME": str(home), "ZT_NO_DAEMON": "1",
            "ZT_REDIS_URL": "", "PYTHONPATH": str(ROOT)}


#: Seed the agency and log in as the auditor, in the subprocess's own ZT_HOME.
_SEED = """
import asyncio, sys
sys.path.insert(0, ".")
from gateway.part_a.session import login, plane
from gateway.part_a.wiring import DEMO_TENANT, seed_demo
asyncio.run(seed_demo(plane()))
login("cag.audit", DEMO_TENANT)
"""


# ------------------------------------------------- the ways this failed quietly --

def test_an_unrecognised_daemon_reply_is_treated_as_no_daemon(monkeypatch):
    """A daemon too old to know `/check-read` answers 404 with a JSON error body.

    That body parses fine and contains neither `skip` nor `allow`, so reading `allow` off
    it with a `True` default meant the clearance check was skipped silently -- against a
    daemon left running from a previous version, which is the ordinary case during an
    upgrade. The failure mode is the worst available: a refusal quietly becomes a read.
    """
    from hooks import daemon_client

    monkeypatch.setattr(daemon_client, "disabled", lambda: False)
    monkeypatch.setattr(daemon_client, "_endpoint", lambda: (1, "t"))
    monkeypatch.setattr(daemon_client, "_post", lambda *a, **k: {"error": "no such path"})
    assert daemon_client.ask_read("Read", {"file_path": "x"}) is None


def test_the_daemon_does_not_ask_itself_for_the_value_scan():
    """`value_classes` over loopback, from inside the daemon's own handler, killed it.

    The nested `run_until_complete` on an already-running loop took the process down and
    the endpoint file with it, so the next hook found no daemon and fell back to the slow
    path -- which still worked, which is why it went unnoticed for a while.
    """
    import inspect

    from gateway import daemon

    assert "scan=_value_classes_local" in inspect.getsource(daemon), (
        "the daemon's read check must pass a local scanner, or it calls itself"
    )


def test_the_pack_is_built_once_per_process():
    """A directory read classifies many files, and rebuilding the pack for each measured
    at ~300ms apiece -- the cost the daemon exists to pay exactly once."""
    from gateway.part_a import reading

    reading._CHECKER = None
    first = reading._checker()
    assert reading._checker() is first


def test_a_redirect_target_is_not_a_read():
    """`cat >> notes.md <<EOF` is a write whose verb happens to be a reader.

    Found the hard way: this product refused its own author's append to a test file,
    having decided the redirect target was something being read. Getting it wrong is not
    a small false positive -- it blocks ordinary writes on a reader's clearance.
    """
    target = str(CORPUS / "public" / "circular-2026-11.md")
    assert candidate_paths("Bash", {"command": f"cat >> {target} <<EOF"}) == []
    assert candidate_paths("Bash", {"command": f"cat > {target}"}) == []
    # ...but a genuine read that happens to redirect its OUTPUT still counts.
    assert [p.name for p in candidate_paths(
        "Bash", {"command": f"cat {target} > /tmp/out"})] == ["circular-2026-11.md"]


# ------------------------------------------- the credential floor, role or no role --

def _key_file(tmp_path):
    """A config file with a correctly-shaped credential in it.

    Assembled rather than written whole, for the reason the rest of this suite is: a
    complete key in a source file is a complete key in a tool argument.
    """
    key = "sk-" + "ant-" + "api03-" + "x7Kq9mZp2Wv4Bn8Rt6" + "Yu3Ia5Oe1Ld0Sf3Gh7Jk2Mn5Pq8Rs"
    path = tmp_path / "config.env"
    path.write_text(f"ANTHROPIC_API_KEY={key}" + chr(10) + "DEBUG=1" + chr(10),
                    encoding="utf-8")
    return path, key


def test_a_credential_in_a_file_is_refused_with_nobody_logged_in(tmp_path):
    """The hole this closed.

    The clearance gate used to return early when there was no session, on the reasoning
    that without a role there is no policy layer. True -- but it also meant no protection
    at all, so a `.env` full of live keys was read straight into the transcript by anyone
    who had not run `zerotrace login`. Ten seconds to find, and the prompt hook had never
    worked that way: it blocks a credential whether or not you have a role.
    """
    import asyncio

    from gateway.part_a.reading import candidate_paths, decide_read

    path, key = _key_file(tmp_path)
    monkey_home = tmp_path / "empty-home"
    monkey_home.mkdir()
    import os

    old = os.environ.get("ZT_HOME")
    os.environ["ZT_HOME"] = str(monkey_home)
    try:
        decision = asyncio.run(decide_read(candidate_paths("Read",
                                                           {"file_path": str(path)})))
    finally:
        if old is None:
            os.environ.pop("ZT_HOME", None)
        else:
            os.environ["ZT_HOME"] = old

    assert decision is not None, "no session meant no protection at all"
    assert decision.allow is False
    assert "ANTHROPIC_KEY" in decision.withheld[0].classes
    assert key not in decision.reason


def test_the_credential_refusal_does_not_claim_a_clearance_problem(tmp_path):
    """"You are not cleared for this" would send the reader to ask for a grant that does
    not exist. There is no role that makes a private key safe to pull into a context
    window, which is why the outbound credential rule carries no clearance block either.
    """
    from gateway.part_a.reading import ReadDecision, Withheld

    decision = ReadDecision(
        allow=False, actor="", tenant="", groups=(),
        withheld=(Withheld(path="config.env", action="block",
                           classes=("ANTHROPIC_KEY",), rule_index=None,
                           rule_scope="credential"),),
    )
    assert "contain credentials" in decision.reason
    assert "No role clears this" in decision.reason
    assert "is not cleared for them" not in decision.reason


def test_the_floor_covers_credentials_and_leaves_records_to_the_policy(tmp_path):
    """Scope matters. "May this person read a payslip" has no answer when there is no
    person, so records are left to the policy layer and only credentials are refused
    outright. A floor that also blocked records would refuse every read on a machine
    where nobody had logged in."""
    from gateway.part_a.reading import credential_files

    path, _ = _key_file(tmp_path)
    payslip = CORPUS / "hr-personnel" / "payslip-2026-03-EMP4471.md"

    assert credential_files([path]), "a credential file was not caught"
    assert credential_files([payslip]) == [], "a record was caught by the credential floor"


def test_an_empty_argument_is_not_the_current_directory():
    """`grep -c "" file` counts lines. It is not a read of the whole repository.

    `Path("")` is the current directory, so an empty token expanded to every file under
    the working tree -- `.git` included -- and the read was judged against all of it.
    Found when this gate blocked its own author counting the lines in two test files.
    A false positive of that shape is how a security tool gets switched off.
    """
    paths = candidate_paths("Bash", {"command": 'grep -c "" pytest.ini'})
    assert [p.name for p in paths] == ["pytest.ini"]
    assert not any(".git" in str(p) for p in paths)


def test_writing_to_a_file_is_not_reading_it():
    """`Write` names `file_path` too, and judging a write against the file's *current*
    contents is wrong in the direction that breaks people's work.

    Editing a document about HR records became impossible on an HR clearance. Caught
    when this repository's README was written and the hook refused to save it, because
    the README discusses the very classes it documents. A tool that blocks writes gets
    switched off within the hour.
    """
    payslip = str(CORPUS / "hr-personnel" / "payslip-2026-03-EMP4471.md")
    assert candidate_paths("Write", {"file_path": payslip, "content": "x"}) == []
    assert candidate_paths("Edit", {"file_path": payslip, "new_string": "x"}) == []
    assert candidate_paths("NotebookEdit", {"notebook_path": payslip}) == []
    # ...but reading the same file still is a read.
    assert candidate_paths("Read", {"file_path": payslip})


def test_an_unknown_reader_is_gated_and_an_unknown_writer_is_not():
    """MCP servers are not ours to enumerate, so the tool's name is the only signal."""
    faq = str(CORPUS / "public" / "scheme-14-faq.md")
    assert candidate_paths("mcp__fs__read_file", {"path": faq})
    assert candidate_paths("mcp__docs__get_document", {"path": faq})
    assert candidate_paths("mcp__fs__save_note", {"path": faq}) == []
    assert candidate_paths("mcp__fs__write_file", {"path": faq}) == []


def test_the_installed_matcher_actually_reaches_the_read_tools():
    """The gate is worthless if the harness never invokes it.

    Every other test in this file calls `zt_pretool` directly, which bypasses the
    PreToolUse *matcher* in the installed settings. That matcher listed Bash, Write,
    Edit and the rest but not Read or Grep -- so on a real Claude Code session a `Read`
    was never handed to the hook, and reads were only gated when they happened to go
    through Bash. Every test passed the whole time.

    This pins the matcher to the tools the gate claims to handle, so the two cannot
    drift apart again.
    """
    import re

    from hooks.install import HOOKS
    from gateway.part_a.reading import READ_TOOLS

    matcher = next(h[2] for h in HOOKS if h[0] == "PreToolUse")
    for tool in sorted(READ_TOOLS):
        assert re.fullmatch(matcher, tool), (
            f"{tool} is gated by reading.py but the installed matcher never sends it"
        )
    # The write-side tools stay matched too: their arguments still carry payloads.
    for tool in ("Bash", "Write", "Edit", "mcp__fs__read_file"):
        assert re.fullmatch(matcher, tool), f"{tool} fell out of the matcher"
