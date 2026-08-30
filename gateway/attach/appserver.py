"""Attach ZeroTrace to Codex through the app-server protocol.

This is the supported interface behind rich clients such as the VS Code extension, and
it replaces the hook route for Codex entirely. Hooks were the wrong door: Codex will not
run a hook a human has not reviewed, trust is pinned to the file's hash, and an untrusted
hook is skipped in silence (docs/14_CODEX_HOOK_TRUST.md). None of that applies here,
because a client is not an extension point that has to be trusted -- it is the thing
being served.

Two interception points, both native to the protocol.

**Prompts.** The client composes `turn/start`. A prompt ZeroTrace denies is simply never
sent, so nothing reaches the model and nothing enters the transcript. That is strictly
stronger than the `UserPromptSubmit` hook, which could only ask the harness to stop after
already being handed the text.

**Tool calls.** The server asks the client to approve each one, as a JSON-RPC *request*
that blocks until it is answered:

    item/commandExecution/requestApproval   the command line, before it runs
    execCommandApproval                     argv form of the same
    applyPatchApproval                      the file changes, with content
    item/fileChange/requestApproval         a file edit, by id

Answering with a denial stops the call and hands the agent our reason, so it can try
something else. That is a real veto with a channel back, not an exit code the harness is
free to ignore.

**What decides how much we see.** Approvals are routed by policy, so a client that asks
for none is not protected. `thread/start` takes `approvalPolicy` and `turn/start` can
override it per turn -- so the client, meaning us, chooses. We ask for `untrusted`, the
strictest, and set `approvalsReviewer="user"` so requests come to us rather than to
Codex's own `auto_review` subagent. `assert_enforcing()` refuses any configuration that
would quietly narrow coverage.

Contract verified against codex-cli 0.151.0-alpha.7.1 via `codex app-server
generate-json-schema`, and the handshake against a live process.
"""

from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

#: Policies under which commands are offered to us. `never` and `dangerFullAccess` route
#: nothing, so a session using them is unprotected however healthy it looks.
ENFORCING_POLICIES = frozenset({"untrusted", "on-request"})

#: Server->client requests carrying something worth scanning.
APPROVAL_METHODS = (
    "item/commandExecution/requestApproval",
    "execCommandApproval",
    "applyPatchApproval",
    "item/fileChange/requestApproval",
)

#: The two methods whose decision is a ReviewDecision rather than a plain string enum.
_REVIEW_DECISION_METHODS = frozenset({"execCommandApproval", "applyPatchApproval"})


class Transport(Protocol):
    """Newline-delimited JSON-RPC."""

    def send(self, message: dict) -> None: ...
    def recv(self) -> dict | None: ...


@dataclass(frozen=True)
class Decision:
    allow: bool
    reason: str = ""
    classes: tuple[str, ...] = ()

    @property
    def rejection(self) -> str:
        return self.reason or "ZeroTrace blocked this."


ALLOW = Decision(True)


# ------------------------------------------------------------------- checking --

def build_checker() -> Callable[[str], Decision]:
    """Build the detector pack once and reuse it.

    The hook path rebuilds it per invocation because each hook is a fresh process that
    exits. A client is long-lived, and this sits in front of every command the agent
    runs, so paying that cost per approval would be indefensible.
    """
    import asyncio
    import logging
    import os

    logging.getLogger("gateway").setLevel(logging.CRITICAL)

    from gateway.base.cache import NullSpanCache
    from gateway.base.checker import Checker, CheckerConfig
    from gateway.base.scanner import DetectorPack
    from gateway.check import text_tree, to_verdict
    from gateway.detect.encodings import EncodedScanner
    from gateway.detect.obfuscation import ObfuscationScanner
    from gateway.detect.s0_credentials import scan_span_credentials
    from gateway.detect.composite import scan_span_composite
    from gateway.detect.s1_context import ContextScanner
    from gateway.detectors import ALL_DETECTORS

    detectors = list(ALL_DETECTORS)
    pack = DetectorPack.build(
        detectors, version=1,
        scanners=[scan_span_credentials, ObfuscationScanner(detectors),
                  ContextScanner(), scan_span_composite,
                  EncodedScanner(scan_span_credentials)],
    )
    checker = Checker(pack, NullSpanCache(),
                      os.environ.get("ZT_VAULT_MASTER_KEY", "dev-key").encode(),
                      CheckerConfig.from_env())

    def check(text: str) -> Decision:
        if not text.strip():
            return ALLOW
        v = to_verdict(asyncio.run(checker.check(text_tree(text), "local")))
        return Decision(v.allow, v.reason, tuple(v.classes))

    return check


