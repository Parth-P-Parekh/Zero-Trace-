"""Gating what the agent is about to *read* off this machine.

`session.decide_prompt` asks whether this person may **send** something. This asks the
other half of the question, on local files: may this person **see** this? It is the same
decision `retrieval.RetrievalGuard` makes about a vector store's chunks, pointed at the
retriever a coding agent actually has — the filesystem.

**Why this is a PreToolUse concern and not a PostToolUse one.** `zt_pretool`'s docstring
says, correctly, that PreToolUse sees a `Read`'s path and not its contents. That is true
of the *agent's* view. It is not true of ours: the hook is a local process with the same
filesystem access, so it can open the file itself, classify it, ask the policy, and refuse
— all before the tool runs and therefore before a single byte reaches the transcript.
Doing it afterwards would be too late in the only way that matters. A PostToolUse hook can
append a scolding message, but the content is already in the context window, the model has
already read it, and the transcript keeps it forever.

**Withholding is whole-file.** The policy's vocabulary is allow / warn / tokenize / mask /
block, and a hook's vocabulary is yes or no. So `mask` becomes a refusal here, recorded
with `mask_needs_proxy` — the decision on the record is the one the policy made, and the
degradation is a separate, visible fact. Moving *up* the lattice is the safe direction and
the one a business unit is allowed to take; silently serving a file the policy wanted
masked would be the other one.

**What it cannot see.** A path this cannot resolve is a path this cannot judge:
`curl | sh`, a file opened by a script the agent runs, an editor's own buffer. The
honest boundary is that this covers reads whose target is named in the tool call. Claiming
otherwise would be the same overreach the pretool hook was careful not to make.
"""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

#: Commands whose non-flag arguments are files being read. Deliberately short: `python`
#: and `node` take a script that then reads anything, so including them would promise a
#: coverage this cannot deliver, and a command like `cp` moves bytes without the agent
#: seeing them. What is here is the set whose whole purpose is to put a file's contents
#: on stdout, which is to say into the transcript.
READERS: frozenset[str] = frozenset({
    "cat", "bat", "head", "tail", "less", "more", "nl", "strings", "xxd", "od",
    "grep", "egrep", "fgrep", "rg", "ag", "ack", "jq", "yq", "column", "tac",
    "type", "get-content", "gc",
})

#: Arg names that hold a path, for tools we do not have a table for. MCP servers and
#: Codex's tool names are not ours to enumerate, and a server called `read_file` with a
#: `path` argument should be gated like `Read`.
PATH_KEYS: frozenset[str] = frozenset({
    "file_path", "filepath", "path", "notebook_path", "file", "filename", "target_file",
})

#: How much of a file to classify. A record announces itself in its header; reading a
#: gigabyte to find that out would make every `Read` slow to protect the rare huge file.
SAMPLE_BYTES = 64 * 1024

#: How many files a directory-shaped read expands to. `grep -r` over a tree is a read of
#: every file in it, and there has to be a ceiling somewhere.
MAX_FILES = 64

#: Extensions that hold no readable record. Skipping them is a real judgement -- a secret
#: could sit in a `.png` -- but classification works on text, and running the scanners
#: over binary produces noise, not findings.
BINARY_SUFFIXES: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz", ".tar",
    ".whl", ".exe", ".dll", ".so", ".dylib", ".pyc", ".woff", ".woff2", ".ttf", ".mp4",
})


@dataclass(frozen=True, slots=True)
class Withheld:
    """One file the actor may not read, and the rule that says so."""

    path: str
    action: str
    classes: tuple[str, ...]
    rule_index: int | None
    rule_scope: str


