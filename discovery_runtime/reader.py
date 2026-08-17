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
from typing import Any, Dict, List, Protocol

from runtime_contracts import DecisionEvidence, Unresolved

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


class Reader(Protocol):
    """Anything that turns text into a ``Reading``.

    ``kind`` labels its evidence (``ReaderKind.RULE``, ``ReaderKind.MODEL``, …) so fusion can
    report *who* said what — never to privilege one source over another.
    """

    reader_id: str
    kind: Any

    def read(self, text: str) -> Reading: ...


def merge_readings(readings: List[Reading]) -> Reading:
    """Fuse readers. Agreement on a material field is kept; disagreement makes the field
    ``Unresolved`` (a "what did you mean?" question). No reader is privileged.

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

    # Compared by canonical value, not by the evidence object: two readers that agree agree even
    # when they cite different spans and carry different confidences.
    contested = []
    for name, items in merged.items():
        distinct = {repr(item.value) for item in items}
        if len(distinct) > 1:
            contested.append(
                Unresolved(
                    dimension=name,
                    reason=_disagreement_reason(),
                    detail=f"readers disagree on {name}: {sorted(distinct)}",
                    evidence=tuple(items),
                    result_changing=True,
                )
            )

    return Reading(
        payload=base.payload,
        evidence=merged,
        unresolved=list(base.unresolved) + contested,
    )


def _disagreement_reason():
    """``UNRESOLVED_DISAGREEMENT`` — named through the contract rather than spelled here."""
    from runtime_contracts import OpenReason

    return OpenReason.UNRESOLVED_DISAGREEMENT
