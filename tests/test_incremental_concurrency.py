"""Discovery fan-out (LLM-parallelization audit, P1) — opt-in, order-preserving, result-identical.
Independent STALE re-derivations overlap under DISCOVERY_CONCURRENCY>1; default is the serial path."""
from __future__ import annotations

import time

from runtime_contracts import (
    VerifiedIntent, IntentField, DecisionEvidence, ReaderKind, Author, IntentState,
    EvidenceChange, UPDATED,
)

from discovery_runtime import DiscoveryCheckpoint, discover_incremental, evidence_ids
from discovery_runtime._parallel import run_parallel


def test_run_parallel_serial_by_default(monkeypatch):
    monkeypatch.delenv("DISCOVERY_CONCURRENCY", raising=False)
    assert run_parallel([lambda: 1, lambda: 2, lambda: 3]) == [1, 2, 3]


def _concl(ref_id, value) -> VerifiedIntent:
    ev = DecisionEvidence("r1", ReaderKind.RULE, value, source_ref=f"{ref_id}#v1")
    return VerifiedIntent(objective="rebalance",
                          fields={"f": IntentField(value=value, author=Author.READER, evidence=[ev])},
                          policy_version="pol@1", capability_version="readers@1").seal()


def _valid_map(concls):
    return {next(iter(evidence_ids(c))): c.fields["f"].value
            for c in concls if c.state is IntentState.VERIFIED}


def _run(delay=0.03):
    refs = [f"crm://{i}" for i in range(6)]
    concls = [_concl(r, f"v{i}") for i, r in enumerate(refs)]
    changes = [EvidenceChange(r, UPDATED) for r in refs]          # all UPDATED → all STALE → all re-derived
    values = {r: f"new{i}" for i, r in enumerate(refs)}
    cp = DiscoveryCheckpoint(policy_version="pol@1", capability_set_version="readers@1")

    def rediscover(vi):
        time.sleep(delay)
        rid = next(iter(evidence_ids(vi)))
        ev = DecisionEvidence("r1", ReaderKind.RULE, values[rid], source_ref=f"{rid}#cur")
        return VerifiedIntent(objective="rebalance",
                              fields={"f": IntentField(value=values[rid], author=Author.READER, evidence=[ev])}).seal()

    t0 = time.perf_counter()
    res = discover_incremental(concls, changes, cp, rediscover=rediscover)
    return res, time.perf_counter() - t0


def test_incremental_parallel_equals_serial_and_faster(monkeypatch):
    monkeypatch.delenv("DISCOVERY_CONCURRENCY", raising=False)
    serial, wall_s = _run()
    monkeypatch.setenv("DISCOVERY_CONCURRENCY", "4")
    parallel, wall_p = _run()

    assert _valid_map(serial.conclusions) == _valid_map(parallel.conclusions)   # identical valid state
    assert serial.report.recomputed == parallel.report.recomputed == 6          # same report
    assert wall_p < wall_s * 0.6, f"serial={wall_s:.2f}s parallel={wall_p:.2f}s"  # 6 stale, 4-wide overlap
