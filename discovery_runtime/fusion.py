"""What two readers agreeing actually means, and what it means when they do not.

Extracted from RAAAL/Quantify's fusion, which had the semantics this package
was missing. The previous fusion here compared ``repr(value)``, so two readers
that meant the same thing in different notation — ``'500'`` and ``500`` — were
recorded as a disagreement and became a clarification question nobody needed to
be asked. That is worse than an unhelpful question: it is a loop that appears
whenever a deterministic reader normalises and a model does not.

**Generic machinery, domain comparison rules.** ``TEXT`` and ``SET`` are
implemented here because "exactly equal" and "the same tokens in any order" are
not domain facts. Everything else — what ``£2.5k`` is worth, whether
``12-month`` is a duration — is a domain fact, so a mode is a *name* here and
its meaning arrives as an injected normaliser. Nothing in this module knows
about money.

**Nothing here can make two different values equal.** ``TEXT`` stays exact,
because assuming two spellings mean the same thing is the failure this design
exists to prevent. A normaliser that returns ``None`` means "I cannot read
this", and an unreadable value is never equal to anything — including another
unreadable one.

**Four outcomes, not one.** ``DISAGREE``, ``INSUFFICIENT_RELATION`` and
``AMBIGUOUS_BY_LANGUAGE`` are kept apart because they call for different
repairs: adjudication, a binding nobody supplied, and a question to the person
respectively. Collapsing them into ``UNRESOLVED`` makes the record say
"something was wrong" and stop there.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Optional, Sequence

#: Turns a written value into something comparable, or ``None`` if it cannot
#: read it. Supplied per mode by the domain: the runtime names the mode, the
#: domain says what the mode means.
Normalizer = Callable[[str], Any]


class Fusion(str, Enum):
    """What fusion concluded about one dimension."""

    AGREE = "AGREE"
    """The readers pointed at the same value, by the schema's own rule."""

    DISAGREE = "DISAGREE"
    """They point at different values, or one proposed a value the other never
    mentioned. Never resolved by score: a confidence number is a reader's
    opinion of itself, and preferring the higher one is picking a winner in a
    disagreement nobody adjudicated."""

    INSUFFICIENT_RELATION = "INSUFFICIENT_RELATION"
    """The value cannot mean anything without a binding nobody supplied — three
    ratios and three accounts, with nothing saying which belongs to which."""

    AMBIGUOUS_BY_LANGUAGE = "AMBIGUOUS_BY_LANGUAGE"
    """The words carry both readings in attested usage. Not a parser failure
    and not a model failure — a question for the person who wrote them."""

    @property
    def proceeds(self) -> bool:
        return self is Fusion.AGREE


@dataclass(frozen=True)
class Proposal:
    """One reader's answer for one dimension, with who said it."""

    value: Any
    reader_id: str = ""
    source_ref: str = ""


@dataclass(frozen=True)
class Decision:
    """Fusion's conclusion for one dimension, and why."""

    dimension: str
    outcome: Fusion
    value: Any = None
    detail: str = ""
    proposals: Sequence[Proposal] = field(default_factory=tuple)

    @property
    def proceeds(self) -> bool:
        return self.outcome.proceeds


def same_value(one: Any, other: Any, mode: str = "TEXT", *,
               normalizers: Optional[Mapping[str, Normalizer]] = None) -> bool:
    """Whether two readers said the same thing, by the mode's rule.

    ``mode`` names how this dimension compares; ``normalizers`` says what the
    name means. An unknown mode falls back to ``TEXT`` rather than raising —
    the safe direction, because TEXT is exact and the cost of falling back is a
    disagreement reported that a domain rule might have reconciled, not an
    agreement invented.
    """
    left, right = str(one).strip(), str(other).strip()
    if left.lower() == right.lower():
        return True

    if mode == "SET":
        return _tokens(left) == _tokens(right)

    reader = (normalizers or {}).get(mode)
    if reader is None:
        # TEXT, or a mode nobody supplied a rule for. Exact, and already
        # checked above.
        return False

    try:
        a, b = reader(left), reader(right)
    except Exception:                                          # noqa: BLE001
        # A normaliser that raises has not said the values are equal.
        return False

    if a is None or b is None:
        # Unreadable is not a value. Two things a normaliser could not read are
        # not thereby the same thing — that would make every pair of nonsense
        # strings agree.
        return False
    return a == b


def _tokens(raw: str) -> frozenset:
    """Unordered, case-folded, punctuation-separated."""
    import re

    return frozenset(t for t in re.split(r"[,;/\s]+", raw.lower()) if t)


def fuse(dimension: str, proposals: Sequence[Proposal], *,
         mode: str = "TEXT",
         normalizers: Optional[Mapping[str, Normalizer]] = None,
         contradicted_by: Optional[str] = None,
         requires_binding: bool = False,
         ambiguous_between: Sequence[str] = ()) -> Decision:
    """Fuse every reader's answer for one dimension into one decision.

    Order of judgement matters and is deliberate. A dimension that cannot mean
    anything without a binding is not *disagreed* about — the readers may agree
    perfectly and the value still be unusable — so that is settled first. A
    contradiction against the words themselves outranks agreement between
    readers, because two readers agreeing on something the sentence contradicts
    is two readers making the same mistake.
    """
    proposals = tuple(p for p in proposals if p is not None)

    if not proposals:
        return Decision(dimension, Fusion.DISAGREE,
                        detail="no reader proposed a value")

    if requires_binding:
        return Decision(
            dimension, Fusion.INSUFFICIENT_RELATION, proposals=proposals,
            detail=f"{dimension} needs a binding that nothing supplied")

    if contradicted_by:
        return Decision(
            dimension, Fusion.DISAGREE, proposals=proposals,
            detail=f"the words contradict it: {contradicted_by}")

    if ambiguous_between:
        return Decision(
            dimension, Fusion.AMBIGUOUS_BY_LANGUAGE, proposals=proposals,
            detail="the words carry both readings: "
                   + " | ".join(ambiguous_between))

    first = proposals[0]
    for other in proposals[1:]:
        if not same_value(first.value, other.value, mode,
                          normalizers=normalizers):
            return Decision(
                dimension, Fusion.DISAGREE, proposals=proposals,
                detail=f"{first.reader_id or 'one reader'} read "
                       f"{first.value!r} and "
                       f"{other.reader_id or 'another'} read {other.value!r}")

    return Decision(dimension, Fusion.AGREE, value=first.value,
                    proposals=proposals)
