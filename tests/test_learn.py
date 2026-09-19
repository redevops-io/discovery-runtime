"""The learning lifecycle, and the one property it exists to protect: **a correction is not a rule.**

Chess could get away with turning outcomes into priors quickly because Stockfish scores every decision.
Real domains cannot, so these tests pin the gate rather than the happy path: a single experience — even a
deliberate human correction, even a clean demonstration — never becomes an active lesson; promotion needs
support, confidence, *and* an explicit review; and a lesson that was trusted can be retired when
counter-evidence arrives. The arithmetic (a Wilson lower bound) is what makes small samples unpersuasive
by construction, so the invariant does not depend on a special case that a later edit could drop.
"""
from __future__ import annotations

from discovery_runtime import (
    Experience,
    Lesson,
    LessonState,
    Origin,
    Outcome,
    Pattern,
    PromotionPolicy,
    challenge,
    eligible,
    from_demonstration,
    mine,
    observe,
    propose,
    review,
    shadow,
    wilson_lower_bound,
)

SIG = "in_check=False|phase=middlegame|material=level"


def _exp(outcome: Outcome, *, action: str = "queen+check", origin: Origin = Origin.EXPERIENCE) -> Experience:
    return observe(SIG, decision="pick a move", action=action, outcome=outcome, origin=origin)


# ──────────────────────────── the invariant ────────────────────────────

def test_a_single_correction_is_not_a_rule():
    """One corrective experience yields, at most, a candidate that still requires validation — never an
    active lesson, even if a reviewer immediately accepts it. Support of 1 fails the gate on two counts
    (min_support and confidence), which is the whole design."""
    correction = observe(SIG, "pick a move", "queen+check", Outcome.BAD, origin=Origin.CORRECTION)
    patterns = mine([correction], proposition="is safe", good=(Outcome.GOOD,))
    assert len(patterns) == 1
    pat = patterns[0]
    assert pat.support == 0 and pat.contradictions == 1

    cand = propose(pat, "Be cautious with queen checks here.")
    assert cand.proposed.state is LessonState.PROPOSED
    assert cand.validation_required is True

    # even an eager reviewer cannot promote it — the pattern is not eligible
    lesson = review(cand, accepted=True, reviewer="alice")
    assert not lesson.is_active
    assert lesson.state is LessonState.REJECTED


def test_promotion_requires_support_confidence_and_review():
    """The positive path: enough consistent supporting experiences make the pattern eligible, but ACTIVE
    still needs an explicit accept. Decline, and it is REJECTED with the same evidence."""
    policy = PromotionPolicy(min_support=3, min_confidence=0.35, require_review=True)
    supports = [_exp(Outcome.GOOD, action="rook+capture") for _ in range(6)]
    pat = mine(supports)[0]
    assert eligible(pat, policy)

    cand = propose(pat, "Prefer the rook capture in this signature.", policy=policy)
    assert cand.validation_required is True                  # eligible, but review still required

    declined = review(cand, accepted=False, reviewer="bob", policy=policy)
    assert declined.state is LessonState.REJECTED

    accepted = review(cand, accepted=True, reviewer="bob", policy=policy)
    assert accepted.is_active
    assert accepted.state is LessonState.ACTIVE
    assert accepted.reviewer == "bob"


def test_an_active_lesson_can_be_retired_by_counterevidence():
    """An active belief is provisional. Fold in enough counterexamples that the enlarged pattern falls below
    threshold and the lesson RETIRES — distinct from REJECTED, because it *was* trusted."""
    policy = PromotionPolicy(min_support=3, min_confidence=0.35, max_contradiction_rate=0.25)
    pat = mine([_exp(Outcome.GOOD, action="rook+capture") for _ in range(6)])[0]
    lesson = review(propose(pat, "Prefer the rook capture.", policy=policy),
                    accepted=True, reviewer="carol", policy=policy)
    assert lesson.is_active

    retired = challenge(lesson, [_exp(Outcome.BAD, action="rook+capture") for _ in range(6)], policy=policy)
    assert retired.state is LessonState.RETIRED
    assert retired.pattern.contradictions == 6              # the evidence is kept, not discarded


