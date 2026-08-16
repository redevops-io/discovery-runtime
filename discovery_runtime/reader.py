"""Readers turn a request's words into a *reading*: a domain draft (opaque ``payload``), a
``DecisionEvidence`` per material field, and an ``Unresolved`` per result-changing dimension the
words imply but do not pin. The seal (``seal.py``) then refuses until nothing result-changing is
open.

Two-reader discipline (extracted from RAAAL/Quantify): a deterministic reader is the default; a
model reader can be plugged in as a second reader. **No reader is privileged** — when two readers
disagree on a material field, that field becomes ``Unresolved`` (a "what did you mean?" question),
never silently resolved. The runtime is domain-agnostic: the ``payload`` is whatever the domain's
readers produce (a portfolio policy, a GRC intent, …); only the domain's readers know what it means.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from runtime_contracts.intent import DecisionEvidence, Unresolved


@dataclass
class Reading:
    """One reader's (or the fused) interpretation. ``payload`` is the domain's draft object — the
    runtime never inspects it; a domain ``canonicalize`` turns it into the sealed ``interpreted``
    dict at draft time."""
    payload: Any
    evidence: list[DecisionEvidence] = field(default_factory=list)
    unresolved: list[Unresolved] = field(default_factory=list)


class Reader(Protocol):
    """A reader is any object that turns text into a ``Reading``. ``source_type`` labels its
    evidence (``rule`` | ``model`` | …) so fusion can report *who* said what — never to privilege
    one source over another."""
    source_type: str

    def read(self, text: str) -> Reading: ...


def merge_readings(readings: list[Reading]) -> Reading:
    """Fuse readers. Agreement on a material field is kept; disagreement makes the field
    ``Unresolved`` (a "what did you mean?" question). No ``source_type`` is privileged.

    Pure function — same readings in, same fused reading out. This is the functional core of
    multi-witness discovery; the runtime shell only decides *which* readers run.
    """
    if not readings:
        return Reading(payload=None)
    if len(readings) == 1:
        return readings[0]
    base = readings[0]
    by_field: dict[str, set[str]] = {}
    for r in readings:
        for e in r.evidence:
            by_field.setdefault(e.field, set()).add(repr(e.value))
    extra_unresolved: list[Unresolved] = []
    for f, vals in by_field.items():
        if len(vals) > 1:
            extra_unresolved.append(
                Unresolved(f, f"readers disagree on {f}: {sorted(vals)}", result_changing=True)
            )
    all_evidence = [e for r in readings for e in r.evidence]
    all_unresolved = list(base.unresolved) + extra_unresolved
    return Reading(payload=base.payload, evidence=all_evidence, unresolved=all_unresolved)
