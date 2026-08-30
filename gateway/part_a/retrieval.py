"""Gating what comes *back*: retrieval, and the model's reply.

The prompt path asks "may this person send this". This asks the other question, and it is
the one an access-control system exists for: **may this person see this**.

    guard = RetrievalGuard(context)
    result = await guard.filter(documents, actor)
    result.visible      # what to hand the model
    result.withheld     # what was kept back, and under which rule

**Retrieval is not access control.** A vector store returns what is semantically nearest,
not what the caller is entitled to. Embedding-similarity has no notion of a clearance, so a
question about "employee benefits" will happily surface a named payslip. Filtering after
retrieval, by classifying what came back and asking the policy about it, is the part that
turns a search index into something a government agency can point at an auditor.

**Withheld documents never reach the model.** Masking a reply after the fact is too late:
the content is already in the context window, and the transcript keeps it. So this runs
between the retriever and the prompt, and the model is handed only what survived.

The classification is structural and advisory (`detect/documents.py`); the *decision* is
Part A's. That division is deliberate — a guess about what a document is should not also
be the authority on who may read it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gateway.detect.documents import classify


@dataclass(frozen=True, slots=True)
class Verdict:
    """One document, and what the policy said about it for this actor."""

    document_id: str
    action: str
    classes: tuple[str, ...] = ()
    rule_index: int | None = None
    rule_scope: str = "default"
    reason: str = ""

    @property
    def visible(self) -> bool:
        return self.action in ("allow", "warn")


@dataclass
class GuardResult:
    visible: list[Any] = field(default_factory=list)
    withheld: list[Verdict] = field(default_factory=list)
    verdicts: list[Verdict] = field(default_factory=list)
    #: The full Outcome behind each verdict that had findings, keyed by document id.
    #: The Verdict is what a caller shows a user; the Outcome is what the ledger needs,
    #: and a decision nobody can record is one Part A says we must not act on.
    outcomes: dict[str, Any] = field(default_factory=dict)

    def explain(self) -> str:
        """What to tell the user in place of the documents they did not get.

        Silence is the wrong answer: someone who cannot tell whether a search found
        nothing or found something they may not read will conclude the tool is broken and
        route around it. Naming the class and the rule -- never the content -- is enough
        to be actionable without leaking what was withheld.
        """
        if not self.withheld:
            return ""
        lines = [
            f"{len(self.withheld)} document(s) were withheld by policy, not omitted:"
        ]
        for v in self.withheld:
            lines.append(
                f"  - {v.document_id}: {', '.join(v.classes) or 'restricted'} "
                f"({v.action}, rule {v.rule_index} of the {v.rule_scope} policy)"
            )
        lines.append("Ask the owning group if you need access.")
        return "\n".join(lines)


class RetrievalGuard:
    """Filter retrieved documents through the inbound policy."""

    __slots__ = ("_ctx", "_min_confidence", "_classify")

    def __init__(self, context: Any, *, min_confidence: float = 0.0,
                 classifier: Any = None) -> None:
        self._ctx = context
        self._min_confidence = min_confidence
        # Injected so a caller with a stronger classifier can supply one. A file on disk
        # can be run through the *value* detectors as well as the structural ones -- a
        # bare column of Aadhaar numbers has no record vocabulary to match, so structure
        # alone would call it prose. A retriever's chunk usually cannot afford that scan;
        # a single file read can. See gateway/part_a/reading.py.
        self._classify = classifier or classify

    async def filter(self, documents: list[Any], actor: Any) -> GuardResult:
        """Classify each document, ask the policy, keep only what the actor may see."""
        result = GuardResult()
        for index, doc in enumerate(documents):
            doc_id, text = _unpack(doc, index)
            verdict, outcome = await self._judge(doc_id, text, actor)
            result.verdicts.append(verdict)
            if outcome is not None:
                result.outcomes[doc_id] = outcome
            if verdict.visible:
                result.visible.append(doc)
            else:
                result.withheld.append(verdict)
        return result

    async def _judge(self, doc_id: str, text: str, actor: Any):
        from zerotrace.spans.model import Finding

        found = [f for f in self._classify(text) if f.confidence >= self._min_confidence]
        if not found:
            return Verdict(doc_id, "allow"), None

        findings = [
            Finding(entity_class=f.entity_class, span_path=f"documents[{doc_id}]",
                    leg="inbound", confidence=f.confidence)
            for f in found
        ]
        outcome = await self._ctx.decide(findings, actor, leg="inbound")
        return Verdict(
            document_id=doc_id,
            action=outcome.action,
            classes=tuple(outcome.finding_classes),
            rule_index=outcome.rule_index,
            rule_scope=outcome.rule_scope,
            reason=f"{outcome.action} for {actor.id}",
        ), outcome


def _unpack(doc: Any, index: int) -> tuple[str, str]:
    """Accept the shapes a retriever actually returns.

    A dict with `text`/`content`/`page_content` covers LangChain, LlamaIndex and most
    hand-rolled stores; a bare string covers the rest. Being liberal here costs nothing
    and refusing to parse someone's retriever output would just mean the guard is skipped.
    """
    if isinstance(doc, str):
        return f"doc[{index}]", doc
    if isinstance(doc, dict):
        text = doc.get("text") or doc.get("content") or doc.get("page_content") or ""
        return str(doc.get("id") or doc.get("source") or f"doc[{index}]"), str(text)
    text = getattr(doc, "page_content", None) or getattr(doc, "text", "") or ""
    return str(getattr(doc, "id", f"doc[{index}]")), str(text)
