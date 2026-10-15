# Status

- **Maturity:** reference (library with a conformance test suite; no production deployment claimed in this repo).
- **Version:** latest tag v0.1.19 (2026-10-14); source declares `0.1.20` = docs-only, no tag yet. No GitHub Releases, tags only.
- **Last git activity:** 2026-10-14 (`git log -1 --format=%cs` on master at the time of writing).
- **Supported:** intent discovery (`DiscoveryRuntime`: draft, clarify, resolve, seal) and the `discovery_runtime.learn` lifecycle (observe, mine, propose, shadow/review, challenge). Python 3.10+ (CI runs 3.12). Install by git tag only.
- **Not supported / not provided:** PyPI package (none published); a runnable end-to-end example (needs consumer schema and readers); the "proactive monitoring / propose missions" behaviour described in the GitHub repo blurb; anything in the private consumers (`wealth-manager`, GRC).

## Known issues

- Stray tags `v0.3.0` and `v0.4.0` (same commits as `v0.1.3` / `v0.1.4`) sort above `v0.1.19` under semver. Superseded, not deleted. Do not pin.
- `v0.1.11` installs as `0.1.10`; `v0.1.12` is on a line that never reached `master`; `v0.1.17` reports `__version__` `0.1.16` and is in the stale `build/lib` range; prefer `>= v0.1.19`.
- Test command assumes a sibling `runtime-contracts` checkout.
- Licence labelling: see [LICENSE.md](LICENSE.md); GitHub's licence label and the file text differ (flagged for counsel review, no conclusion here).

See [docs/release-history.md](docs/release-history.md) and [CHANGELOG.md](CHANGELOG.md).