def test_a_challenge_that_still_holds_keeps_the_lesson_active():
    """One dissenting datum against a strong pattern does not retire it — the gate is about the balance of
    evidence, not the last observation."""
    policy = PromotionPolicy(min_support=3, min_confidence=0.35, max_contradiction_rate=0.25)
    pat = mine([_exp(Outcome.GOOD, action="rook+capture") for _ in range(20)])[0]
    lesson = review(propose(pat, "Prefer the rook capture.", policy=policy),
                    accepted=True, reviewer="dave", policy=policy)
    still = challenge(lesson, [_exp(Outcome.BAD, action="rook+capture")], policy=policy)
    assert still.is_active


def test_demonstration_still_enters_the_lifecycle():
    """A demonstration is an intentional teaching signal, but a *single* one does not auto-activate — it is
    support like any other and goes through the same gate. Demonstration teaches the initial workflow;
    experience teaches where it should improve, and both are validated."""
    demo = from_demonstration(SIG, "pick a move", "castle")
    assert demo.origin is Origin.DEMONSTRATION and demo.outcome is Outcome.GOOD
    cand = propose(mine([demo])[0], "Castle here.")
    assert review(cand, accepted=True, reviewer="erin").is_active is False


def test_shadow_is_never_active():
    """Shadow evaluation observes a candidate alongside the live system without applying it."""
    pat = mine([_exp(Outcome.GOOD, action="rook+capture") for _ in range(6)])[0]
    s = shadow(propose(pat, "Prefer the rook capture."))
    assert s.state is LessonState.SHADOW and not s.is_active


# ──────────────────────────── the arithmetic ────────────────────────────

def test_wilson_lower_bound_is_conservative_for_small_samples():
    """The property the invariant leans on: for a perfect record, one observation is far less persuasive
    than ten, and the bound rises monotonically with sample size."""
    one = wilson_lower_bound(1, 1)
    three = wilson_lower_bound(3, 3)
    ten = wilson_lower_bound(10, 10)
    assert one < three < ten
    assert one < 0.35 <= ten          # one clean datum fails a sane threshold; ten clears it
    assert wilson_lower_bound(0, 0) == 0.0


def test_confidence_never_exceeds_the_evidence():
    """A perfect but tiny record cannot masquerade as certainty."""
    assert Pattern("s", "p", supporting=(_exp(Outcome.GOOD),)).confidence < 0.5


# ──────────────────────────── determinism ────────────────────────────

def test_mining_is_deterministic_and_order_preserving():
    """Same experiences in, byte-identical patterns out — groups in first-seen order, members in input
    order. Determinism is a property the rest of this runtime holds itself to, and learning is no exception."""
    xs = [
        _exp(Outcome.GOOD, action="a"),
        _exp(Outcome.BAD, action="b"),
        _exp(Outcome.GOOD, action="a"),
        _exp(Outcome.GOOD, action="b"),
    ]
    p1 = mine(xs)
    p2 = mine(xs)
    assert [(p.scope, p.proposition, p.support, p.contradictions) for p in p1] == \
           [(p.scope, p.proposition, p.support, p.contradictions) for p in p2]
    # first-seen action order: "a" before "b"
    assert p1[0].proposition.startswith("a:") and p1[1].proposition.startswith("b:")
    assert p1[0].support == 2                                # both "a" experiences were GOOD


def test_mine_splits_supporting_from_counterexamples_by_outcome():
    xs = [_exp(Outcome.GOOD, action="x"), _exp(Outcome.BAD, action="x"), _exp(Outcome.GOOD, action="x")]
    pat = mine(xs)[0]
    assert pat.support == 2 and pat.contradictions == 1
    assert abs(pat.contradiction_rate - (1 / 3)) < 1e-9
