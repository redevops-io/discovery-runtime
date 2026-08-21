## Release line

Current: **v0.1.4**. `v0.2.0` is reserved for the coordinated release milestone
across `runtime-contracts` and this package, and nothing before it may claim a
`0.2.x` or higher number.

### Superseded tags

`v0.3.0` and `v0.4.0` were published in error. This package had never released
a tag — its `pyproject.toml` said `0.2.0` and nothing was ever pushed — so those
two took numbers off a line that had not been opened.

They point at the same commits as the correct tags and are left in place rather
than deleted, because a published tag is immutable and deleting one breaks
anybody who already pinned it:

    v0.3.0  ==  v0.1.3   (superseded — do not pin)
    v0.4.0  ==  v0.1.4   (superseded — do not pin)

Pin `v0.1.4`.

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

## Invariants

1. **No reader is privileged.** Two readers disagreeing on a material field → that field becomes an
   open question, never a silent pick.
2. **Silence is not agreement.** Seal refuses while any result-changing dimension is open.
3. **Identity is content.** `VerifiedIntent` is frozen; its `content_hash` is a stable digest of the
   canonical meaning + evidence + unresolved. A plan re-runs from the hash, never from the sentence.
4. **The runtime is domain-free.** Meaning lives in `runtime-contracts`; semantics live in the
   consumer. This runtime only knows how to *discover, contest, clarify, and seal* a dimension.

## Test

```bash
PYTHONPATH=../runtime-contracts python -m pytest tests/ -q
```

The conformance suite uses a deliberately non-finance toy domain ("book a meeting") to prove the
runtime is domain-agnostic.
