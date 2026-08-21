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
        vi = rt.resolve(vi, q.field, answer_for(q))
    vi = rt.seal(vi)          # raises SealError if anything result-changing is still open

v0.2.x adds an **incremental** path beside the stateless sealer: given an explicit ``EvidenceChange``
set and a version-aware ``DiscoveryCheckpoint`` ``{evidence_position, policy_version,
capability_set_version}``, ``discover_incremental`` re-derives ONLY the conclusions the change (or a
policy/capability bump) affects — marking them STALE (re-evaluate) or INVALIDATED (basis gone) — while
the rest stay VERIFIED. ``discover_full`` is the rescan baseline (Benchmark B). Not a stream processor.
"""
from __future__ import annotations

from runtime_contracts.intent import (
    Amendment,
    DecisionEvidence,
    IntentState,
    SealError,
    Unresolved,
    VerifiedIntent,
)

from .intent import clarifications, draft_intent, resolve
from .reader import Reader, Reading, merge_readings
from .runtime import DiscoveryRuntime
from .seal import digest, seal
from .incremental import (
    DiscoveryCheckpoint,
    IncrementalReport,
    IncrementalResult,
    classify,
    discover_incremental,
    discover_full,
    evidence_ids,
    mark_stale,
    mark_invalidated,
)

__version__ = "0.2.0"

__all__ = [
    "DiscoveryRuntime",
    "Reader",
    "Reading",
    "merge_readings",
    "draft_intent",
    "clarifications",
    "resolve",
    "seal",
    "digest",
    # incremental Discovery (Slice 3)
    "DiscoveryCheckpoint",
    "IncrementalReport",
    "IncrementalResult",
    "classify",
    "discover_incremental",
    "discover_full",
    "evidence_ids",
    "mark_stale",
    "mark_invalidated",
    # re-exported canonical contracts (single owner = runtime-contracts)
    "VerifiedIntent",
    "DecisionEvidence",
    "Unresolved",
    "Amendment",
    "IntentState",
    "SealError",
]
