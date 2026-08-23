"""Bounded, order-preserving parallel execution for independent Discovery work (LLM-parallelization
audit, P1). ``draft_intent`` runs its readers (a deterministic rule reader + a latency-dominant model
reader) as independent siblings, and ``discover_incremental`` re-derives each STALE conclusion
independently. Both evaluate serially today. ``run_parallel`` overlaps them when opted in via
``DISCOVERY_CONCURRENCY`` (default 1 = unchanged serial), preserving order so fusion and the report are
identical to the serial path."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor


def discovery_concurrency() -> int:
    try:
        return max(1, int(os.getenv("DISCOVERY_CONCURRENCY", "1")))
    except ValueError:
        return 1


def run_parallel(thunks) -> list:
    """Run 0-arg callables, results in input order. Serial when concurrency<=1 (default) or one thunk;
    otherwise a bounded ThreadPool. Thunks must be independent."""
    thunks = list(thunks)
    c = discovery_concurrency()
    if c <= 1 or len(thunks) <= 1:
        return [t() for t in thunks]
    with ThreadPoolExecutor(max_workers=min(c, len(thunks))) as pool:
        futures = [pool.submit(t) for t in thunks]
        return [f.result() for f in futures]        # input order preserved
