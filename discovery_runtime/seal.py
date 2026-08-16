"""Sealing — the runtime's enforcement of "nothing result-changing is still open." This is the
behavior the reconciliation deliberately moved OUT of the (now-frozen) ``VerifiedIntent`` contract
and INTO the runtime functional core: the contract records the seal *decision* (``state`` +
``content_hash``); the act of deciding lives here.

Behavior is preserved from ``wealth-manager``'s ``VerifiedIntent.seal()``/``_digest()``:
- seal refuses (``SealError``) while any result-changing dimension is open — "we ran out of time
  asking" can never silently become "the requester agreed";
- the digest is a stable ``sha256`` over the canonical content (``sort_keys``), truncated to 32 hex.

The digest keys the domain-agnostic ``interpreted`` dict (where wealth-manager keyed the finance
``client_policy``); hash *strings* therefore differ from the pre-extraction values by design, while
the seal/refuse *behavior* is identical. Same input → same hash (deterministic, replay-safe).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace

from runtime_contracts.intent import IntentState, SealError, VerifiedIntent


def digest(vi: VerifiedIntent) -> str:
    """Stable content hash. Evidence + unresolved are part of identity — a contested field is a
    different fact — so they are hashed too."""
    payload = {
        "interpreted": vi.interpreted,
        "produced_by": vi.produced_by,
        "author": vi.author,
        "evidence": [asdict(e) for e in vi.evidence],
        "unresolved": [asdict(u) for u in vi.unresolved],
    }
    body = json.dumps(payload, sort_keys=True, default=str).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()[:32]


def seal(vi: VerifiedIntent) -> VerifiedIntent:
    """Transition DRAFT → VERIFIED. Refuses while any result-changing dimension is open. Sealing
    does not change identity; the hash is stamped over the already-fixed content. Returns a NEW
    ``VerifiedIntent`` (frozen contract)."""
    if vi.sealed:
        return vi
    open_dims = vi.open_result_changing()
    if open_dims:
        raise SealError(
            "cannot seal — result-changing dimensions still open: "
            + ", ".join(f"{u.field} ({u.question})" for u in open_dims)
        )
    return replace(vi, content_hash=digest(vi), state=IntentState.VERIFIED)