@dataclass(frozen=True, slots=True)
class ReadDecision:
    """What the policy said about this read, for this person."""

    allow: bool
    actor: str
    tenant: str
    groups: tuple[str, ...] = ()
    withheld: tuple[Withheld, ...] = ()

    @property
    def reason(self) -> str:
        """The refusal, naming the rule and never the contents.

        This string goes to the agent, so it is written to be useful to the *user* reading
        their terminal while telling the model nothing about what was in the file. The
        class name and the rule index are structural facts about the policy; they are
        already public in `Control-DB/policies/`.
        """
        if not self.actor:
            # No role was in play, so this was the credential floor and not a clearance
            # decision. Saying "you are not cleared" would send the reader to ask for an
            # access grant that does not exist and would not help.
            lines = [
                f"ZeroTrace withheld {len(self.withheld)} file(s) from this read: they "
                f"contain credentials. Nothing was read and nothing entered the "
                f"transcript. No role clears this -- a secret pulled into the context "
                f"window is in the transcript for good."
            ]
        else:
            who = f"{self.actor}" + (f" ({', '.join(self.groups)})" if self.groups
                                     else " (no clearance groups)")
            lines = [
                f"ZeroTrace withheld {len(self.withheld)} file(s) from this read: "
                f"{who} is not cleared for them. Nothing was read and nothing entered "
                f"the transcript."
            ]
        for w in self.withheld:
            lines.append(
                f"  - {w.path}: {', '.join(w.classes) or 'restricted'} "
                f"(rule {w.rule_index} of the {w.rule_scope} policy said {w.action})"
            )
        lines.append(
            "Do not attempt to read this another way. Ask the owning group for access, "
            "or `zerotrace login` as someone who holds it."
        )
        return "\n".join(lines)


# ------------------------------------------------------------ what is being read --

def candidate_paths(tool: str, args: dict) -> list[Path]:
    """Every existing file this tool call would put in front of the model.

    Returns files only. A directory is expanded, because `grep -r docs/` is a read of
    everything under `docs/` even though the tool call names one path.
    """
    raw: list[str] = []
    if tool == "Bash" or tool == "shell":
        raw.extend(_bash_paths(str(args.get("command") or "")))
    else:
        for key, value in args.items():
            if key.lower() in PATH_KEYS and isinstance(value, str) and value.strip():
                raw.append(value)
        # `Grep`'s haystack is its `path`, already covered above; its `pattern` is not a
        # file and must not be treated as one.

    out: list[Path] = []
    seen: set[Path] = set()
    for item in raw:
        for path in _expand(item):
            if path not in seen:
                seen.add(path)
                out.append(path)
            if len(out) >= MAX_FILES:
                return out
    return out


def _expand(item: str) -> list[Path]:
    text = item.strip().strip('"').strip("'").strip()
    # An empty token is not a path. `Path("")` is the *current directory*, so
    # `grep -c "" some_file` -- an empty pattern, a perfectly ordinary line count --
    # expanded to every file in the repository, `.git` included, and the read was judged
    # against all of it. Found when this gate blocked its own author counting lines.
    if not text:
        return []
    try:
        path = Path(text).expanduser()
    except (OSError, ValueError):
        return []
    try:
        if path.is_file():
            return [path] if _readable(path) else []
        if path.is_dir():
            return [p for p in sorted(path.rglob("*"))[: MAX_FILES * 4]
                    if p.is_file() and _readable(p)][:MAX_FILES]
    except OSError:
        return []
    return []


def _readable(path: Path) -> bool:
    return path.suffix.lower() not in BINARY_SUFFIXES


