# discovery-runtime

The generic **Intent-Discovery runtime**: turn a requester's words into a sealed `VerifiedIntent`, and
— when the world's evidence moves — re-derive **only** the conclusions that change.

```
words → [readers] → fuse (agree kept / disagree → open question) → clarify → seal
                                                                      │
                              refuses while anything result-changing is still open

evidence changes (EvidenceChange[]) + checkpoint → classify → recompute ONLY the affected conclusions
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

## Incremental Discovery (v0.2.x)

Beside the stateless `text → VerifiedIntent` path, Discovery can operate from an explicit change set +
a **version-aware checkpoint** instead of rescanning the world — it is not a stream processor:

```python
from discovery_runtime import DiscoveryCheckpoint, discover_incremental, discover_full

# checkpoint pins how far we consumed the evidence stream AND the policy/capability versions in force
current = DiscoveryCheckpoint(evidence_position="…", policy_version="pol@2", capability_set_version="rd@3")
result  = discover_incremental(conclusions, changes, current, rediscover=my_rediscover)
```

- A conclusion goes **STALE** (may no longer be trustworthy → re-evaluate) when an evidence it relied on
  was *updated*, or the policy/capability version moved; it goes **INVALIDATED** (known no longer to hold)
  when an evidence it relied on was *deleted*. A policy/model bump triggers rediscovery even when no
  source datum changed.
- Only the **affected** conclusions recompute; the rest stay `VERIFIED`, untouched. `discover_full` is the
  rescan baseline — **Benchmark B** shows the incremental path reaches the same valid outcome touching far
  less (fewer records / model calls / bytes).

## Where it came from, who owns what

Discovery was proved out inside **RAAAL/Quantify** (the wealth-manager application). This repo is the
extraction of the *generic* mechanism into its own owner, so it can be reused without forking:

| Layer | Repo | Holds |
|---|---|---|
| Canonical **meaning** | `runtime-contracts` | `VerifiedIntent`, `DecisionEvidence`, `Unresolved`, `Amendment`, `SealError` |
| Generic **mechanism** (this repo) | `discovery-runtime` | `Reader`/`Reading`, `merge_readings` (fusion), `draft_intent`/`clarifications`/`resolve`, `seal`, `DiscoveryRuntime`; **incremental**: `DiscoveryCheckpoint`, `EvidenceChange`-driven `classify`/`discover_incremental`/`discover_full`, `mark_stale`/`mark_invalidated` |
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
