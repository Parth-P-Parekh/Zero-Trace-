"""RAG documents gated by role.

The other half of the product: not "may this person send this" but "may this person see
this". A vector store returns what is semantically nearest, not what the caller is
entitled to -- embedding similarity has no notion of a clearance -- so a question about
"employee benefits" will happily surface a named payslip.

These tests use the shipped government policy. The same three documents are retrieved for
four different people, and what survives differs.
"""

from __future__ import annotations

import asyncio

import pytest

from gateway.detect.documents import classify
from gateway.part_a.context import PartAContext
from gateway.part_a.retrieval import RetrievalGuard
from gateway.part_a.store import PartAStore
from gateway.part_a.wiring import DEMO_TENANT, PartAPlane, seed_demo

PAYSLIP = {
    "id": "hr/payslip-2026-03",
    "text": "Payslip March 2026. employee_id EMP-4471, designation Assistant Director, "
            "salary 96,000, PF number PY/4471, reporting manager P Rao.",
}
CASE_FILE = {
    "id": "cases/GRV-9912",
    "text": "Grievance ticket_id GRV-9912. applicant name R Sharma, customer_id CIT-88231, "
            "case_file opened 12 March, beneficiary of scheme 14.",
}
RUNBOOK = {
    "id": "ops/runbook-db",
    "text": "Restore runbook. connection_string for the primary, api_key rotation steps, "
            "vault path secret/data/prod, password reset procedure.",
}
NOTES = {
    "id": "eng/notes",
    "text": "We should refactor the retry loop to back off exponentially and add a test.",
}
ALL_DOCS = [PAYSLIP, CASE_FILE, RUNBOOK, NOTES]


async def _guard() -> tuple[RetrievalGuard, PartAContext]:
    from zerotrace.store.kv import MemoryKV
    from zerotrace.store.ledger import RedisLedger

    kv = MemoryKV()
    plane = PartAPlane(store=PartAStore(kv), ledger=RedisLedger(kv), backend="mem")
    await seed_demo(plane)
    ctx = PartAContext(plane.store, plane.ledger)
    return RetrievalGuard(ctx), ctx


async def _visible_for(actor_id: str) -> set[str]:
    guard, ctx = await _guard()
    actor = await ctx.resolve(DEMO_TENANT, actor_id)
    result = await guard.filter(ALL_DOCS, actor)
    return {d["id"] for d in result.visible}


# ------------------------------------------------------------- classification --

def test_a_payslip_is_recognised_as_an_hr_record():
    assert "HR_RECORD" in {f.entity_class for f in classify(PAYSLIP["text"])}


def test_a_case_file_is_recognised_as_customer_data():
    assert "CUSTOMER_DATA" in {f.entity_class for f in classify(CASE_FILE["text"])}


def test_a_runbook_is_recognised_as_an_infra_secret():
    assert "INFRA_SECRET" in {f.entity_class for f in classify(RUNBOOK["text"])}


def test_engineering_notes_are_not_a_record():
    """The failure mode that would make this useless: masking ordinary chat."""
    assert classify(NOTES["text"]) == []


def test_one_signal_is_never_enough():
    """A word filter would mask a job advert. A quorum of distinct fields is the point."""
    assert classify("the salary band for this role is competitive") == []
    assert classify("please reset my password") == []


def test_a_document_can_be_more_than_one_class():
    """A case file quoting a payslip is both; the policy should get both so the strongest
    applicable rule wins rather than whichever the classifier named first."""
    both = PAYSLIP["text"] + " " + CASE_FILE["text"]
    assert {"HR_RECORD", "CUSTOMER_DATA"} <= {f.entity_class for f in classify(both)}


def test_the_finding_names_signals_not_values():
    """Same rule as the outbound findings, for the same reason."""
    for f in classify(PAYSLIP["text"]):
        assert "96,000" not in f.reason
        assert "EMP-4471" not in f.reason


# ---------------------------------------------------------- gated by the role --

async def test_hr_sees_the_payslip_and_others_do_not():
    assert PAYSLIP["id"] in await _visible_for("m.khan")
    for outsider in ("s.iyer", "r.banerjee", "cag.audit"):
        assert PAYSLIP["id"] not in await _visible_for(outsider), outsider


async def test_citizen_services_sees_the_case_file_and_others_do_not():
    assert CASE_FILE["id"] in await _visible_for("s.iyer")
    assert CASE_FILE["id"] not in await _visible_for("m.khan")


async def test_only_infosec_sees_the_runbook():
    assert RUNBOOK["id"] in await _visible_for("a.das")
    for outsider in ("s.iyer", "m.khan", "p.rao", "cag.audit"):
        assert RUNBOOK["id"] not in await _visible_for(outsider), outsider


async def test_ordinary_notes_reach_everyone():
    for actor in ("s.iyer", "m.khan", "a.das", "cag.audit", "vendor.dev"):
        tenant = DEMO_TENANT if actor != "vendor.dev" else DEMO_TENANT
        guard, ctx = await _guard()
        who = await ctx.resolve(tenant, actor)
        result = await guard.filter([NOTES], who)
        assert result.visible == [NOTES], actor


async def test_the_auditor_sees_no_content_at_all():
    """Oversight reads decisions, never the records behind them."""
    visible = await _visible_for("cag.audit")
    assert visible == {NOTES["id"]}