def _bash_paths(command: str) -> list[str]:
    """File arguments of the reading commands in a shell line.

    Split on the operators that start a new command so `ls && cat secrets` is two
    commands and only the second one is a read. `posix=False` keeps Windows backslashes
    intact, at the cost of leaving quotes on the tokens -- `_expand` strips those.
    """
    out: list[str] = []
    for part in _split_commands(command):
        try:
            tokens = shlex.split(part, posix=False)
        except ValueError:
            continue
        if not tokens:
            continue
        verb = Path(tokens[0].strip('"').strip("'")).name.lower()
        # A redirect reads a file whatever the command is: `while read x; do ...; done < f`
        for i, token in enumerate(tokens):
            if token == "<" and i + 1 < len(tokens):
                out.append(tokens[i + 1])
            elif token.startswith("<") and len(token) > 1 and not token.startswith("<<"):
                out.append(token[1:])
        if verb not in READERS:
            continue
        skip_next = False
        for token in tokens[1:]:
            if skip_next:
                skip_next = False
                continue
            # A redirect target is a destination, not a source. `cat >> notes.md <<EOF`
            # is a *write* whose verb happens to be a reader, and treating its target as
            # something being read was caught by this product refusing its own author's
            # append to a test file. Getting this wrong is not a small false positive:
            # it blocks ordinary writes on a reader's clearance.
            if token in (">", ">>", "1>", "2>", "&>", "|"):
                skip_next = token != "|"
                continue
            if token.startswith(">"):
                continue
            if token.startswith("-") or token == "<":
                continue
            out.append(token)
    return out


def _split_commands(command: str) -> list[str]:
    parts = [command]
    for sep in ("&&", "||", ";", "|", "\n"):
        parts = [chunk for part in parts for chunk in part.split(sep)]
    return [p.strip() for p in parts if p.strip()]


# ------------------------------------------------------------------ classifying --

def classify_file(text: str, *, scan: Any = None) -> list[Any]:
    """Structure *and* values: what kind of record this is, plus what is in it.

    `detect/documents.classify` answers "is this a payslip" from co-occurring field names.
    That misses the file which is nothing but a column of identifiers -- a register export
    has no prose to match, and calling it unclassified would let the most concentrated
    file in the corpus through. So the value detectors run too, and every class they name
    is folded in as a finding of its own.
    """
    from gateway.detect.documents import DocumentFinding, classify

    found = list(classify(text))
    named = {f.entity_class for f in found}
    for entity_class in (scan or value_classes)(text):
        if entity_class not in named:
            found.append(
                DocumentFinding(entity_class=entity_class, confidence=0.9,
                                matched=("value detector",))
            )
    return found


def value_classes(text: str) -> tuple[str, ...]:
    """The classes the ordinary detectors find in this text.

    Asks the warm daemon first. It already holds the compiled pack, and building a second
    one per file read would put the interpreter-startup cost back that the daemon exists
    to remove. `session_id=""` on purpose: a file's contents must not be carried into the
    cross-prompt reassembly window, or reading a config would poison the next prompt.

    **The daemon itself must not call this.** It would be asking itself over loopback,
    from inside its own request handler, and the nested `run_until_complete` on a loop
    that is already running took the whole daemon down rather than returning an error.
    The daemon passes `scan=_value_classes_local` instead -- see `classify_file`.
    """
    try:
        from hooks import daemon_client

        answer = daemon_client.ask(text[:SAMPLE_BYTES], "")
        if answer is not None:
            return tuple(answer.get("classes") or ())
    except Exception:  # noqa: BLE001
        pass
    return _value_classes_local(text)


#: The compiled pack, built at most once per process. Without this every file in a
#: directory read rebuilt it, which is the ~300ms the daemon exists to pay only once.
_CHECKER: Any = None


def _checker() -> Any:
    global _CHECKER
    if _CHECKER is None:
        from gateway.base.cache import NullSpanCache
        from gateway.base.checker import Checker, CheckerConfig
        from gateway.base.scanner import DetectorPack
        from gateway.detect.composite import scan_span_composite
        from gateway.detect.s0_credentials import scan_span_credentials
        from gateway.detectors import ALL_DETECTORS

        pack = DetectorPack.build(
            list(ALL_DETECTORS), version=1,
            scanners=[scan_span_credentials, scan_span_composite],
        )
        _CHECKER = Checker(pack, NullSpanCache(),
                           os.environ.get("ZT_VAULT_MASTER_KEY", "dev-key").encode(),
                           CheckerConfig.from_env())
    return _CHECKER


