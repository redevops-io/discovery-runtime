"""Build a ``VerifiedIntent`` from a reading, drive the "what did you mean?" clarification loop, and
record client answers. The seal (``seal.py``) refuses while any result-changing dimension is open —
so a half-understood request can never look settled.

Extracted from ``wealth-manager/wealth_manager/discovery/intent.py`` and ported onto the reconciled,
**domain-free** ``runtime_contracts.VerifiedIntent`` (which carries a schema-agnostic ``interpreted``
dict instead of a finance ``ClientPolicy``). The dotted-path helpers are generic — they walk any
``dict``/object graph — so no domain accessor needs to be injected.
"""
from __future__ import annotations

import copy
from dataclasses import replace
from typing import Any, Callable

from runtime_contracts.intent import (
    Amendment,
    DecisionEvidence,
    Unresolved,
    VerifiedIntent,
)

from .reader import Reader, Reading, merge_readings

# A canonicalizer turns a reader's domain payload into the sealed ``interpreted`` dict. The default
# assumes the payload is already a plain dict; a domain injects one that serializes its typed policy.
Canonicalize = Callable[[Any], dict[str, Any]]
FusionPolicy = Callable[[list[Reading]], Reading]


def _default_canonicalize(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return copy.deepcopy(payload)
    if hasattr(payload, "__dataclass_fields__"):
        from dataclasses import asdict

        return asdict(payload)
    if hasattr(payload, "__dict__"):
        return copy.deepcopy(vars(payload))
    raise TypeError(f"cannot canonicalize payload of type {type(payload)!r}; inject a canonicalize()")


def draft_intent(
    text: str,
    readers: list[Reader] | None,
    *,
    canonicalize: Canonicalize = _default_canonicalize,
    fusion_policy: FusionPolicy = merge_readings,
) -> VerifiedIntent:
    """Run the readers, fuse them, and draft an unsealed ``VerifiedIntent``. Domain-agnostic:
    ``readers`` + ``canonicalize`` are the only domain knowledge, and both are injected."""
    if not readers:
        raise ValueError("draft_intent needs at least one reader")
    reading = fusion_policy([r.read(text) for r in readers])
    return VerifiedIntent(
        interpreted=canonicalize(reading.payload),
        request_text=text,
        evidence=tuple(reading.evidence),
        unresolved=tuple(reading.unresolved),
    )


def clarifications(vi: VerifiedIntent) -> list[Unresolved]:
    """The open "what did you mean?" questions to put to the requester, in order."""
    return vi.open_result_changing()


def resolve(vi: VerifiedIntent, field: str, value: Any) -> VerifiedIntent:
    """Record the requester's authoritative answer to an open question: set the interpreted field,
    drop the matching ``Unresolved``, and log an amendment + evidence. The requester is always the
    author. Returns a NEW ``VerifiedIntent`` (the contract is frozen — identity is content, not a
    mutable cell)."""
    interpreted = copy.deepcopy(vi.interpreted)
    old = _get_field(interpreted, field)
    _set_field(interpreted, field, value)
    unresolved = tuple(u for u in vi.unresolved if u.field != field)
    amendments = vi.amendments + (Amendment(field=field, old=old, new=value, by="client"),)
    evidence = vi.evidence + (
        DecisionEvidence(field=field, value=value, source_type="policy",
                         source_ref="client_answer", confidence=1.0),
    )
    return replace(vi, interpreted=interpreted, unresolved=unresolved,
                   amendments=amendments, evidence=evidence)


def _get_field(obj: Any, dotted: str) -> Any:
    for p in dotted.split("."):
        obj = obj.get(p) if isinstance(obj, dict) else getattr(obj, p, None)
        if obj is None:
            return None
    return obj


def _set_field(obj: Any, dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    for p in parts[:-1]:
        nxt = obj.get(p) if isinstance(obj, dict) else getattr(obj, p, None)
        if nxt is None:
            nxt = {}
            if isinstance(obj, dict):
                obj[p] = nxt
            else:
                setattr(obj, p, nxt)
        obj = nxt
    last = parts[-1]
    if isinstance(obj, dict):
        obj[last] = value
    else:
        setattr(obj, last, value)
