"""Fusion semantics, in pairs: the same meaning agrees, a different meaning does not.

Every test here is a pair on purpose. "Two readers agree" is trivially satisfiable by a comparison
that always returns True, and "two readers disagree" by one that always returns False — so either
assertion alone proves nothing about the rule between them. The pair is the evidence.

The defect this module was written for: fusion compared ``repr(value)``, so ``'500'`` and ``500``
were a disagreement and became a clarification question on a value both readers had read correctly.
A deterministic reader that normalises and a model that does not would produce one on every amount.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from discovery_runtime.fusion import Decision, Fusion, Proposal, fuse, same_value


def money(raw: str):
    """A domain normaliser, of the kind a schema supplies. Deliberately small.

    It knows currency symbols, thousands separators and a `k` suffix — enough to exercise the seam.
    The runtime does not contain this and must not: whether `£2.5k` is 2500 is a domain fact.
    """
    import re

    text = raw.strip().lower().replace(",", "")
    m = re.fullmatch(r"[£$€]?\s*([\d.]+)\s*(k|m)?", text)
    if not m:
        return None
    scale = {"k": 1_000, "m": 1_000_000}.get(m.group(2), 1)
    return Decimal(m.group(1)) * scale


NORMALIZERS = {"NUMBER": money}


# --- the pair the whole extraction exists for -------------------------------

def test_stringly_identical_values_agree_before_any_rule_runs():
    """`'500'` and `500` are the same text once stringified, mode notwithstanding.

    The original defect compared `repr`, where they differ — which is why a deterministic reader
    and a model produced a clarification question on amounts they had both read correctly.
    """
    assert same_value("500", 500)
    assert same_value("500", 500, "NUMBER", normalizers=NORMALIZERS)


def test_same_number_written_differently_agrees():
    assert same_value("$500", "500", "NUMBER", normalizers=NORMALIZERS)
    assert same_value("£2.5k", "2500", "NUMBER", normalizers=NORMALIZERS)
    assert same_value("1,000", 1000, "NUMBER", normalizers=NORMALIZERS)


def test_different_numbers_still_disagree():
    """The half that matters. A comparison that reconciles everything is not a comparison."""
    assert not same_value("500", 600, "NUMBER", normalizers=NORMALIZERS)
    assert not same_value("£2.5k", "2500000", "NUMBER", normalizers=NORMALIZERS)
    assert not same_value("$500", "$5000", "NUMBER", normalizers=NORMALIZERS)


def test_text_stays_exact():
    """TEXT does not guess.

    Assuming two spellings mean the same thing is the failure the whole design is about, so the
    default mode reconciles nothing beyond case and surrounding space.
    """
    assert same_value("Monthly", "monthly")
    assert same_value(" monthly ", "monthly")
    assert not same_value("monthly", "month")
    assert not same_value("VTI", "VOO")


def test_set_compares_tokens_unordered():
    assert same_value("VTI, BND", "BND VTI", "SET")
    assert same_value("a;b;c", "c, a, b", "SET")
    assert not same_value("VTI, BND", "VTI, VOO", "SET")
    assert not same_value("VTI", "VTI, BND", "SET")


def test_an_unreadable_value_is_not_equal_to_anything():
    """Including another unreadable one.

    A normaliser returning None means "I cannot read this". Treating two of those as equal would
    make every pair of nonsense strings agree, which is the most dangerous possible direction for
    this function to fail in.
    """
    assert not same_value("bananas", "oranges", "NUMBER", normalizers=NORMALIZERS)
    assert not same_value("bananas", "bananas!", "NUMBER", normalizers=NORMALIZERS)
    # Identical text still agrees — that is checked before any normaliser runs.
    assert same_value("bananas", "bananas", "NUMBER", normalizers=NORMALIZERS)


def test_an_unknown_mode_falls_back_to_exact():
    """The safe direction.

    A mode nobody supplied a rule for reports a disagreement a domain rule might have reconciled.
    The other direction would invent an agreement, which is unrecoverable.

    Compared with `$500` rather than `500`: values are stringified before comparison, so `'500'`
    and `500` are textually equal and would pass under any mode. That is worth knowing — the
    original defect was comparing `repr`, where `"'500'"` and `'500'` differ — but it makes them
    useless for testing a fallback.
    """
    assert not same_value("$500", 500, "CURRENCY_OF_THE_REALM")
    assert same_value("$500", "$500", "CURRENCY_OF_THE_REALM")


def test_a_normaliser_that_raises_does_not_mean_equal():
    def explodes(_):
        raise ValueError("nope")

    assert not same_value("a", "b", "NUMBER", normalizers={"NUMBER": explodes})


# --- outcomes, kept apart because they call for different repairs -----------

def _p(value, reader="r"):
    return Proposal(value=value, reader_id=reader)


def test_agreement_proceeds_and_carries_the_value():
    decision = fuse("amount", [_p("$500", "rules"), _p(500, "model")],
                    mode="NUMBER", normalizers=NORMALIZERS)
    assert decision.outcome is Fusion.AGREE
    assert decision.proceeds
    assert decision.value == "$500"


def test_disagreement_names_both_readers_and_does_not_proceed():
    decision = fuse("amount", [_p("$500", "rules"), _p(600, "model")],
                    mode="NUMBER", normalizers=NORMALIZERS)
    assert decision.outcome is Fusion.DISAGREE
    assert not decision.proceeds
    assert "rules" in decision.detail and "model" in decision.detail, (
        "a disagreement that does not say who said what cannot be adjudicated")


def test_a_contradiction_outranks_agreement():
    """Two readers agreeing on something the words contradict is two readers making one mistake."""
    agreeing = [_p("annual", "rules"), _p("annual", "model")]
    assert fuse("cadence", agreeing).outcome is Fusion.AGREE
    assert fuse("cadence", agreeing,
                contradicted_by="'every month' says monthly").outcome is Fusion.DISAGREE


def test_a_missing_binding_is_not_a_disagreement():
    """The readers may agree perfectly and the value still be unusable.

    Reported as its own outcome because the repair is different: a binding nobody supplied needs a
    schema or a reader, not adjudication between two answers.
    """
    agreeing = [_p("60/40", "rules"), _p("60/40", "model")]
    assert fuse("weights", agreeing).outcome is Fusion.AGREE
    decision = fuse("weights", agreeing, requires_binding=True)
    assert decision.outcome is Fusion.INSUFFICIENT_RELATION
    assert not decision.proceeds


def test_language_ambiguity_is_its_own_outcome():
    """Not a parser failure and not a model failure — a question for the person."""
    agreeing = [_p("rebalance", "rules"), _p("rebalance", "model")]
    assert fuse("action", agreeing).outcome is Fusion.AGREE
    decision = fuse("action", agreeing,
                    ambiguous_between=("periodic_rebalancing", "stated_weights"))
    assert decision.outcome is Fusion.AMBIGUOUS_BY_LANGUAGE
    assert "periodic_rebalancing" in decision.detail


def test_no_proposal_is_a_disagreement_not_an_agreement():
    assert fuse("amount", []).outcome is Fusion.DISAGREE


@pytest.mark.parametrize("outcome", list(Fusion))
def test_only_agreement_proceeds(outcome):
    assert outcome.proceeds is (outcome is Fusion.AGREE)


# --- the seam, through merge_readings ---------------------------------------

def test_merge_readings_uses_the_comparison_rule():
    """The regression that started this, at the level a caller sees it."""
    from runtime_contracts import DecisionEvidence, ReaderKind

    from discovery_runtime import Reading, merge_readings

    def ev(reader_id, value):
        return DecisionEvidence(reader_id=reader_id, kind=ReaderKind.RULE,
                                value=value, source_ref="s")

    readings = [
        Reading(payload={"amount": "$500"}, evidence={"amount": [ev("rules", "$500")]}),
        Reading(payload={"amount": 500}, evidence={"amount": [ev("model", 500)]}),
    ]

    naive = merge_readings(readings)
    assert naive.unresolved, (
        "without a comparison rule these must be reported as differing — TEXT is exact")

    informed = merge_readings(readings, compare_as={"amount": "NUMBER"},
                              normalizers=NORMALIZERS)
    assert not informed.unresolved, (
        "with the schema's rule these agree, and asking about them is the loop this fixes")


def test_merge_readings_still_reports_real_disagreement():
    from runtime_contracts import DecisionEvidence, ReaderKind

    from discovery_runtime import Reading, merge_readings

    def ev(reader_id, value):
        return DecisionEvidence(reader_id=reader_id, kind=ReaderKind.RULE,
                                value=value, source_ref="s")

    readings = [
        Reading(payload={"amount": "$500"}, evidence={"amount": [ev("rules", "$500")]}),
        Reading(payload={"amount": 600}, evidence={"amount": [ev("model", 600)]}),
    ]
    fused = merge_readings(readings, compare_as={"amount": "NUMBER"},
                           normalizers=NORMALIZERS)
    assert [u.dimension for u in fused.unresolved] == ["amount"]