def _run(coro) -> Any:
    """Await a coroutine from synchronous code, running loop or not.

    `classify_file` is called from inside `RetrievalGuard.filter`, which is itself
    awaited -- so there is already a loop on this thread and `asyncio.run` raises. The
    first version of this swallowed that in a bare `except` and returned no classes at
    all, which meant the value detectors never ran and a file that was nothing but a
    column of identifiers classified as prose. A silent degradation to "found nothing"
    is the worst possible failure for a detector, so the loop question is answered
    explicitly here instead.
    """
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _value_classes_local(text: str) -> tuple[str, ...]:
    """The same answer without a daemon, for tests and for the daemon's own use."""
    try:
        from gateway.check import text_tree, to_verdict

        verdict = to_verdict(_run(_checker().check(text_tree(text[:SAMPLE_BYTES]), "read")))
        return tuple(verdict.classes)
    except Exception:  # noqa: BLE001
        # Losing the value scan costs one class of finding. The structural classifier has
        # already run, so the read is still judged -- just on less evidence. It is logged
        # rather than passed over in silence: this failing quietly is how the bug above
        # survived, and "found nothing" must never be indistinguishable from "did not
        # look".
        import logging

        logging.getLogger("gateway.part_a").warning(
            "the value scan failed on a read; judging on structure alone", exc_info=True
        )
        return ()


# --------------------------------------------------------------------- deciding --

def credential_files(paths: list[Path], *, scan: Any = None) -> list[Withheld]:
    """Files whose contents are a credential, judged without reference to any role.

    The prompt path already works this way: `zt_check` blocks a secret whether or not
    anyone has run `zerotrace login`, because a credential leaving is not a question about
    clearance. The read path did not, and the asymmetry was a real hole -- with no session
    there was no policy layer at all, so a `.env` full of live keys was pulled straight
    into the transcript. Anyone can find that in ten seconds by not logging in.

    So the CREDENTIAL family is enforced here unconditionally, ahead of and independent of
    the clearance decision. The family is read from the contract rather than listed here,
    so adding a credential class in one place cannot quietly create a readable secret in
    another -- the same reasoning, and the same source, as `zt_check._has_credential`.

    This deliberately does *not* cover the record classes. Whether a payslip may be read
    is a question about who is asking, and with nobody logged in there is no answer to
    it. Whether a private key may be read into a context window is not that kind of
    question.
    """
    from gateway.contracts.entity_classes import CLASS_TO_FAMILY, EntityClass

    def is_credential(name: str) -> bool:
        try:
            family = CLASS_TO_FAMILY[EntityClass(name)]
        except (KeyError, ValueError):
            # An unknown class is not assumed to be a credential here: this function runs
            # with no policy behind it, so a wrong guess blocks a read nobody can clear.
            return False
        return getattr(family, "value", str(family)) == "CREDENTIAL"

    scanner = scan or value_classes
    out: list[Withheld] = []
    for path in paths:
        text = _sample(path)
        if not text:
            continue
        found = tuple(sorted(c for c in set(scanner(text)) if is_credential(c)))
        if found:
            out.append(Withheld(path=_doc_id(path), action="block", classes=found,
                                rule_index=None, rule_scope="credential"))
    return out


def _credential_only(paths: list[Path], scan: Any) -> ReadDecision | None:
    """The floor that applies when the policy cannot answer.

    With no session, or a tenant nobody has seeded, there is no clearance layer -- and
    that used to mean no protection at all on this path, so a `.env` full of live keys
    was pulled straight into the transcript by anyone who had not run `zerotrace login`.

    Records stay unguarded here, because "may this person read a payslip" has no answer
    when there is no person. A credential is different: there is no role that makes a
    private key safe to pull into a context window, which is exactly why the outbound
    rule for credentials carries no clearance block either. Deny-by-default when the
    identity is unknown, explicit grant when it is known -- the policy still decides for
    a logged-in actor, including granting infosec its own runbooks.
    """
    creds = credential_files(paths, scan=scan)
    if not creds:
        return None
    return ReadDecision(allow=False, actor="", tenant="", groups=(),
                        withheld=tuple(creds))


