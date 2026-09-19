"""Learn — the generic experience→lesson lifecycle, with one invariant: **a correction is not a rule.**

Discovery turns words into a sealed conclusion. *Learning* is the other direction over time: turn the
outcomes of past decisions into priors that improve the next one — without letting a single human
correction, or a single lucky game, rewrite the system on the spot.

This is the contract the chess ablation earned. There, a strong independent oracle (Stockfish) scores
every decision, so "what went well" is cheap and immediate — and even then the measured learning came
from lessons *mined from many scored decisions and gated by support and confidence*, never written from
one game. Real domains (revenue, projects, GRC) do **not** have that oracle. So the same shortcut —
``human correction → permanent rule`` — is exactly what this module refuses. A correction is an
:class:`Experience`; enough consistent experiences become a :class:`Pattern`; a Pattern can be *proposed*
as a :class:`LearningCandidate`; and only an explicit review/shadow step (which stands in for the missing
oracle) turns an eligible candidate into an **active** :class:`Lesson`::

    experience → pattern → candidate → (review / shadow) → lesson vN+1
                                        └ never auto-promoted; validation_required

It is **domain-agnostic**, like the rest of this runtime — parameterized by a ``context_signature`` string
it never interprets. Chess produces *"in this position signature, be cautious with queen checks."* Revenue
produces *"opportunities with characteristics X and Y have historically responded poorly."* Projects
produce *"when exactly one contact is on the active opportunity, select that contact."* Same lifecycle,
different words.

Pure and deterministic: no model calls, no clocks, no ordering surprises — confidence is a closed-form
Wilson lower bound, so it is conservative for small samples by construction (one supporting experience
scores far below ten), and mining the same experiences twice yields byte-identical patterns. The review
step is an input (a decision made elsewhere — a human, a slower trusted signal, a shadow evaluation), not
something this module invents.

Demonstration and experience compose here rather than competing: a demonstrated example is an
:class:`Experience` with ``origin=Origin.DEMONSTRATION`` — an intentional teaching signal that counts as
support like any other, but does **not** bypass the gate. *Demonstration teaches the initial workflow;
experience teaches where that workflow should improve* — and every improvement is still a candidate that
has to earn its place.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import Enum

from runtime_contracts import DecisionEvidence


class Outcome(str, Enum):
    """How a past decision turned out. Deliberately coarse — the domain decides what "good" means and
    reports it; this module only counts agreement."""
    GOOD = "good"
    BAD = "bad"
    NEUTRAL = "neutral"


class Origin(str, Enum):
    """Where an experience came from. All three enter the *same* lifecycle; none skips the gate."""
    EXPERIENCE = "experience"        # observed in the wild
    DEMONSTRATION = "demonstration"  # an intentional human-taught example (teaches the initial workflow)
    CORRECTION = "correction"        # a human overrode a decision after the fact


class LessonState(str, Enum):
    """A lesson's lifecycle. Only ``ACTIVE`` may inform a live decision; everything else is provisional.
    ``RETIRED`` is an ACTIVE lesson that later counter-evidence pulled back below threshold — the state is
    distinct from ``REJECTED`` (never accepted) because a lesson that *was* trusted and stopped being
    trustworthy is a different fact from one that never qualified."""
    PROPOSED = "proposed"   # a candidate's lesson; never applied
    SHADOW = "shadow"       # evaluated alongside the live system, still not applied
    ACTIVE = "active"       # accepted after review/shadow; may inform decisions
    REJECTED = "rejected"   # reviewed and declined, or ineligible
    RETIRED = "retired"     # was ACTIVE; counter-evidence dropped it below threshold


# ──────────────────────────── confidence (pure, closed-form) ────────────────────────────

def wilson_lower_bound(successes: int, n: int, *, z: float = 1.96) -> float:
    """The Wilson score interval's lower bound for a binomial proportion — a conservative estimate of the
    true "holds" rate given ``successes`` out of ``n`` observations. Conservative for small ``n`` by
    construction: 1/1 scores ~0.21, 3/3 ~0.44, 10/10 ~0.72. That single property is what makes "a
    correction is not a rule" fall out of the arithmetic rather than out of a special case — one
    supporting experience cannot clear a sensible threshold no matter how clean it looks."""
    if n <= 0:
        return 0.0
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = p + z2 / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)
    return max(0.0, (center - margin) / denom)


# ──────────────────────────── the value objects ────────────────────────────

@dataclass(frozen=True)
class Experience:
    """One past decision and how it turned out — the atom of learning.

    ``context_signature`` is the domain-agnostic key this module groups on and never interprets (chess:
    ``"in_check=False|phase=middlegame|material=level"``; projects: ``"op=select_contact|contacts=1"``).
    ``evidence`` reuses the canonical :class:`DecisionEvidence` so learning provenance and Discovery
    provenance are the same currency."""
    context_signature: str
    decision: str
    action: str
    outcome: Outcome
    evidence: tuple[DecisionEvidence, ...] = ()
    runtime_version: str = ""
    origin: Origin = Origin.EXPERIENCE
    produced_by: str = ""


@dataclass(frozen=True)
class Pattern:
    """A proposition about a ``scope`` (a context signature, possibly coarsened), backed by the experiences
    that support it and the ones that contradict it. Confidence is derived, never set — so a Pattern cannot
    claim more certainty than its evidence carries."""
    scope: str
    proposition: str
    supporting: tuple[Experience, ...] = ()
    counterexamples: tuple[Experience, ...] = ()

    @property
    def support(self) -> int:
        return len(self.supporting)

    @property
    def contradictions(self) -> int:
        return len(self.counterexamples)

    @property
    def total(self) -> int:
        return self.support + self.contradictions

    @property
    def contradiction_rate(self) -> float:
        return self.contradictions / self.total if self.total else 0.0

    @property
    def confidence(self) -> float:
        """Wilson lower bound of support / (support + counterexamples). Conservative for small samples."""
        return wilson_lower_bound(self.support, self.total)


@dataclass(frozen=True)
class Lesson:
    """A rule / prior / strategy the runtime may consult — but only while ``state is ACTIVE``. Carries its
    own provenance (the :class:`Pattern` behind it) so "why does the system believe this?" is answerable,
    and a ``reviewer`` once it has been through the gate."""
    statement: str
    applicability: str
    pattern: Pattern
    state: LessonState = LessonState.PROPOSED
    origin: Origin = Origin.EXPERIENCE
    reviewer: str = ""

    @property
    def confidence(self) -> float:
        return self.pattern.confidence

    @property
    def is_active(self) -> bool:
        return self.state is LessonState.ACTIVE


@dataclass(frozen=True)
class LearningCandidate:
    """A proposed change awaiting validation. ``validation_required`` is the load-bearing flag: it is the
    reason a candidate is never itself a rule. It is ``True`` until :func:`review` (or :func:`shadow` then
    review) has run against a :class:`PromotionPolicy`."""
    proposed: Lesson            # a Lesson in PROPOSED state — the proposed_change
    supporting_pattern: Pattern
    validation_required: bool = True
    rationale: str = ""


@dataclass(frozen=True)
class PromotionPolicy:
    """The gate a candidate must clear to become an ACTIVE lesson. Defaults are deliberately conservative;
    ``min_support > 1`` alone already means no single correction can promote, and ``require_review`` means
    even an eligible candidate needs an explicit accept (the stand-in for the oracle a real domain lacks)."""
    min_support: int = 3
    min_confidence: float = 0.35
    max_contradiction_rate: float = 0.25
    require_review: bool = True


# ──────────────────────────── constructors ────────────────────────────

def observe(context_signature: str, decision: str, action: str, outcome: Outcome, *,
            evidence: tuple[DecisionEvidence, ...] = (), runtime_version: str = "",
            origin: Origin = Origin.EXPERIENCE, produced_by: str = "") -> Experience:
    """Record one decision + its outcome. A human correction is ``origin=Origin.CORRECTION`` with the
    ``outcome`` the correction implies — still just an experience, never a rule."""
    return Experience(context_signature, decision, action, outcome, tuple(evidence),
                      runtime_version, origin, produced_by)


def from_demonstration(context_signature: str, decision: str, action: str, *,
                       evidence: tuple[DecisionEvidence, ...] = (), runtime_version: str = "",
                       produced_by: str = "") -> Experience:
    """A demonstrated example — an intentional teaching signal (outcome GOOD by construction). It counts as
    support like any other experience and does **not** bypass the gate."""
    return observe(context_signature, decision, action, Outcome.GOOD, evidence=evidence,
                   runtime_version=runtime_version, origin=Origin.DEMONSTRATION, produced_by=produced_by)


# ──────────────────────────── mining (pure, deterministic) ────────────────────────────

def mine(experiences: list[Experience], *, proposition: str = "action leads to a good outcome",
         good=(Outcome.GOOD,)) -> list[Pattern]:
    """Group experiences by ``(context_signature, action)`` into Patterns; an experience whose outcome is in
    ``good`` supports the proposition, the rest contradict it. Deterministic: groups are emitted in first-seen
    order and each group keeps input order, so mining the same list twice is byte-identical."""
    order: list[tuple[str, str]] = []
    groups: dict[tuple[str, str], tuple[list[Experience], list[Experience]]] = {}
    for e in experiences:
        key = (e.context_signature, e.action)
        if key not in groups:
            groups[key] = ([], [])
            order.append(key)
        (groups[key][0] if e.outcome in good else groups[key][1]).append(e)
    patterns: list[Pattern] = []
    for scope, action in order:
        sup, ctr = groups[(scope, action)]
        patterns.append(Pattern(scope=scope, proposition=f"{action}: {proposition}",
                                supporting=tuple(sup), counterexamples=tuple(ctr)))
    return patterns


def eligible(pattern: Pattern, policy: PromotionPolicy = PromotionPolicy()) -> bool:
    """Whether a Pattern's evidence *could* support an active lesson — support, confidence and contradiction
    rate all within policy. Necessary, not sufficient: ``require_review`` still stands between here and ACTIVE."""
    return (pattern.support >= policy.min_support
            and pattern.confidence >= policy.min_confidence
            and pattern.contradiction_rate <= policy.max_contradiction_rate)


# ──────────────────────────── the lifecycle ────────────────────────────

def propose(pattern: Pattern, statement: str, *, applicability: str = "",
            origin: Origin = Origin.EXPERIENCE, policy: PromotionPolicy = PromotionPolicy(),
            rationale: str = "") -> LearningCandidate:
    """Turn a Pattern into a candidate. The proposed Lesson is always born ``PROPOSED`` (never ACTIVE), and
    ``validation_required`` is ``True`` whenever the policy requires review OR the pattern is not yet
    eligible — i.e. essentially always, which is the point."""
    proposed = Lesson(statement=statement, applicability=applicability or pattern.scope,
                      pattern=pattern, state=LessonState.PROPOSED, origin=origin)
    needs = policy.require_review or not eligible(pattern, policy)
    return LearningCandidate(proposed=proposed, supporting_pattern=pattern,
                             validation_required=needs, rationale=rationale)


def shadow(candidate: LearningCandidate) -> Lesson:
    """Move a candidate's lesson into SHADOW — evaluated alongside the live system, still not applied. A
    reviewer watches shadow behaviour before accepting. Does not consult the policy; SHADOW is never ACTIVE."""
    return replace(candidate.proposed, state=LessonState.SHADOW)


def review(candidate: LearningCandidate, *, accepted: bool, reviewer: str,
           policy: PromotionPolicy = PromotionPolicy()) -> Lesson:
    """The gate. Returns an ACTIVE lesson **only** if the reviewer accepts *and* the supporting pattern is
    eligible under the policy; otherwise REJECTED. This is where the human / slower-trusted-signal / oracle
    stands in — nothing here promotes on its own."""
    ok = accepted and eligible(candidate.supporting_pattern, policy)
    state = LessonState.ACTIVE if ok else LessonState.REJECTED
    return replace(candidate.proposed, state=state, reviewer=reviewer)


def challenge(lesson: Lesson, counterexamples: list[Experience],
              policy: PromotionPolicy = PromotionPolicy()) -> Lesson:
    """Fold new counter-evidence into an ACTIVE lesson and re-test it. If the enlarged pattern is no longer
    eligible, the lesson is RETIRED — an active belief is provisional, not permanent. A non-active lesson is
    returned unchanged (only what the system trusts can be pulled back)."""
    if not lesson.is_active:
        return lesson
    p = lesson.pattern
    enlarged = replace(p, counterexamples=p.counterexamples + tuple(counterexamples))
    new_state = LessonState.ACTIVE if eligible(enlarged, policy) else LessonState.RETIRED
    return replace(lesson, pattern=enlarged, state=new_state)
