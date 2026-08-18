"""discovery-runtime — the generic Intent-Discovery runtime.

Turn a requester's words into a sealed ``VerifiedIntent``: multi-witness readers → fusion (agree /
disagree → open question) → clarification loop → seal (refuse while anything result-changing is
open). Domain-agnostic: parameterized by a schema + readers, it never knows what a dimension *means*.

Extracted from RAAAL/Quantify (the reference implementation that proved the design). Contracts live
in ``runtime-contracts``; finance semantics stay in wealth-manager; GRC is the second consumer.

    from discovery_runtime import DiscoveryRuntime
    rt = DiscoveryRuntime(schema=my_schema, readers=[MyRuleReader()])
    vi = rt.draft("…")
    for q in rt.clarifications(vi):
        vi = rt.resolve(vi, q.dimension, answer_for(q))
    vi = rt.seal(vi)          # raises NotSealable if anything result-changing is still open
"""
from __future__ import annotations

from runtime_contracts import (
    Amendment,
    DecisionEvidence,
    IntentState,
    NotSealable,
    Unresolved,
    VerifiedIntent,
)

from .intent import clarifications, draft_intent, interpreted, resolve
from .fusion import Decision, Fusion, Proposal, fuse, same_value
from .reader import Reader, Reading, merge_readings
from .runtime import DiscoveryRuntime
from .seal import digest, seal

__version__ = "0.1.9"

__all__ = [
    "DiscoveryRuntime",
    "Reader",
    "Reading",
    "merge_readings",
    "Fusion",
    "Proposal",
    "Decision",
    "fuse",
    "same_value",
    "draft_intent",
    "interpreted",
    "clarifications",
    "resolve",
    "seal",
    "digest",
    # re-exported canonical contracts (single owner = runtime-contracts)
    "VerifiedIntent",
    "DecisionEvidence",
    "Unresolved",
    "Amendment",
    "IntentState",
    "NotSealable",
]
