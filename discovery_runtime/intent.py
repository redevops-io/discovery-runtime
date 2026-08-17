"""Build a ``VerifiedIntent`` from a reading, drive the "what did you mean?" clarification loop, and
record client answers. The seal refuses while any result-changing dimension is open — so a
half-understood request can never look settled.

**Ported onto the contract as it is, not as this package remembered it.** An earlier version built
``VerifiedIntent(interpreted=<dict>, request_text=…, evidence=<flat tuple>)`` and walked dotted
paths into that dict. The contract has no ``interpreted`` and no top-level ``evidence``: it has
``fields``, a mapping from dimension name to ``IntentField``, and each field carries its own
evidence, author and provenance. That is not a cosmetic difference — it is where authorship lives,
and authorship is the thing the seal exists to protect.

So the domain's ``canonicalize`` still turns an opaque payload into a plain mapping, and this module
turns that mapping into ``IntentField`` entries, attaching the evidence the readers filed under each
name.
"""
from __future__ import annotations

import copy
from typing import Any, Callable, Dict, List, Mapping

from runtime_contracts import (
    Amendment,
    Author,
    DecisionEvidence,
    IntentField,
    ReaderKind,
    Unresolved,
    VerifiedIntent,
)

from .reader import Reader, Reading, merge_readings

#: Turns a reader's domain payload into a plain mapping of dimension -> value. The default assumes
#: the payload is already dict-like; a domain injects one that serializes its typed policy.
Canonicalize = Callable[[Any], Dict[str, Any]]
FusionPolicy = Callable[[List[Reading]], Reading]

#: What this package stamps on the fields it produces, so a stored intent can say which runtime
#: drafted it without the caller having to remember.
PRODUCED_BY = "discovery-runtime@0.3.0"


def _default_canonicalize(payload: Any) -> Dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, Mapping):
        return dict(copy.deepcopy(payload))
    if hasattr(payload, "__dataclass_fields__"):
        from dataclasses import asdict

        return asdict(payload)
    if hasattr(payload, "__dict__"):
        return copy.deepcopy(vars(payload))
    raise TypeError(
        f"cannot canonicalize payload of type {type(payload)!r}; inject a canonicalize()"
    )


def draft_intent(
    text: str,
    readers: List[Reader] | None,
    *,
    objective: str = "",
    canonicalize: Canonicalize = _default_canonicalize,
    fusion_policy: FusionPolicy = merge_readings,
) -> VerifiedIntent:
    """Run the readers, fuse them, and draft an unsealed ``VerifiedIntent``.

    Domain-agnostic: ``readers`` and ``canonicalize`` are the only domain knowledge and both are
    injected. ``objective`` is the one thing the contract requires and the runtime cannot invent —
    what the request is *for* is a domain statement.
    """
    if not readers:
        raise ValueError("draft_intent needs at least one reader")

    reading = fusion_policy([r.read(text) for r in readers])
    interpreted = canonicalize(reading.payload)

    contested = {u.dimension for u in reading.unresolved if u.result_changing}

    fields: Dict[str, IntentField] = {}
    for name, value in interpreted.items():
        evidence = tuple(reading.evidence.get(name, ()))
        fields[name] = IntentField(
            value=value,
            # `READER`, not `MODEL`: which reader produced it is recorded per piece of evidence,
            # and a value that came out of fusion is the readers' collectively. Claiming MODEL for
            # a rule-derived value would overstate what said it.
            author=Author.READER,
            produced_by=PRODUCED_BY,
            source_span=evidence[0].source_ref if evidence else "",
            evidence=evidence,
            # Recorded on the field as well as raised as a question. A caller that renders fields
            # without reading `unresolved` still sees that this one is disputed.
            contested=name in contested,
        )

    return VerifiedIntent(
        objective=objective,
        fields=fields,
        relations=tuple(reading.relations),
        unresolved=tuple(reading.unresolved),
        produced_by=PRODUCED_BY,
        utterance_ref=utterance_ref(text),
    )


def utterance_ref(text: str) -> str:
    """A stable handle for the request, without carrying the request.

    The contract holds a reference and never the prose, which is what makes "nothing downstream
    re-reads the words" a property of the artifact rather than a rule to remember.
    """
    from hashlib import sha256

    return "utt-" + sha256(text.encode()).hexdigest()[:16]


def clarifications(vi: VerifiedIntent) -> List[Unresolved]:
    """The open "what did you mean?" questions to put to the requester, in order.

    ``unsealable`` rather than ``blocking``. The two differ and the difference matters here:
    ``blocking`` is what stops *execution*, while ``unsealable`` is what stops *sealing* — which is
    broader, because a dimension nobody was asked about does not prevent a run from being attempted
    but does prevent the intent from claiming to be understood. Asking only the narrower set would
    let the loop end with questions outstanding and the seal then refuse, which is a clarification
    loop that never converges.
    """
    return list(vi.unsealable)


def interpreted(vi: VerifiedIntent) -> Dict[str, Any]:
    """The settled dimensions as a plain mapping of name to value.

    The contract stores each dimension as an ``IntentField`` carrying its author, provenance and
    evidence; this is the view that drops all of that. Useful for comparing two intents' *meaning*,
    and deliberately not what identity is computed from — two intents can agree on every value and
    differ in who said them, and those are not the same intent.
    """
    return {name: field.value for name, field in vi.fields.items()}


def resolve(vi: VerifiedIntent, dimension: str, value: Any) -> VerifiedIntent:
    """Record the requester's authoritative answer to an open question.

    Sets the field authored ``USER``, drops the matching ``Unresolved``, and logs an amendment with
    the evidence for it. The requester is always the author, and ``USER`` dominates every other
    author — which is why this is the only path that may assign it, and why a value the requester
    did not state must never arrive here.

    Returns a NEW ``VerifiedIntent``: the contract is frozen, and identity is content rather than a
    mutable cell.
    """
    from dataclasses import replace

    previous = vi.value(dimension)

    evidence = DecisionEvidence(
        reader_id="client",
        kind=ReaderKind.HUMAN,
        value=value,
        source_ref="client_answer",
    )

    fields = dict(vi.fields)
    fields[dimension] = IntentField(
        value=value,
        author=Author.USER,
        produced_by=PRODUCED_BY,
        source_span="client_answer",
        evidence=(evidence,),
        # Answered, so no longer disputed. The disagreement stays visible in the amendment log and
        # in the earlier evidence; what changes is that there is now an author who outranks it.
        contested=False,
    )

    return replace(
        vi,
        fields=fields,
        unresolved=tuple(u for u in vi.unresolved if u.dimension != dimension),
        amendments=vi.amendments
        + (Amendment(dimension=dimension, from_value=previous, to_value=value,
                     author=Author.USER),),
    )