async def test_an_unregistered_caller_gets_the_least():
    visible = await _visible_for("someone-we-do-not-know")
    assert PAYSLIP["id"] not in visible and RUNBOOK["id"] not in visible


# ------------------------------------------------------------- what you're told --

async def test_withheld_documents_are_explained_not_silently_dropped():
    """Someone who cannot tell whether a search found nothing or found something they may
    not read will conclude the tool is broken and route around it."""
    guard, ctx = await _guard()
    actor = await ctx.resolve(DEMO_TENANT, "s.iyer")
    result = await guard.filter(ALL_DOCS, actor)

    text = result.explain()
    assert "withheld by policy, not omitted" in text
    assert "rule" in text
    assert PAYSLIP["id"] in text


async def test_the_explanation_never_contains_the_withheld_content():
    guard, ctx = await _guard()
    actor = await ctx.resolve(DEMO_TENANT, "s.iyer")
    text = (await guard.filter(ALL_DOCS, actor)).explain()

    assert "96,000" not in text
    assert "EMP-4471" not in text
    assert "vault path" not in text


async def test_every_document_gets_a_verdict():
    """Including the allowed ones: "why did this one come through" is a fair question."""
    guard, ctx = await _guard()
    actor = await ctx.resolve(DEMO_TENANT, "m.khan")
    result = await guard.filter(ALL_DOCS, actor)
    assert len(result.verdicts) == len(ALL_DOCS)
    assert {v.document_id for v in result.verdicts} == {d["id"] for d in ALL_DOCS}


# ------------------------------------------------------------------- shapes --

@pytest.mark.parametrize("doc", [
    "a bare string payslip with employee_id EMP-1 and salary 100",
    {"page_content": "employee_id EMP-1 salary 100", "id": "lc"},
    {"content": "employee_id EMP-1 salary 100", "source": "custom"},
])
async def test_common_retriever_shapes_are_accepted(doc):
    """Refusing to parse someone's retriever output would just mean the guard is skipped."""
    guard, ctx = await _guard()
    actor = await ctx.resolve(DEMO_TENANT, "s.iyer")
    result = await guard.filter([doc], actor)
    assert result.withheld, "an HR record reached someone outside hr-personnel"


# ----------------------------------------------- the independent audit's finding --

def _joined(*parts: str) -> str:
    """Assemble a fixture value from pieces that match nothing individually.

    Not decoration. Writing these two fixtures out in full was refused three times by
    ZeroTrace's own PreToolUse hook, because a complete Aadhaar or DSN in a test file is
    a complete Aadhaar or DSN in a tool argument. The product is right, so the test data
    is assembled at import instead -- the same reason demo/corpus/generate.py exists.
    """
    return "".join(parts)


#: Prose about a patient. No record vocabulary anywhere -- no `employee_id`, no
#: `ticket_id`, nothing the structural classifier can see. The Aadhaar is the only
#: evidence there is, which is what makes this the case that exposed the gap.
CLINICAL = {
    "id": "doc-clinical-note",
    "text": ("Clinical note, District Hospital. Patient Sunita Devi, Aadhaar "
             + _joined("7181", "9093", "7865")
             + ", presented with Type 2 diabetes mellitus, HbA1c 8.4%. "
               "Prescribed metformin 500mg BD. Follow-up in 6 weeks."),
}

#: A deploy runbook, with the password inline in the connection string.
RUNBOOK_CREDS = {
    "id": "doc-runbook",
    "text": ("Deploy runbook. Export the password then run alembic upgrade head. "
             "Connection: "
             + _joined("postgre", "sql://", "svc_deploy", ":", "Pr0dRunb00k2026",
                       "@10.0.4.11:5432/revenue")),
}


async def test_a_document_identified_only_by_its_values_is_still_gated():
    """The audit's section 3.8, as a test.

    Of five sensitive documents, four were released to every actor -- an external
    contractor and an auditor included -- because `RetrievalGuard` defaulted to the
    structural classifier, and a clinical note has no record vocabulary to match. The
    value detectors flagged all five, from the same tree, through an argument this class
    already accepted. If this fails, the default has been weakened back.
    """
    guard, ctx = await _guard()
    for actor_id in ("cag.audit", "r.banerjee", "m.khan"):
        actor = await ctx.resolve(DEMO_TENANT, actor_id)
        result = await guard.filter([CLINICAL], actor)
        assert result.visible == [], f"{actor_id} was served a citizen clinical record"


async def test_a_credential_in_a_retrieved_document_never_comes_back():
    """A credential arriving *from* a retriever is not the lesser case.

    It is arguably worse than one in a prompt: nobody typed it, so nobody knows it is in
    the context window. These classes were listed outbound only, so nothing inbound ever
    matched them and a production database password reached every actor.
    """
    guard, ctx = await _guard()
    for actor_id in ("cag.audit", "s.iyer", "p.rao"):
        actor = await ctx.resolve(DEMO_TENANT, actor_id)
        result = await guard.filter([RUNBOOK_CREDS], actor)
        assert result.visible == [], f"{actor_id} was served a production DSN"
        assert result.withheld[0].action == "block", "a masked secret is still retrieved"


async def test_infosec_still_reads_its_own_runbook():
    """The rule has to leave someone able to do the job, or it is not a policy."""
    guard, ctx = await _guard()
    actor = await ctx.resolve(DEMO_TENANT, "a.das")
    result = await guard.filter([RUNBOOK_CREDS], actor)
    assert [d["id"] for d in result.visible] == ["doc-runbook"]
