"""Incremental Discovery + Benchmark B, on the canonical runtime-contracts 0.3.x contract.

Re-derive only the conclusions an explicit change set (or a policy/capability version bump) affects,
with distinct STALE vs INVALIDATED semantics; and prove the incremental path reaches the same VALID
outcome as a full rescan while touching far less. Conclusions are canonical ``VerifiedIntent``s whose
evidence hangs off each ``IntentField``.
"""
from __future__ import annotations

from runtime_contracts import (
    VerifiedIntent, IntentField, DecisionEvidence, ReaderKind, Author, IntentState,
    EvidenceChange, UPDATED, DELETED,
)

from discovery_runtime import (
    DiscoveryCheckpoint, classify, discover_incremental, discover_full, evidence_ids,
)


def _concl(ref_id, value, *, ver="v1", policy="pol@1", cap="readers@1") -> VerifiedIntent:
    ev = DecisionEvidence("r1", ReaderKind.RULE, value, source_ref=f"{ref_id}#{ver}")
    vi = VerifiedIntent(objective="rebalance",
                        fields={"f": IntentField(value=value, author=Author.READER, evidence=[ev])},
                        policy_version=policy, capability_version=cap)
    return vi.seal()


def _rediscover_from(values, calls):
    """Stand-in for re-running Discovery: produce a fresh sealed conclusion reflecting current values."""
    def rediscover(vi):
        calls.append(vi)
        rid = next(iter(evidence_ids(vi)))
        val = values[rid]
        ev = DecisionEvidence("r1", ReaderKind.RULE, val, source_ref=f"{rid}#cur")
        fresh = VerifiedIntent(objective="rebalance",
                               fields={"f": IntentField(value=val, author=Author.READER, evidence=[ev])})
        return fresh.seal()
    return rediscover


def _valid_map(concls):
    """Semantic outcome: {logical evidence id -> value} over the VALID (VERIFIED) conclusions."""
    return {next(iter(evidence_ids(c))): c.fields["f"].value
            for c in concls if c.state is IntentState.VERIFIED}


# ── classification (pure) ──

def test_updated_evidence_is_stale():
    c = _concl("crm://42", "a1")
    ch = [EvidenceChange("crm://42", UPDATED)]
    verdict, reason = classify(c, ch, DiscoveryCheckpoint(policy_version="pol@1", capability_set_version="readers@1"))
    assert verdict is IntentState.STALE and "evidence updated" in reason


def test_deleted_evidence_is_invalidated():
    c = _concl("crm://42", "a1")
    verdict, reason = classify(c, [EvidenceChange("crm://42", DELETED)], DiscoveryCheckpoint())
    assert verdict is IntentState.INVALIDATED and "basis deleted" in reason


def test_policy_bump_is_stale_without_any_source_change():
    c = _concl("crm://42", "a1", policy="pol@1")
    cur = DiscoveryCheckpoint(policy_version="pol@2", capability_set_version="readers@1")
    verdict, reason = classify(c, [], cur)
    assert verdict is IntentState.STALE and "policy pol@1 → pol@2" in reason


def test_capability_bump_is_stale():
    c = _concl("crm://42", "a1", cap="readers@1")
    cur = DiscoveryCheckpoint(policy_version="pol@1", capability_set_version="readers@2")
    assert classify(c, [], cur)[0] is IntentState.STALE


def test_unaffected_conclusion_stays_verified():
    c = _concl("crm://42", "a1")
    cur = DiscoveryCheckpoint(policy_version="pol@1", capability_set_version="readers@1")
    assert classify(c, [EvidenceChange("erp://99", UPDATED)], cur)[0] is IntentState.VERIFIED


# ── incremental recompute ──

def test_recomputes_only_affected():
    concls = [_concl("A", "a1"), _concl("B", "b1"), _concl("C", "c1")]
    cur = DiscoveryCheckpoint(evidence_position="pos-2", policy_version="pol@1", capability_set_version="readers@1")
    calls = []
    res = discover_incremental(concls, [EvidenceChange("A", UPDATED)], cur,
                               rediscover=_rediscover_from({"A": "a2", "B": "b1", "C": "c1"}, calls))
    assert res.report.recomputed == 1 and res.report.unchanged == 2 and len(calls) == 1
    assert _valid_map(res.conclusions)["A"] == "a2"
    assert res.checkpoint.evidence_position == "pos-2"


def test_delete_invalidates_and_is_not_recomputed():
    concls = [_concl("A", "a1"), _concl("B", "b1")]
    cur = DiscoveryCheckpoint(policy_version="pol@1", capability_set_version="readers@1")
    calls = []
    res = discover_incremental(concls, [EvidenceChange("A", DELETED)], cur,
                               rediscover=_rediscover_from({"B": "b1"}, calls))
    assert res.report.invalidated == 1 and res.report.recomputed == 0 and len(calls) == 0
    a = next(c for c in res.conclusions if next(iter(evidence_ids(c))) == "A")
    assert a.state is IntentState.INVALIDATED and "A" not in _valid_map(res.conclusions)


# ── Benchmark B: incremental == full-scan (valid outcome), touching far less ──

def test_benchmark_b_incremental_matches_full_scan_touching_less():
    refs = ["A", "B", "C", "D", "E"]
    concls = [_concl(r, f"{r.lower()}1") for r in refs]
    values = {"A": "a2", "B": "b1", "C": "c1", "D": "d1", "E": "e1"}   # only A changed
    cur = DiscoveryCheckpoint(evidence_position="pos-9", policy_version="pol@1", capability_set_version="readers@1")

    full_calls, inc_calls = [], []
    full = discover_full(concls, cur, rediscover=_rediscover_from(values, full_calls))
    inc = discover_incremental(concls, [EvidenceChange("A", UPDATED)], cur,
                               rediscover=_rediscover_from(values, inc_calls))

    assert _valid_map(inc.conclusions) == _valid_map(full.conclusions)   # same VALID outcome ...
    assert _valid_map(inc.conclusions)["A"] == "a2"
    assert full.report.model_calls == 5 and inc.report.model_calls == 1   # ... touching far less
    assert full.report.recomputed == 5 and inc.report.recomputed == 1
    assert inc.report.bytes_touched < full.report.bytes_touched


def test_benchmark_b_policy_bump_rediscovers_all_without_source_change():
    concls = [_concl(r, f"{r.lower()}1", policy="pol@1") for r in ("A", "B", "C")]
    values = {"A": "a1", "B": "b1", "C": "c1"}
    cur = DiscoveryCheckpoint(policy_version="pol@2", capability_set_version="readers@1")
    calls = []
    inc = discover_incremental(concls, [], cur, rediscover=_rediscover_from(values, calls))
    assert inc.report.recomputed == 3                          # the policy bump alone rediscovers all
    assert all(c.policy_version == "pol@2" for c in inc.conclusions)
    inc2 = discover_incremental(inc.conclusions, [], cur, rediscover=_rediscover_from(values, calls))
    assert inc2.report.recomputed == 0                         # and converges