def _default_window():
    """The cross-prompt window, or None when it cannot be loaded.

    Losing it costs missed bridges, never a blocked prompt, so a client still starts.
    """
    try:
        from gateway.base.window import PromptWindow

        return PromptWindow()
    except Exception:  # noqa: BLE001
        return None


def payload_of(method: str, params: dict) -> str:
    """The text worth scanning in one approval request.

    `item/fileChange/requestApproval` carries only identifiers -- the content arrives
    separately as `item/fileChange/patchUpdated` notifications. This returns empty for it
    rather than pretend to inspect it; `applyPatchApproval` is where file content is
    actually seen.
    """
    if method == "item/commandExecution/requestApproval":
        return str(params.get("command") or "")
    if method == "execCommandApproval":
        argv = params.get("command") or []
        return " ".join(str(a) for a in argv) if isinstance(argv, list) else str(argv)
    if method == "applyPatchApproval":
        changes = params.get("fileChanges") or {}
        parts: list[str] = []
        for path, change in changes.items():
            parts.append(str(path))
            parts.extend(_strings(change))
        return "\n".join(parts)
    return ""


def _strings(obj: Any, depth: int = 0) -> list[str]:
    if depth > 4:
        return []
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _strings(v, depth + 1)]
    if isinstance(obj, list):
        return [s for v in obj for s in _strings(v, depth + 1)]
    return []


def denial_for(method: str, reason: str) -> dict:
    """The deny result for one approval method.

    Two shapes, which is why this is a function. `ReviewDecision` carries a rejection
    string back to the agent; the newer item-scoped approvals take a bare `decline`.
    """
    if method in _REVIEW_DECISION_METHODS:
        return {"decision": {"denied": {"rejection": reason}}}
    return {"decision": "decline"}


def approval_for(method: str) -> dict:
    if method in _REVIEW_DECISION_METHODS:
        return {"decision": "approved"}
    return {"decision": "accept"}


# --------------------------------------------------------------------- client --

