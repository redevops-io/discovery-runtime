"""``DiscoveryRuntime`` — the imperative shell. It owns the long-lived configuration (the domain
schema, the readers, the fusion + canonicalization policy) and exposes the functional core as a
small, stable surface. It is parameterized by a schema and readers; it does **not** know any
domain's meaning:

    DiscoveryRuntime(schema=quantify_schema, readers=[RuleReader(), LlmReader(...)])
    DiscoveryRuntime(schema=grc_schema,      readers=[GrcRuleReader(), GrcLlmReader(...)])

and NOT ``runtime.discover_assets()`` / ``discover_sell_action()`` — finance (or GRC) verbs never
appear here. Domains supply the schema, the readers, and (if their draft is not a plain dict) a
``canonicalize``. Quantify is the first consumer, GRC the second.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from runtime_contracts.intent import Unresolved, VerifiedIntent

from .intent import (
    Canonicalize,
    FusionPolicy,
    _default_canonicalize,
    clarifications,
    draft_intent,
    resolve,
)
from .reader import Reader, merge_readings
from .seal import seal


@dataclass
class DiscoveryRuntime:
    """Turn a request into a sealed ``VerifiedIntent`` for one domain. ``schema`` is opaque to the
    runtime — the readers interpret it; keeping it here lets a domain introspect/validate its own
    dimensions without the runtime learning what they mean."""

    readers: list[Reader]
    schema: Any = None
    canonicalize: Canonicalize = _default_canonicalize
    fusion_policy: FusionPolicy = field(default=merge_readings)

    def draft(self, text: str) -> VerifiedIntent:
        """Words → unsealed ``VerifiedIntent`` (readers → fuse → canonicalize)."""
        return draft_intent(
            text, self.readers,
            canonicalize=self.canonicalize,
            fusion_policy=self.fusion_policy,
        )

    def clarifications(self, vi: VerifiedIntent) -> list[Unresolved]:
        """Open result-changing questions for this intent, in order."""
        return clarifications(vi)

    def resolve(self, vi: VerifiedIntent, field: str, value: Any) -> VerifiedIntent:
        """Record the requester's authoritative answer to one open question."""
        return resolve(vi, field, value)

    def seal(self, vi: VerifiedIntent) -> VerifiedIntent:
        """Seal — refuses while any result-changing dimension is open."""
        return seal(vi)

    def understand(self, text: str) -> VerifiedIntent:
        """Convenience: draft then seal in one call. Raises ``SealError`` if the request is not
        fully pinned — callers that expect open questions should use ``draft`` + ``clarifications``
        + ``resolve`` and seal only once nothing result-changing is open."""
        return self.seal(self.draft(text))
