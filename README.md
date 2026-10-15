# discovery-runtime

![License: AGPL-3.0 + Commons Clause](https://img.shields.io/badge/License-AGPL--3.0%20%2B%20Commons%20Clause-blue.svg) ![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg) [![NVIDIA Inception](https://img.shields.io/badge/NVIDIA-Inception%20Program%20Member-76B900.svg)](https://www.nvidia.com/en-us/startups/)
&nbsp;·&nbsp; self-hosted &nbsp;·&nbsp; no lock-in &nbsp;·&nbsp; source-available

**What it does.** Intent discovery: turns a requester's words into a sealed `VerifiedIntent`
(words -> readers -> fuse -> clarify -> seal). It refuses to seal while anything result-changing is
still open. A second module, `discovery_runtime.learn`, turns outcomes of past decisions into
reviewed priors. (This is *not* the "proactive layer that monitors and proposes missions" described in
the GitHub repository blurb; that is a different component and is not in this repo.)

**Who it's for.** Developers building a domain application that needs a verified, hash-identified
statement of what the user asked for. Domain meaning lives in consumers; this repo is the generic mechanism.

**Maturity: reference.** A library with a conformance test suite; no stated production deployment in this repo.

**3-minute example.** There is no runnable end-to-end example in this repo: the snippet below needs a
user-defined schema and readers. What does run is the test suite (uses a toy "book a meeting" domain):

```bash
PYTHONPATH=../runtime-contracts python -m pytest tests/ -q   # needs a sibling runtime-contracts checkout
```

**Evidence.** `tests/` (conformance, `tests/test_learn.py`, `tests/test_release_line.py`). The Wilson figures
quoted under "Learning" (0.2065 and 0.7225) are *internally reproduced* closed-form arithmetic.
The chess-ablation link is an external page whose result is not audited here.

**Limitations.** Requires consumer-supplied schema and readers; no PyPI package (git-tag install only);
the test command assumes a sibling `runtime-contracts` checkout; consumers named below (`wealth-manager`, GRC)
are not public.

**Docs.** [STATUS.md](STATUS.md) · [CHANGELOG.md](CHANGELOG.md) · [docs/release-history.md](docs/release-history.md) · [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) · [LICENSE.md](LICENSE.md)

> **NVIDIA Inception Program Member** — ReDevOps is a member of the NVIDIA Inception Program, supporting startups advancing AI and accelerated computing. Membership provides access to NVIDIA technology, technical resources, and the startup ecosystem. It does not imply product endorsement by NVIDIA.

## Release status (pinned)

Current release: **v0.1.19** (latest tag by date, 2026-10-14; package and `__version__` both `0.1.19`). Use `v0.1.19` or later on the `v0.1.x` line.

- `v0.3.0` and `v0.4.0` are stray tags published in error. They resolve to the same commits as `v0.1.3` and `v0.1.4`
  (`v0.3.0 == v0.1.3`, `v0.4.0 == v0.1.4`), sort above `v0.1.19` under semver, are superseded, and are intentionally **not deleted**
  (a published tag is immutable). Do not pin them.
- `v0.1.17` falls in the range the CHANGELOG describes as affected by a stale `build/lib` in `runtime-contracts` (tags up to v0.3.13), and its `__version__` reads `0.1.16`. Recommend `>= v0.1.19`.
- Also do not pin `v0.1.11` (installs as `0.1.10`) or `v0.1.12` (on a line that never reached `master`).
- `v0.2.0` is reserved for a coordinated milestone with `runtime-contracts`.

Full history: [docs/release-history.md](docs/release-history.md).

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
  "discovery-runtime @ git+https://github.com/redevops-io/discovery-runtime.git@v0.1.19",
]
```

`v0.1.19` is the latest tag on the forward line carrying `learn` (introduced in `v0.1.13`); it pulls its own `runtime-contracts` pin
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

> **Contract evolution.** Consumers should pin `discovery-runtime` to a released tag. If a consumer needs
> a change to the shared `learn` contract or lifecycle semantics, make that change in `discovery-runtime`,
> release a new tag, and update consumers to that tag. Do not fork or locally redefine the learning
> contract in downstream projects.

The boundary this draws:

```
discovery-runtime owns          consumer owns (e.g. a portfolio experiment)
  Experience                      context_signature semantics
  Pattern                         domain Outcome semantics
  LearningCandidate               evidence mapping
  Lesson                          reviewer identity / policy
  lifecycle arithmetic            domain evaluation
  promotion invariants
```

A consumer should be a thin **adapter** around `observe → mine → propose → shadow → review → challenge`,
not a second learning implementation — so it is testing this runtime's actual mechanism, not a
domain-specific recreation of it. That is also what makes `learn`'s conservatism load-bearing downstream:
where the learning sample is tiny (a few dozen decisions), the centralized Wilson gate is precisely what
stops a single reviewed success or failure from becoming a persistent rule.

For a **reproducible** run, record the *resolved* git commit and the installed `runtime-contracts` version
in the experiment manifest, not just the tag — so a frozen result keeps an immutable identity even if
tag/repository infrastructure later changes.

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

## License

AGPL-3.0-or-later with the Commons Clause (source-available; see [LICENSE.md](LICENSE.md), [LICENSE](LICENSE), [LICENSE-COMMONS-CLAUSE](LICENSE-COMMONS-CLAUSE)).