async def decide_read(paths: list[Path], *, plane: dict | None = None,
                      scan: Any = None) -> ReadDecision | None:
    """Judge every file this read would surface. None when there is no role in play.

    None rather than an exception when nobody has logged in or the tenant is not seeded:
    the clearance layer is an addition to the credential check, not a replacement for it,
    and failing a read because an operator skipped `zerotrace seed` would be punishing the
    user for our setup step. That is the same rule `decide_prompt` follows.

    `plane` is a caller-owned dict the daemon uses to keep the store handle across calls.
    Building it measured at ~397ms, which is most of the cost of a gated read, and it is
    pure plumbing -- the session, the actor and the policy are read fresh below, every
    time, so caching it cannot make a stale decision. Callers that do not have a long
    life pass nothing and get a fresh one.
    """
    if not paths:
        return None

    from gateway.part_a.context import PartAContext
    from gateway.part_a.retrieval import RetrievalGuard
    from gateway.part_a.session import current
    from gateway.part_a.session import plane as build_plane

    session = current()
    if session is None:
        return _credential_only(paths, scan)

    if plane is None:
        p = build_plane()
    else:
        if "p" not in plane:
            plane["p"] = build_plane()
        p = plane["p"]

    if not await p.store.tenant_exists(session.tenant):
        return _credential_only(paths, scan)

    ctx = PartAContext(p.store, p.ledger)
    actor = await ctx.resolve(session.tenant, session.actor)

    documents = [{"id": _doc_id(path), "text": _sample(path)} for path in paths]
    documents = [d for d in documents if d["text"]]
    if not documents:
        return None

    guard = RetrievalGuard(
        ctx, classifier=lambda text: classify_file(text, scan=scan)
    )
    result = await guard.filter(documents, actor)

    withheld = tuple(
        Withheld(path=v.document_id, action=v.action, classes=v.classes,
                 rule_index=v.rule_index, rule_scope=v.rule_scope)
        for v in result.withheld
    )
    await _record(ctx, result)

    return ReadDecision(
        allow=not withheld,
        actor=actor.id,
        tenant=session.tenant,
        groups=tuple(getattr(actor, "groups", ()) or ()),
        withheld=withheld,
    )


async def _record(ctx: Any, result: Any) -> None:
    """Append every decision with findings to the ledger.

    A read that was allowed is evidence too: "who looked at the payslip and was cleared
    for it" is the question an auditor asks second, right after "who was refused".
    """
    import uuid

    blocked = {v.document_id for v in result.withheld}
    for doc_id, outcome in result.outcomes.items():
        if doc_id in blocked and outcome.action == "mask":
            # A hook can withhold a file or serve it; it cannot serve half of one. The
            # policy's intent stays on the record and the degradation is named beside it.
            outcome = replace(
                outcome, action="block",
                degraded_reasons=tuple(outcome.degraded_reasons) + ("mask_needs_proxy",),
            )
        try:
            await ctx.record(outcome, request_id=f"read-{uuid.uuid4().hex[:12]}",
                             model="cli")
        except Exception:  # noqa: BLE001
            # The read has already been refused by this point. Losing the record is bad
            # and is logged upstream; turning it into an unhandled exception would turn a
            # correct refusal into a crash.
            pass


def _sample(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return fh.read(SAMPLE_BYTES)
    except OSError:
        return ""


def _doc_id(path: Path) -> str:
    """A short, stable name for the file.

    Relative to the working directory when it sits underneath it, because that is what
    the user typed and what they will recognise. Capped at 180 characters: the ledger
    rejects a `finding_paths` entry over 200 on the grounds that anything that long is
    probably a value that leaked into a path field, and it is right to.
    """
    try:
        text = str(path.resolve().relative_to(Path.cwd()))
    except (OSError, ValueError):
        text = str(path)
    return text if len(text) <= 180 else "..." + text[-177:]