@dataclass
class AppServerClient:
    """A ZeroTrace-mediated app-server session."""

    transport: Transport
    check: Callable[[str], Decision] = field(default_factory=build_checker)
    approval_policy: str = "untrusted"
    approvals_reviewer: str = "user"
    thread_id: str | None = None
    blocked: list[Decision] = field(default_factory=list)
    #: Cross-prompt carry. Set to None to disable; the session id keys it, so a client
    #: serving several threads keeps their carries apart.
    window: Any = field(default_factory=lambda: _default_window())
    session_id: str = "appserver"
    _next_id: int = 1

    # -- plumbing --

    def _request(self, method: str, params: dict | None = None) -> dict:
        rid, self._next_id = self._next_id, self._next_id + 1
        self.transport.send({"jsonrpc": "2.0", "id": rid, "method": method,
                             "params": params or {}})
        return self._await(rid)

    def _await(self, rid: int) -> dict:
        """Read until our answer arrives, serving the server's requests meanwhile.

        The server asks for approvals *while* a request of ours is outstanding, so a
        client that drained only its own replies would deadlock the moment the agent
        wanted to run a command.
        """
        while True:
            msg = self.transport.recv()
            if msg is None:
                raise ConnectionError("app-server closed the connection")
            if msg.get("id") == rid and "method" not in msg:
                if "error" in msg:
                    raise RuntimeError(f"app-server error: {msg['error']}")
                return msg.get("result") or {}
            self.handle(msg)

    def handle(self, msg: dict) -> None:
        if msg.get("method") in APPROVAL_METHODS and "id" in msg:
            self._answer_approval(msg)

    def _answer_approval(self, msg: dict) -> None:
        method, params = msg["method"], msg.get("params") or {}
        decision = self.check(payload_of(method, params))
        if decision.allow:
            result = approval_for(method)
        else:
            self.blocked.append(decision)
            result = denial_for(method, decision.rejection)
        self.transport.send({"jsonrpc": "2.0", "id": msg["id"], "result": result})

    # -- session --

    def initialize(self, name: str = "zerotrace", version: str = "0.1.0") -> dict:
        return self._request("initialize", {
            "clientInfo": {"name": name, "version": version, "title": "ZeroTrace"}})

    def start_thread(self, cwd: str | None = None, **extra: Any) -> str:
        self.assert_enforcing()
        params: dict[str, Any] = {
            "approvalPolicy": self.approval_policy,
            "approvalsReviewer": self.approvals_reviewer,
        }
        if cwd:
            params["cwd"] = cwd
        params.update(extra)
        result = self._request("thread/start", params)
        self._assert_server_honoured(result)
        self.thread_id = ((result.get("thread") or {}).get("id")
                          or result.get("threadId") or "")
        return self.thread_id

    def _assert_server_honoured(self, result: dict) -> None:
        """Check what we got, not what we asked for.

        `thread/start` echoes the policy and reviewer actually in force, and they need
        not match the request -- enterprise-managed config and requirements can override
        a client. Asking for `untrusted` and assuming we got it is how a session ends up
        looking protected while approvals are routed elsewhere, so the echo is verified
        and a downgrade is refused rather than logged.
        """
        policy = result.get("approvalPolicy")
        reviewer = result.get("approvalsReviewer")
        if policy is not None and not (
            isinstance(policy, str) and policy in ENFORCING_POLICIES
        ):
            raise ValueError(
                f"server set approvalPolicy={policy!r}, which routes no approvals to "
                f"ZeroTrace. Refusing to run unprotected."
            )
        if reviewer is not None and reviewer != "user":
            raise ValueError(
                f"server set approvalsReviewer={reviewer!r}, so approvals go to Codex's "
                f"reviewer rather than ZeroTrace. Refusing to run unprotected."
            )

    def submit(self, text: str) -> Decision:
        """Check, then send. A denied prompt is never sent at all."""
        decision = self.check(text)
        if not decision.allow:
            self.blocked.append(decision)
            return decision

        # Clean alone is not clean in sequence: half a key one turn and the rest the
        # next reaches the model whole. The carried tail is joined to this prompt's head
        # and scanned once more. Both sides were allowed on their own, so a hit here
        # exists only across the boundary. See gateway/base/window.PromptWindow.
        if self.window is not None:
            joined = self.window.bridge(self.session_id, text)
            if joined:
                bridged = self.check(joined)
                if not bridged.allow:
                    split = Decision(
                        False,
                        "ZeroTrace blocked this prompt: joined with what you sent just "
                        "before, it forms "
                        + (", ".join(bridged.classes) or "a credential")
                        + ". Nothing was sent. Splitting a secret across two messages "
                        "does not divide it -- the conversation holds both halves.",
                        bridged.classes,
                    )
                    self.blocked.append(split)
                    self.window.clear(self.session_id)
                    return split
            # Carry only from prompts that were allowed, so a blocked one never leaves a
            # tail for the next to trip over.
            self.window.remember(self.session_id, text)

        self._request("turn/start", {
            "threadId": self.thread_id,
            "input": [{"type": "text", "text": text}],
            "approvalPolicy": self.approval_policy,
        })
        return decision

    def assert_enforcing(self) -> None:
        """Refuse a configuration under which we would silently see less.

        Approvals are the only place a tool call can be stopped, and they are routed by
        policy. Under `never`, or with `approvalsReviewer="auto_review"`, commands run
        without ever being offered to us: the session would look protected and not be.
        Refusing here is the same call as failing closed everywhere else in this codebase.
        """
        if self.approval_policy not in ENFORCING_POLICIES:
            raise ValueError(
                f"approval_policy={self.approval_policy!r} routes no approvals to "
                f"ZeroTrace, so tool calls would not be checked. Use one of "
                f"{sorted(ENFORCING_POLICIES)}."
            )
        if self.approvals_reviewer != "user":
            raise ValueError(
                f"approvals_reviewer={self.approvals_reviewer!r} routes approvals to "
                f"Codex's own reviewer instead of to ZeroTrace. Use 'user'."
            )


# ------------------------------------------------------------------ transport --

class StdioTransport:
    """Spawn `codex app-server` and speak newline-delimited JSON-RPC to it."""

    def __init__(self, argv: list[str]):
        self._proc = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1,
        )
        self._lock = threading.Lock()

    def send(self, message: dict) -> None:
        with self._lock:
            assert self._proc.stdin is not None
            self._proc.stdin.write(json.dumps(message) + "\n")
            self._proc.stdin.flush()

    def recv(self) -> dict | None:
        assert self._proc.stdout is not None
        while True:
            line = self._proc.stdout.readline()
            if not line:
                return None
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except ValueError:
                # Not ours to interpret; skipping beats crashing the session.
                continue

    def close(self) -> None:
        self._proc.terminate()
