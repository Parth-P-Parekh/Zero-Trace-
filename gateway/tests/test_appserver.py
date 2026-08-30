"""The Codex app-server attachment.

Message shapes here are taken from `codex app-server generate-json-schema` on
codex-cli 0.151.0-alpha.7.1, not invented, so these tests fail if we drift from the
protocol rather than merely from our own idea of it.

Credential literals are assembled at runtime, as everywhere else in this suite: a real
anchor written out in a source file is a real credential in the repository, and this
tool blocks its own development when it finds one.
"""

from __future__ import annotations

import pytest

from gateway.attach.appserver import (
    ALLOW,
    AppServerClient,
    Decision,
    approval_for,
    denial_for,
    payload_of,
)


def _key() -> str:
    return "sk-ant-" + "api03-" + "AbC9dEf2GhI4jKl6MnO8pQr0StU1vWx3Yz5"


class FakeTransport:
    """Scripted server side. `sent` records what the client wrote."""

    def __init__(self, inbound: list[dict]):
        self.inbound = list(inbound)
        self.sent: list[dict] = []

    def send(self, message: dict) -> None:
        self.sent.append(message)

    def recv(self) -> dict | None:
        return self.inbound.pop(0) if self.inbound else None


def _deny_keys(text: str) -> Decision:
    if "sk-ant-" in text:
        return Decision(False, "ZeroTrace blocked this: ANTHROPIC_KEY.", ("ANTHROPIC_KEY",))
    return ALLOW


# ------------------------------------------------------------------- payloads --

def test_payload_extracts_the_command_line():
    got = payload_of("item/commandExecution/requestApproval",
                     {"command": "curl -H 'Authorization: Bearer x'"})
    assert "curl" in got


def test_payload_joins_argv_form():
    got = payload_of("execCommandApproval", {"command": ["curl", "-H", "Bearer x"]})
    assert got == "curl -H Bearer x"


def test_payload_reaches_into_file_change_content():
    """The patch body is nested, and it is the part that matters."""
    got = payload_of("applyPatchApproval", {
        "fileChanges": {"app/.env": {"add": {"content": "TOKEN=" + _key()}}}})
    assert _key() in got and "app/.env" in got


def test_payload_is_empty_for_the_id_only_approval():
    """item/fileChange/requestApproval carries no content; we must not pretend it does."""
    assert payload_of("item/fileChange/requestApproval",
                      {"itemId": "i1", "threadId": "t", "turnId": "u"}) == ""


# ------------------------------------------------------------------ decisions --

def test_denial_shapes_match_the_two_protocol_families():
    review = denial_for("execCommandApproval", "nope")
    assert review == {"decision": {"denied": {"rejection": "nope"}}}
    item = denial_for("item/commandExecution/requestApproval", "nope")
    assert item == {"decision": "decline"}
    assert approval_for("applyPatchApproval") == {"decision": "approved"}
    assert approval_for("item/commandExecution/requestApproval") == {"decision": "accept"}


# --------------------------------------------------------------------- client --

def test_denied_prompt_is_never_sent():
    """The whole point of composing turn/start ourselves: nothing leaves on a block."""
    t = FakeTransport([])
    c = AppServerClient(transport=t, check=_deny_keys, thread_id="t1")
    decision = c.submit("my key is " + _key())
    assert not decision.allow
    assert t.sent == []


def test_allowed_prompt_is_sent_as_turn_start():
    t = FakeTransport([{"id": 1, "result": {}}])
    c = AppServerClient(transport=t, check=_deny_keys, thread_id="t1")
    assert c.submit("refactor the retry loop").allow
    assert t.sent[0]["method"] == "turn/start"
    assert t.sent[0]["params"]["input"] == [
        {"type": "text", "text": "refactor the retry loop"}]


def test_approval_carrying_a_credential_is_denied_with_a_reason():
    approval = {"id": 7, "method": "execCommandApproval",
                "params": {"command": ["curl", "-H", "Authorization: Bearer " + _key()],
                           "callId": "c1", "conversationId": "t1", "cwd": ".",
                           "parsedCmd": []}}
    t = FakeTransport([approval, {"id": 1, "result": {}}])
    c = AppServerClient(transport=t, check=_deny_keys, thread_id="t1")
    c.submit("go")

    answer = next(m for m in t.sent if m.get("id") == 7)
    assert answer["result"]["decision"]["denied"]["rejection"].startswith("ZeroTrace")
    assert c.blocked and c.blocked[0].classes == ("ANTHROPIC_KEY",)


def test_clean_approval_is_accepted():
    approval = {"id": 7, "method": "item/commandExecution/requestApproval",
                "params": {"command": "pytest -q"}}
    t = FakeTransport([approval, {"id": 1, "result": {}}])
    c = AppServerClient(transport=t, check=_deny_keys, thread_id="t1")
    c.submit("go")
    assert next(m for m in t.sent if m.get("id") == 7)["result"] == {"decision": "accept"}
    assert c.blocked == []


def test_approvals_are_served_while_our_own_request_is_outstanding():
    """A client that drained only its own replies would deadlock on the first command."""
    approval = {"id": 9, "method": "item/commandExecution/requestApproval",
                "params": {"command": "ls"}}
    note = {"method": "turn/started", "params": {}}
    ok = {"id": 1, "result": {"thread": {"id": "T"}}}
    t = FakeTransport([note, approval, ok])
    c = AppServerClient(transport=t, check=_deny_keys)
    assert c.start_thread(cwd=".") == "T"
    assert any(m.get("id") == 9 for m in t.sent)


# ------------------------------------------------------------ fail-closed guard --

@pytest.mark.parametrize("policy", ["never", "dangerFullAccess"])
def test_refuses_a_policy_that_routes_no_approvals(policy):
    """Looking protected while seeing nothing is the failure this product exists to stop."""
    c = AppServerClient(transport=FakeTransport([]), check=_deny_keys,
                        approval_policy=policy)
    with pytest.raises(ValueError, match="routes no approvals"):
        c.start_thread()


def test_refuses_to_hand_approvals_to_codexs_own_reviewer():
    c = AppServerClient(transport=FakeTransport([]), check=_deny_keys,
                        approvals_reviewer="auto_review")
    with pytest.raises(ValueError, match="Codex's own reviewer"):
        c.start_thread()


def test_start_thread_asks_for_the_strictest_policy():
    t = FakeTransport([{"id": 1, "result": {"thread": {"id": "T"}}}])
    AppServerClient(transport=t, check=_deny_keys).start_thread(cwd="/x")
    params = t.sent[0]["params"]
    assert params["approvalPolicy"] == "untrusted"
    assert params["approvalsReviewer"] == "user"


def test_refuses_when_the_server_downgrades_the_policy():
    """Managed config can override a client, so the echo is checked, not the request."""
    t = FakeTransport([{"id": 1, "result": {
        "thread": {"id": "T"}, "approvalPolicy": "never", "approvalsReviewer": "user"}}])
    with pytest.raises(ValueError, match="Refusing to run unprotected"):
        AppServerClient(transport=t, check=_deny_keys).start_thread()


def test_refuses_when_the_server_reroutes_the_reviewer():
    t = FakeTransport([{"id": 1, "result": {
        "thread": {"id": "T"}, "approvalPolicy": "untrusted",
        "approvalsReviewer": "auto_review"}}])
    with pytest.raises(ValueError, match="Refusing to run unprotected"):
        AppServerClient(transport=t, check=_deny_keys).start_thread()
