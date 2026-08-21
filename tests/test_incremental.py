"""Incremental Discovery + Benchmark B (v0.2.x Slice 3).

Re-derive only the conclusions an explicit change set (or a policy/capability version bump) affects,
with distinct STALE vs INVALIDATED semantics; and prove the incremental path reaches the same VALID
outcome as a full rescan while touching far less (records / model calls / bytes).
"""
from __future__ import annotations

from runtime_contracts.intent import VerifiedIntent, DecisionEvidence, IntentState
from runtime_contracts.evidence import evidence_change, evidence_ref, UPDATED, DELETED

from discovery_runtime import (
    DiscoveryCheckpoint, classify, discover_incremental, discover_full, evidence_ids,
)


def _concl(ref_id, value, *, ver="v1", policy="pol@1", cap="readers@1"):
    ev = DecisionEvidence(field="f", value=value, source_type="rule", source_ref=f"{ref_id}#{ver}")
    return VerifiedIntent(interpreted={"f": value}, request_text=f"q:{ref_id}", evidence=(ev,),
                          state=IntentState.VERIFIED, content_hash=f"sha256:{ref_id}",
                          policy_version=policy, capability_version=cap)


def _rediscover_from(values, calls, *, policy="pol@1", cap="readers@1"):
    """A stand-in for re-running Discovery: produce a fresh conclusion reflecting *current* values."""
    def rediscover(vi):
        calls.append(vi)
        rid = next(iter(evidence_ids(vi)))
        val = values[rid]
        ev = DecisionEvidence(field="f", value=val, source_type="rule", source_ref=f"{rid}#cur")
        return VerifiedIntent(interpreted={"f": val}, request_text=vi.request_text, evidence=(ev,),
                              state=IntentState.VERIFIED, content_hash=f"sha256:{rid}:{val}")
    return rediscover


def _valid_map(concls):
    """Semantic outcome: {logical evidence id -> interpreted} over the VALID (VERIFIED) conclusions."""
    return {next(iter(evidence_ids(c))): c.interpreted for c in concls if c.valid}


# ── classification (pure) ──

def test_updated_evidence_is_stale():
    c = _concl("crm://42", "a1")
    ch = [evidence_change("crm://42", UPDATED, new=evidence_ref("crm://42", version="v2"))]
    verdict, reason = classify(c, ch, DiscoveryCheckpoint(policy_version="pol@1", capability_set_version="readers@1"))
    assert verdict is IntentState.STALE and "evidence updated" in reason


def test_deleted_evidence_is_invalidated():
    c = _concl("crm://42", "a1")
    ch = [evidence_change("crm://42", DELETED)]
    verdict, reason = classify(c, ch, DiscoveryCheckpoint())
    assert verdict is IntentState.INVALIDATED and "basis deleted" in reason


def test_policy_bump_is_stale_without_any_source_change():
    c = _concl("crm://42", "a1", policy="pol@1")
    cur = DiscoveryCheckpoint(policy_version="pol@2", capability_set_version="readers@1")
    verdict, reason = classify(c, [], cur)          # empty change set — only the policy moved
    assert verdict is IntentState.STALE and "policy pol@1 → pol@2" in reason


def test_capability_bump_is_stale():
    c = _concl("crm://42", "a1", cap="readers@1")
    cur = DiscoveryCheckpoint(policy_version="pol@1", capability_set_version="readers@2")
    verdict, _ = classify(c, [], cur)
    assert verdict is IntentState.STALE


def test_unaffected_conclusion_stays_verified():
    c = _concl("crm://42", "a1")
    other = [evidence_change("erp://99", UPDATED)]
    cur = DiscoveryCheckpoint(policy_version="pol@1", capability_set_version="readers@1")
    verdict, _ = classify(c, other, cur)
    assert verdict is IntentState.VERIFIED


# ── incremental recompute ──

def test_recomputes_only_affected():
    concls = [_concl("A", "a1"), _concl("B", "b1"), _concl("C", "c1")]
    cur = DiscoveryCheckpoint(evidence_position="pos-2", policy_version="pol@1", capability_set_version="readers@1")
    changes = [evidence_change("A", UPDATED, new=evidence_ref("A", version="v2"))]
    calls = []
    values = {"A": "a2", "B": "b1", "C": "c1"}
    res = discover_incremental(concls, changes, cur, rediscover=_rediscover_from(values, calls))
    assert res.report.recomputed == 1 and res.report.unchanged == 2    # only A re-derived
    assert len(calls) == 1
    assert _valid_map(res.conclusions)["A"] == {"f": "a2"}             # A reflects the new value
    assert res.checkpoint.evidence_position == "pos-2"                 # cursor advanced


def test_delete_invalidates_and_is_not_recomputed():
    concls = [_concl("A", "a1"), _concl("B", "b1")]
    cur = DiscoveryCheckpoint(policy_version="pol@1", capability_set_version="readers@1")
    calls = []
    res = discover_incremental(concls, [evidence_change("A", DELETED)], cur,
                               rediscover=_rediscover_from({"B": "b1"}, calls))
    assert res.report.invalidated == 1 and res.report.recomputed == 0 and len(calls) == 0
    a = next(c for c in res.conclusions if next(iter(evidence_ids(c))) == "A")
    assert a.invalidated and "A" not in _valid_map(res.conclusions)    # dropped from the valid set


# ── Benchmark B: incremental == full-scan (valid outcome), touching far less ──

def test_benchmark_b_incremental_matches_full_scan_touching_less():
    refs = ["A", "B", "C", "D", "E"]
    concls = [_concl(r, f"{r.lower()}1") for r in refs]
    values = {"A": "a2", "B": "b1", "C": "c1", "D": "d1", "E": "e1"}   # only A changed
    cur = DiscoveryCheckpoint(evidence_position="pos-9", policy_version="pol@1", capability_set_version="readers@1")
    changes = [evidence_change("A", UPDATED, new=evidence_ref("A", version="v2"))]

    full_calls, inc_calls = [], []
    full = discover_full(concls, cur, rediscover=_rediscover_from(values, full_calls))
    inc = discover_incremental(concls, changes, cur, rediscover=_rediscover_from(values, inc_calls))

    # equivalent VALID outcome (semantic conclusions match) ...
    assert _valid_map(inc.conclusions) == _valid_map(full.conclusions)
    assert _valid_map(inc.conclusions)["A"] == {"f": "a2"}
    # ... reached touching far less
    assert full.report.model_calls == 5 and inc.report.model_calls == 1
    assert full.report.recomputed == 5 and inc.report.recomputed == 1
    assert inc.report.bytes_touched < full.report.bytes_touched


def test_benchmark_b_policy_bump_rediscovers_all_without_source_change():
    refs = ["A", "B", "C"]
    concls = [_concl(r, f"{r.lower()}1", policy="pol@1") for r in refs]
    values = {"A": "a1", "B": "b1", "C": "c1"}                          # no source change
    cur = DiscoveryCheckpoint(policy_version="pol@2", capability_set_version="readers@1")
    calls = []
    inc = discover_incremental(concls, [], cur, rediscover=_rediscover_from(values, calls))
    assert inc.report.recomputed == 3                                  # the policy bump alone rediscovers all
    # and the re-derived conclusions now carry the current policy version (won't re-flag next pass)
    assert all(c.policy_version == "pol@2" for c in inc.conclusions)
    inc2 = discover_incremental(inc.conclusions, [], cur, rediscover=_rediscover_from(values, calls))
    assert inc2.report.recomputed == 0
