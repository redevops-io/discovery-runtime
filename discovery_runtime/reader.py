"""Readers turn a request's words into a *reading*: a domain draft (opaque ``payload``), the
evidence for each material field, and an ``Unresolved`` per result-changing dimension the words
imply but do not pin. The seal (``seal.py``) then refuses until nothing result-changing is open.

Two-reader discipline (extracted from RAAAL/Quantify): a deterministic reader is the default; a
model reader can be plugged in as a second reader. **No reader is privileged** — when two readers
disagree on a material field, that field becomes ``Unresolved`` (a "what did you mean?" question),
never silently resolved. The runtime is domain-agnostic: the ``payload`` is whatever the domain's
readers produce (a portfolio policy, a GRC intent, …); only the domain's readers know what it means.

**Evidence is filed under the field it supports, not carried inside it.** ``Reading.evidence`` is a
mapping from field name to the evidence for that field, which is the shape
``runtime_contracts`` uses: ``VerifiedIntent.fields`` maps a name to an ``IntentField`` and the
evidence hangs off that. An earlier version of this module put a ``field`` attribute on
``DecisionEvidence`` itself and kept a flat list. The canonical contract has no such attribute, and
adding one back would mean a piece of evidence could name a field other than the one it is filed
under — two answers to "which field is this about" and no rule for which wins.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Protocol

from runtime_contracts import DecisionEvidence, Unresolved

from .fusion import Fusion, Proposal, fuse

#: Evidence, by the field it supports.
EvidenceByField = Dict[str, List[DecisionEvidence]]


@dataclass
class Reading:
    """One reader's (or the fused) interpretation.

    ``payload`` is the domain's draft object — the runtime never inspects it; a domain
    ``canonicalize`` turns it into the sealed field mapping at draft time.
    """

    payload: Any
    evidence: EvidenceByField = field(default_factory=dict)
    unresolved: List[Unresolved] = field(default_factory=list)
    #: Relations the reader established between values — "this ratio belongs to
    #: that account", not "this dimension has that value".
    #:
    #: Carried because the contract carries them: `VerifiedIntent.relations` is
    #: inside `canonical_form`, so an intent that drops them is a different
    #: request. Two readings naming the same instruments in different roles are
    #: not the same reading, and a runtime that only moved dimensions would
    #: lose that distinction silently.
    #:
    #: The runtime does not interpret them. What a relation *kind* means, and
    #: how one is found in a sentence, are the domain's; this only ensures they
    #: survive the journey from reader to sealed artifact.
    relations: List[Any] = field(default_factory=list)


class Reader(Protocol):
    """Anything that turns text into a ``Reading``.

    ``kind`` labels its evidence (``ReaderKind.RULE``, ``ReaderKind.MODEL``, …) so fusion can
    report *who* said what — never to privilege one source over another.
    """

    reader_id: str
    kind: Any

    def read(self, text: str) -> Reading: ...


def merge_readings(readings: List[Reading], *,
                   compare_as: Optional[Mapping[str, str]] = None,
                   normalizers: Optional[Mapping[str, Any]] = None) -> Reading:
    """Fuse readers. Agreement on a material field is kept; disagreement makes the field
    ``Unresolved`` (a "what did you mean?" question). No reader is privileged.

    ``compare_as`` maps a dimension to the name of its comparison rule and ``normalizers`` says
    what those names mean — both supplied by the domain, because whether ``£2.5k`` and ``2500``
    are the same number is a domain fact and this module does not know about money.

    Pure function — same readings in, same fused reading out. This is the functional core of
    multi-witness discovery; the runtime shell only decides *which* readers run.
    """
    if not readings:
        return Reading(payload=None)
    if len(readings) == 1:
        return readings[0]

    base = readings[0]

    merged: EvidenceByField = {}
    for reading in readings:
        for name, items in reading.evidence.items():
            merged.setdefault(name, []).extend(items)

    # Judged by the schema's comparison rule, not by `repr`. Comparing
    # representations made `'500'` and `500` a disagreement, so a deterministic
    # reader that normalises and a model that does not produced a clarification
    # question on every amount they both got right.
    contested = []
    for name, items in merged.items():
        decision = fuse(
            name,
            [Proposal(value=item.value, reader_id=item.reader_id,
                      source_ref=item.source_ref) for item in items],
            mode=(compare_as or {}).get(name, "TEXT"),
            normalizers=normalizers,
        )
        if not decision.proceeds:
            contested.append(
                Unresolved(
                    dimension=name,
                    reason=_reason_for(decision.outcome),
                    detail=decision.detail,
                    evidence=tuple(items),
                    result_changing=True,
                )
            )

    # Relations from every reader, in order, de-duplicated by identity. A
    # relation two readers both found is one relation, not corroboration to be
    # counted twice.
    relations = []
    for reading in readings:
        for relation in reading.relations:
            if relation not in relations:
                relations.append(relation)

    return Reading(
        payload=base.payload,
        evidence=merged,
        unresolved=list(base.unresolved) + contested,
        relations=relations,
    )


def _reason_for(outcome: Fusion):
    """The contract's reason for a fusion outcome.

    A language ambiguity and a reader disagreement are both open questions and
    they are not the same open question — one is answered by the person saying
    which they meant, the other by adjudicating two readers. The contract has
    one enum for why a dimension is open, so this is where the distinction is
    carried across; the fuller detail travels in ``Unresolved.detail``.
    """
    from runtime_contracts import OpenReason

    if outcome is Fusion.AMBIGUOUS_BY_LANGUAGE:
        return OpenReason.NOT_ASKED
    return OpenReason.UNRESOLVED_DISAGREEMENT
