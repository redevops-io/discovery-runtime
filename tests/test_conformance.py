"""Conformance suite for the generic Discovery runtime.

The domain used here is deliberately NOT finance — a toy "meeting request" schema — to prove the
runtime carries no domain knowledge. It exercises the properties the extraction must preserve:
multi-witness fusion (agree kept / disagree → open question), the clarification loop, seal refusal
while anything result-changing is open, seal determinism, and frozen-value immutability.
"""
from __future__ import annotations

import re

import pytest

from runtime_contracts import OpenReason, ReaderKind
from discovery_runtime import interpreted, digest
from discovery_runtime import (
    DiscoveryRuntime,
    Reading,
    NotSealable,
    Unresolved,
    draft_intent,
    merge_readings,
    resolve,
    seal,
)
from runtime_contracts import DecisionEvidence, IntentState


# ── a toy non-finance domain: "book a meeting" ───────────────────────────────
class MeetingRuleReader:
    """Evidence is filed under the dimension it supports, which is the contract's own shape.

    It used to be a flat list with the dimension carried inside each item as
    `DecisionEvidence(field, value, source_type, source_ref)`. The contract has no `field` on
    evidence — `VerifiedIntent.fields` maps a name to an `IntentField` and the evidence hangs off
    that — so those four positional arguments landed on
    `(reader_id, kind, value, confidence)` and put free text where a decimal string belongs.
    """

    reader_id = "meeting-rules@1"
    kind = ReaderKind.RULE

    def read(self, text: str) -> Reading:
        payload: dict = {}
        evidence: dict[str, list[DecisionEvidence]] = {}
        unresolved: list[Unresolved] = []
        low = text.lower()

        m = re.search(r"with (\w+)", low)
        if m:
            payload["attendee"] = m.group(1)
            evidence["attendee"] = [DecisionEvidence(
                reader_id=self.reader_id, kind=self.kind,
                value=m.group(1), source_ref=m.group(0))]

        dur = re.search(r"(\d+)\s*min", low)
        if dur:
            payload["duration_min"] = int(dur.group(1))
            evidence["duration_min"] = [DecisionEvidence(
                reader_id=self.reader_id, kind=self.kind,
                value=int(dur.group(1)), source_ref=dur.group(0))]
        else:
            unresolved.append(Unresolved(
                dimension="duration_min", reason=OpenReason.NOT_ASKED,
                detail="how long should the meeting be?", result_changing=True))

        if not evidence:
            unresolved.append(Unresolved(
                dimension="attendee", reason=OpenReason.NOT_ASKED,
                detail=f"could not interpret: {text!r}", result_changing=True))
        return Reading(payload=payload, evidence=evidence, unresolved=unresolved)


class ContrarianReader:
    """A second witness that disagrees on attendee — to force a disagreement → open question."""

    reader_id = "contrarian@1"
    kind = ReaderKind.MODEL

    def read(self, text: str) -> Reading:
        return Reading(
            payload={"attendee": "someone_else"},
            evidence={"attendee": [DecisionEvidence(
                reader_id=self.reader_id, kind=self.kind,
                value="someone_else", source_ref="guess")]},
        )


def rt(readers=None):
    return DiscoveryRuntime(schema={"dimensions": ["attendee", "duration_min"]},
                            objective="book a meeting",
                            readers=readers or [MeetingRuleReader()])


def test_draft_extracts_interpreted_and_evidence():
    vi = rt().draft("meet with alice for 30 min")
    assert interpreted(vi) == {"attendee": "alice", "duration_min": 30}
    # Which dimension a piece of evidence supports is the key it is filed under, not an attribute
    # on the evidence. The contract has no `field` on `DecisionEvidence` precisely so the two can
    # never disagree; asserting the mapping is asserting the property.
    assert {name for name, f in vi.fields.items() if f.evidence} == {"attendee", "duration_min"}
    assert all(e.reader_id for f in vi.fields.values() for e in f.evidence), (
        "every piece of evidence must say which reader produced it")
    assert vi.state is IntentState.DRAFT
    assert not vi.is_verified


def test_seal_refuses_while_result_changing_open():
    vi = rt().draft("meet with alice")            # no duration → Unresolved(result_changing)
    assert any(u.dimension == "duration_min" for u in rt().clarifications(vi))
    with pytest.raises(NotSealable):
        rt().seal(vi)


def test_clarify_resolve_then_seal():
    r = rt()
    vi = r.draft("meet with alice")
    assert r.clarifications(vi)                     # duration open
    vi = r.resolve(vi, "duration_min", 45)
    assert not r.clarifications(vi)                 # nothing result-changing open
    sealed = r.seal(vi)
    assert sealed.is_verified and sealed.state is IntentState.VERIFIED
    assert interpreted(sealed)["duration_min"] == 45
    assert any(a.dimension == "duration_min" and a.to_value == 45 for a in sealed.amendments)


def test_disagreement_becomes_open_question_not_silent_pick():
    # two witnesses disagree on attendee → attendee must become an open, result-changing question
    reading = merge_readings([
        MeetingRuleReader().read("meet with alice for 15 min"),
        ContrarianReader().read("meet with alice for 15 min"),
    ])
    assert any(u.dimension == "attendee" and u.result_changing for u in reading.unresolved)


def test_seal_is_deterministic_and_content_addressed():
    a = rt().understand("meet with bob for 20 min")
    b = rt().understand("meet with bob for 20 min")
    assert digest(a) == digest(b) and digest(a)
    c = rt().understand("meet with bob for 25 min")
    assert digest(c) != digest(a)        # different meaning → different identity


def test_frozen_intent_is_not_mutated_by_resolve():
    r = rt()
    draft = r.draft("meet with carol")
    resolved = r.resolve(draft, "duration_min", 10)
    assert draft is not resolved
    assert "duration_min" not in interpreted(draft)   # original untouched
    assert interpreted(resolved)["duration_min"] == 10


def test_module_level_functions_match_runtime_methods():
    # the runtime shell is a thin wrapper over the functional core — both paths agree
    readers = [MeetingRuleReader()]
    via_fn = seal(draft_intent("meet with dan for 30 min", readers))
    via_rt = DiscoveryRuntime(readers=readers).understand("meet with dan for 30 min")
    assert digest(via_fn) == digest(via_rt)
