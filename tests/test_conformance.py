"""Conformance suite for the generic Discovery runtime.

The domain used here is deliberately NOT finance — a toy "meeting request" schema — to prove the
runtime carries no domain knowledge. It exercises the properties the extraction must preserve:
multi-witness fusion (agree kept / disagree → open question), the clarification loop, seal refusal
while anything result-changing is open, seal determinism, and frozen-value immutability.
"""
from __future__ import annotations

import re

import pytest

from discovery_runtime import (
    DiscoveryRuntime,
    Reading,
    SealError,
    Unresolved,
    draft_intent,
    merge_readings,
    resolve,
    seal,
)
from runtime_contracts.intent import DecisionEvidence, IntentState


# ── a toy non-finance domain: "book a meeting" ───────────────────────────────
class MeetingRuleReader:
    source_type = "rule"

    def read(self, text: str) -> Reading:
        payload: dict = {}
        evidence: list[DecisionEvidence] = []
        unresolved: list[Unresolved] = []
        low = text.lower()

        m = re.search(r"with (\w+)", low)
        if m:
            payload["attendee"] = m.group(1)
            evidence.append(DecisionEvidence("attendee", m.group(1), "rule", m.group(0)))

        dur = re.search(r"(\d+)\s*min", low)
        if dur:
            payload["duration_min"] = int(dur.group(1))
            evidence.append(DecisionEvidence("duration_min", int(dur.group(1)), "rule", dur.group(0)))
        else:
            unresolved.append(Unresolved("duration_min", "how long should the meeting be?"))

        if not evidence:
            unresolved.append(Unresolved("attendee", f"could not interpret: {text!r}"))
        return Reading(payload=payload, evidence=evidence, unresolved=unresolved)


class ContrarianReader:
    """A second witness that disagrees on attendee — to force a disagreement → open question."""
    source_type = "model"

    def read(self, text: str) -> Reading:
        return Reading(
            payload={"attendee": "someone_else"},
            evidence=[DecisionEvidence("attendee", "someone_else", "model", "guess")],
        )


def rt(readers=None):
    return DiscoveryRuntime(schema={"dimensions": ["attendee", "duration_min"]},
                            readers=readers or [MeetingRuleReader()])


def test_draft_extracts_interpreted_and_evidence():
    vi = rt().draft("meet with alice for 30 min")
    assert vi.interpreted == {"attendee": "alice", "duration_min": 30}
    assert {e.field for e in vi.evidence} == {"attendee", "duration_min"}
    assert vi.state is IntentState.DRAFT
    assert not vi.sealed


def test_seal_refuses_while_result_changing_open():
    vi = rt().draft("meet with alice")            # no duration → Unresolved(result_changing)
    assert any(u.field == "duration_min" for u in rt().clarifications(vi))
    with pytest.raises(SealError):
        rt().seal(vi)


def test_clarify_resolve_then_seal():
    r = rt()
    vi = r.draft("meet with alice")
    assert r.clarifications(vi)                     # duration open
    vi = r.resolve(vi, "duration_min", 45)
    assert not r.clarifications(vi)                 # nothing result-changing open
    sealed = r.seal(vi)
    assert sealed.sealed and sealed.state is IntentState.VERIFIED
    assert sealed.interpreted["duration_min"] == 45
    assert any(a.field == "duration_min" and a.new == 45 for a in sealed.amendments)


def test_disagreement_becomes_open_question_not_silent_pick():
    # two witnesses disagree on attendee → attendee must become an open, result-changing question
    reading = merge_readings([
        MeetingRuleReader().read("meet with alice for 15 min"),
        ContrarianReader().read("meet with alice for 15 min"),
    ])
    assert any(u.field == "attendee" and u.result_changing for u in reading.unresolved)


def test_seal_is_deterministic_and_content_addressed():
    a = rt().understand("meet with bob for 20 min")
    b = rt().understand("meet with bob for 20 min")
    assert a.content_hash == b.content_hash and a.content_hash.startswith("sha256:")
    c = rt().understand("meet with bob for 25 min")
    assert c.content_hash != a.content_hash        # different meaning → different identity


def test_frozen_intent_is_not_mutated_by_resolve():
    r = rt()
    draft = r.draft("meet with carol")
    resolved = r.resolve(draft, "duration_min", 10)
    assert draft is not resolved
    assert "duration_min" not in draft.interpreted   # original untouched
    assert resolved.interpreted["duration_min"] == 10


def test_module_level_functions_match_runtime_methods():
    # the runtime shell is a thin wrapper over the functional core — both paths agree
    readers = [MeetingRuleReader()]
    via_fn = seal(draft_intent("meet with dan for 30 min", readers))
    via_rt = DiscoveryRuntime(readers=readers).understand("meet with dan for 30 min")
    assert via_fn.content_hash == via_rt.content_hash
