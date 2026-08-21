"""Incremental Discovery — operate from a checkpoint + an explicit change set, not a full rescan.

v0.2.x Slice 3. Discovery's default path is stateless (``draft → fuse → seal``). This adds the
*incremental* path: given a version-aware :class:`DiscoveryCheckpoint`, a set of typed
``EvidenceChange`` deltas, and the current conclusions, it re-derives ONLY the conclusions those
changes (or a policy/capability-version bump) actually affect — leaving the rest untouched.

Deliberately NOT a stream processor: the entry point takes an explicit change set (initial support
per the design — no CDC infrastructure required). Dependency tracking is version-aware on three axes
so a policy or model/capability update triggers rediscovery even when no source data changed:

    checkpoint = {evidence_position, policy_version, capability_set_version}

Invalidation is typed, and the two states are distinct (Governance/REQUIRE_REVIEW depends on it):
  * an UPDATED/created evidence a conclusion relied on, or a policy/capability bump ⇒ **STALE**
    (may no longer be trustworthy → must be re-evaluated);
  * a DELETED evidence a conclusion relied on ⇒ **INVALIDATED** (its basis is gone → known not to hold).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from runtime_contracts.intent import IntentState, VerifiedIntent
from runtime_contracts.evidence import EvidenceChange


@dataclass(frozen=True)
class DiscoveryCheckpoint:
    """A content/version-aware cursor: how far Discovery has consumed the evidence stream, AND the
    policy + capability-set versions in force. A change in any axis can trigger rediscovery — a policy
    or model/capability update invalidates conclusions produced under the old versions even when no
    source datum changed."""
    evidence_position: str = ""            # watermark/cursor into the evidence stream (last change id)
    policy_version: str = ""
    capability_set_version: str = ""


@dataclass
class IncrementalReport:
    """What the pass touched — the basis for the full-scan-vs-incremental comparison (Benchmark B)."""
    examined: int = 0                      # conclusions inspected
    unchanged: int = 0                     # left VERIFIED, untouched
    affected: int = 0                      # found STALE/INVALIDATED by the change set / version bump
    recomputed: int = 0                    # re-derived (STALE → fresh conclusion)
    invalidated: int = 0                   # marked INVALIDATED (basis removed)
    model_calls: int = 0                   # rediscover() invocations (a reader/model pass each)
    bytes_touched: int = 0                 # summed size of the evidence actually reprocessed


@dataclass
class IncrementalResult:
    conclusions: list = field(default_factory=list)
    checkpoint: DiscoveryCheckpoint = field(default_factory=DiscoveryCheckpoint)
    report: IncrementalReport = field(default_factory=IncrementalReport)


# ──────────────────────────── state transitions ────────────────────────────

def mark_stale(vi: VerifiedIntent, reason: str = "") -> VerifiedIntent:
    """VERIFIED → STALE: may no longer be trustworthy; must be re-evaluated. Identity is preserved."""
    return replace(vi, state=IntentState.STALE, validity_reason=reason)


def mark_invalidated(vi: VerifiedIntent, reason: str = "") -> VerifiedIntent:
    """VERIFIED → INVALIDATED: known no longer to hold (its basis was removed)."""
    return replace(vi, state=IntentState.INVALIDATED, validity_reason=reason)


# ──────────────────────────── dependency analysis (pure) ────────────────────────────

def _logical_id(source_ref: str) -> str:
    """The logical artifact id behind an evidence ``source_ref`` (drop the ``#version`` suffix)."""
    return (source_ref or "").split("#", 1)[0]


def evidence_ids(vi: VerifiedIntent) -> set[str]:
    """The logical evidence-artifact ids a conclusion depends on (from its ``DecisionEvidence``)."""
    return {_logical_id(e.source_ref) for e in vi.evidence if e.source_ref}


def _size(vi: VerifiedIntent) -> int:
    return len(vi.request_text or "") + sum(len(str(e.value)) + len(e.source_ref) for e in vi.evidence)


def classify(vi: VerifiedIntent, changes: list[EvidenceChange],
             current: DiscoveryCheckpoint) -> tuple[IntentState, str]:
    """Pure verdict for one conclusion given the change set + the current checkpoint versions.
    Precedence: a removed basis (INVALIDATED) beats a moved basis (STALE) beats a version bump (STALE)."""
    deps = evidence_ids(vi)
    deletes = [c for c in changes if c.removes_basis and c.ref in deps]
    if deletes:
        return IntentState.INVALIDATED, "basis deleted: " + ", ".join(sorted(c.ref for c in deletes))
    updates = [c for c in changes if not c.removes_basis and c.ref in deps]
    if updates:
        return IntentState.STALE, "evidence updated: " + ", ".join(sorted(c.ref for c in updates))
    if vi.policy_version and current.policy_version and vi.policy_version != current.policy_version:
        return IntentState.STALE, f"policy {vi.policy_version} → {current.policy_version}"
    if (vi.capability_version and current.capability_set_version
            and vi.capability_version != current.capability_set_version):
        return IntentState.STALE, f"capability {vi.capability_version} → {current.capability_set_version}"
    return IntentState.VERIFIED, ""


# ──────────────────────────── the incremental entry point ────────────────────────────

def _stamp(vi: VerifiedIntent, current: DiscoveryCheckpoint) -> VerifiedIntent:
    """Stamp a freshly re-derived conclusion with the current dependency versions, so it is not
    re-flagged next pass for the same bump."""
    return replace(vi, policy_version=current.policy_version,
                   capability_version=current.capability_set_version)


def discover_incremental(conclusions: list[VerifiedIntent], changes: list[EvidenceChange],
                         current: DiscoveryCheckpoint, *, rediscover=None) -> IncrementalResult:
    """Re-derive only the conclusions the change set / version bump affects; advance the checkpoint.

    ``rediscover(vi) -> VerifiedIntent`` re-runs Discovery for a STALE conclusion's inputs against the
    current evidence, returning a fresh sealed conclusion (the engine stamps current versions on it).
    If ``rediscover`` is None the affected conclusions are only *marked* STALE (report-only mode)."""
    out: list[VerifiedIntent] = []
    rep = IncrementalReport()
    for vi in conclusions:
        rep.examined += 1
        verdict, reason = classify(vi, changes, current)
        if verdict is IntentState.VERIFIED:
            out.append(vi); rep.unchanged += 1
        elif verdict is IntentState.INVALIDATED:
            out.append(mark_invalidated(vi, reason)); rep.affected += 1; rep.invalidated += 1
        else:  # STALE
            rep.affected += 1
            if rediscover is None:
                out.append(mark_stale(vi, reason))
            else:
                rep.model_calls += 1
                rep.bytes_touched += _size(vi)
                out.append(_stamp(rediscover(vi), current))
                rep.recomputed += 1
    return IncrementalResult(out, current, rep)


def discover_full(conclusions: list[VerifiedIntent], current: DiscoveryCheckpoint,
                  *, rediscover) -> IncrementalResult:
    """The baseline: rescan EVERYTHING — re-derive every conclusion regardless of what changed. Same
    valid outcome as ``discover_incremental`` for the unchanged conclusions, at full cost. Used by
    Benchmark B to show the incremental path reaches the same valid set touching far less."""
    out: list[VerifiedIntent] = []
    rep = IncrementalReport()
    for vi in conclusions:
        rep.examined += 1
        rep.affected += 1
        rep.model_calls += 1
        rep.bytes_touched += _size(vi)
        out.append(_stamp(rediscover(vi), current))
        rep.recomputed += 1
    return IncrementalResult(out, current, rep)
