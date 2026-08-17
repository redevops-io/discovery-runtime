"""Sealing and identity — both delegated to the contract that defines them.

This module used to implement both itself: a hand-rolled ``digest`` over a hand-picked payload, and
a ``seal`` that re-derived which dimensions block. Neither is this package's decision to make.
``runtime_contracts.VerifiedIntent`` already answers "is this sealable", "what blocks it", and
"what is its identity", and every consumer of the contract has to agree on those answers or a plan
sealed by one is not the plan another reads back.

Two implementations of "sealed" is exactly the duplication this runtime was extracted to remove. So
what is left here is the two names the runtime's API promises, forwarding to the contract:

    seal(vi)     -> vi.seal()          raises NotSealable while anything result-changing is open
    digest(vi)   -> vi.intent_hash     content identity, defined by the contract's canonical form

Keeping the functions rather than telling callers to use the methods is deliberate: they are part of
this package's published surface, and a domain that imports them should not have to change when the
contract moves a method.
"""
from __future__ import annotations

from runtime_contracts import VerifiedIntent


def digest(vi: VerifiedIntent) -> str:
    """The intent's content identity, as the contract computes it.

    Not a hash taken here over a payload assembled here. Identity has to be the same number in
    every runtime that speaks this contract, and the only way to guarantee that is for one of them
    to define it.
    """
    return vi.intent_hash


def seal(vi: VerifiedIntent) -> VerifiedIntent:
    """DRAFT → VERIFIED, refusing while any result-changing dimension is open.

    Idempotent: sealing a sealed intent returns it unchanged rather than raising, so a caller that
    cannot cheaply tell whether it has already sealed does not have to guess.

    Raises ``NotSealable`` otherwise — the contract's own error, naming the open dimensions. This
    package previously raised a ``SealError`` of its own, which no other consumer of the contract
    could catch.
    """
    if vi.is_verified:
        return vi
    return vi.seal()
