## Release line

Current: **v0.1.13** — the clean forward line, carrying the `discovery_runtime.learn`
contract. `v0.2.0` is reserved for the coordinated release milestone across
`runtime-contracts` and this package, and nothing before it may claim a `0.2.x` or
higher number.

### Superseded tags

`v0.3.0` and `v0.4.0` were published in error. This package had never released
a tag — its `pyproject.toml` said `0.2.0` and nothing was ever pushed — so those
two took numbers off a line that had not been opened.

They point at the same commits as the correct tags and are left in place rather
than deleted, because a published tag is immutable and deleting one breaks
anybody who already pinned it:

    v0.3.0  ==  v0.1.3   (superseded — do not pin)
    v0.4.0  ==  v0.1.4   (superseded — do not pin)

Two more tags installed under the wrong number and are frozen in the release-line
test's ledger rather than deleted (a published tag is immutable): `v0.1.11` was cut
while `pyproject` still said `0.1.10`, so it installs as `0.1.10`; `v0.1.12` declares
`0.1.12` correctly but sits on a line that never reached `master`. Do not pin either.

Pin `v0.1.13` (latest; carries the learn contract).

# discovery-runtime

![License: AGPL-3.0 + Commons Clause](https://img.shields.io/badge/License-AGPL--3.0%20%2B%20Commons%20Clause-blue.svg) ![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg) [![NVIDIA Inception](https://img.shields.io/badge/NVIDIA-Inception%20Program%20Member-76B900.svg)](https://www.nvidia.com/en-us/startups/)
&nbsp;·&nbsp; self-hosted &nbsp;·&nbsp; no lock-in &nbsp;·&nbsp; source-available

> **🚀 NVIDIA Inception Program Member** — ReDevOps is a member of the NVIDIA Inception Program, supporting startups advancing AI and accelerated computing. Membership provides access to NVIDIA technology, technical resources, and the startup ecosystem. It does not imply product endorsement by NVIDIA.


The generic **Intent-Discovery runtime**: turn a requester's words into a sealed `VerifiedIntent`.

```
words → [readers] → fuse (agree kept / disagree → open question) → clarify → seal
                                                                      │
                              refuses while anything result-changing is still open
```

It is **domain-agnostic** — parameterized by a schema and a set of readers, it never knows what a
dimension *means*:

```python
from discovery_runtime import DiscoveryRuntime

rt = DiscoveryRuntime(schema=my_schema, readers=[MyRuleReader(), MyModelReader(...)])
vi = rt.draft("…the request…")
for q in rt.clarifications(vi):          # the open "what did you mean?" questions
    vi = rt.resolve(vi, q.field, answer_for(q))
vi = rt.seal(vi)                         # raises SealError if anything result-changing is open
```

## Where it came from, who owns what

Discovery was proved out inside **RAAAL/Quantify** (the wealth-manager application). This repo is the
extraction of the *generic* mechanism into its own owner, so it can be reused without forking:

| Layer | Repo | Holds |
|---|---|---|
| Canonical **meaning** | `runtime-contracts` | `VerifiedIntent`, `DecisionEvidence`, `Unresolved`, `Amendment`, `SealError` |
| Generic **mechanism** (this repo) | `discovery-runtime` | `Reader`/`Reading`, `merge_readings` (fusion), `draft_intent`/`clarifications`/`resolve`, `seal`, `DiscoveryRuntime` |
| Domain **semantics** (consumers) | `wealth-manager` (Quantify, 1st), GRC (2nd) | the schema, the reader *bodies*, the typed policy objects |

**Functional core / imperative shell.** Fusion, canonicalization, hashing, and seal enforcement are
pure functions (same input → same output, replay-safe). `DiscoveryRuntime` is the only object — the
shell that owns the schema + readers + policy. No domain verbs (`discover_assets`, …) ever appear
here; domains inject readers and a `canonicalize`.

## Learning — a correction is not a rule

Discovery turns words into a sealed conclusion. `discovery_runtime.learn` is the other direction over
time: turn the outcomes of past decisions into priors that improve the next one — **without** letting a
single human correction, or a single lucky trial, rewrite the system on the spot.

```
experience → pattern → candidate → (review / shadow) → lesson vN+1
                                    └ never auto-promoted; validation_required
```

This is the contract the [chess ablation](https://redevops.io/benchmarks/decision-runtime-chess/) earned.
There a strong independent oracle (Stockfish) scores every decision — and *even then* the measured
learning came from lessons mined from many scored decisions and gated by support and confidence, never
written from one game. Real domains (revenue, projects, GRC) have no such oracle, so the shortcut
`human correction → permanent rule` is exactly what this module refuses. A correction is an `Experience`;
enough consistent experiences become a `Pattern`; a Pattern can be *proposed* as a `LearningCandidate`;
and only an explicit review/shadow step (the stand-in for the missing oracle) turns an **eligible**
candidate into an **active** `Lesson`.

It is domain-agnostic like the rest of the runtime — parameterized by a `context_signature` it never
interprets. Chess: *"in this position signature, be cautious with queen checks."* Revenue: *"opportunities
with characteristics X and Y have historically responded poorly."* Projects: *"when exactly one contact is
on the active opportunity, select that contact."* Same lifecycle, different words. Confidence is a
closed-form Wilson lower bound, so it is conservative for small samples **by construction** (one supporting
experience scores ~0.21, ten score ~0.72) — the invariant falls out of the arithmetic, not a special case.
Demonstration and experience compose rather than compete: a demonstrated example is an `Experience` with
`origin=DEMONSTRATION` that counts as support but does not bypass the gate — *demonstration teaches the
initial workflow; experience teaches where it should improve.*

### Consuming `learn` from another project

`learn` is domain-agnostic and meant to be shared — a second self-learning experiment should **consume
this contract, not reimplement one**, so every domain's learning gets the same invariant and the same
Wilson-lower-bound arithmetic. This repo is public; pin it by tag (never a branch):

```toml
# pyproject.toml
dependencies = [
  "discovery-runtime @ git+https://github.com/redevops-io/discovery-runtime.git@v0.1.13",
]
```

`v0.1.13` is the clean forward line carrying `learn`; it pulls its own `runtime-contracts` pin
transitively, so a bare `pip install` of the line above is enough (no auth — public repo).

```python
from discovery_runtime.learn import observe, mine, propose, review, PromotionPolicy, Outcome, Origin

# 1. record decisions + outcomes as domain-agnostic Experiences (context_signature is opaque to learn)
xs = [observe("regime=trending|vol=high", "pick", "scale_in", Outcome.GOOD, runtime_version="exp-2")
      for _ in range(6)]
# 2. mine → propose → the gate. A single observation can NEVER promote — by the Wilson arithmetic.
candidate = propose(mine(xs)[0], "In this regime, scale in.")
lesson = review(candidate, accepted=True, reviewer="owner", policy=PromotionPolicy(min_support=3))
assert lesson.is_active            # only because support ≥ 3, confidence clears, AND a human accepted
```

The reusable surface is exactly what `discovery_runtime.learn` exports: the value objects
(`Experience` / `Pattern` / `Lesson` / `LearningCandidate`), the `PromotionPolicy` gate, and the
lifecycle `observe → mine → propose → shadow / review → challenge`. Everything domain-specific — what a
`context_signature` means, what counts as a good `Outcome`, who reviews — stays in the consumer.

## Invariants

1. **No reader is privileged.** Two readers disagreeing on a material field → that field becomes an
   open question, never a silent pick.
2. **Silence is not agreement.** Seal refuses while any result-changing dimension is open.
3. **Identity is content.** `VerifiedIntent` is frozen; its `content_hash` is a stable digest of the
   canonical meaning + evidence + unresolved. A plan re-runs from the hash, never from the sentence.
4. **The runtime is domain-free.** Meaning lives in `runtime-contracts`; semantics live in the
   consumer. This runtime only knows how to *discover, contest, clarify, and seal* a dimension.
5. **A correction is not a rule.** No single experience — not even a deliberate human correction, not
   even a clean demonstration — becomes an active `Lesson`. Promotion needs support, confidence, and an
   explicit review; and an active lesson is retired when counter-evidence pulls it below threshold.

## Test

```bash
PYTHONPATH=../runtime-contracts python -m pytest tests/ -q
```

The conformance suite uses a deliberately non-finance toy domain ("book a meeting") to prove the
runtime is domain-agnostic.
