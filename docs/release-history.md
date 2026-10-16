# Release history

Moved out of the README introduction. For the short pinned status see the README
and [STATUS.md](../STATUS.md); per-version notes are in [CHANGELOG.md](../CHANGELOG.md).

Tag dates below are the tagged commit's committer date (GitHub API, checked 2026-10-15).
There are no GitHub Releases for this repository, only tags.

| Tag | Commit date (UTC) | Note |
|---|---|---|
| v0.1.17 | 2026-09-29 | `__version__` reads `0.1.16`; lies in the CHANGELOG's stale `build/lib` range (pins `runtime-contracts` v0.3.13). Prefer v0.1.19. |
| v0.1.18 | 2026-10-13 | First tag whose package and `__version__` agree with its name. |
| v0.1.19 | 2026-10-14 | Latest tag by date. Pins `runtime-contracts` v0.3.14 (no stale `build/lib`). Recommended. |
| v0.3.0 | 2026-08-17 | Stray; same commit as v0.1.3. Superseded, not deleted. |
| v0.4.0 | 2026-08-17 | Stray; same commit as v0.1.4. Superseded, not deleted. |

Under semver ordering v0.3.0 and v0.4.0 sort *above* v0.1.19, so tools that sort tags
by version (some resolvers, GitHub's tag list) may show them as "latest". They are not.

## Original README introduction (preserved verbatim)

### Release line

Current: **v0.1.17** — the clean forward line, carrying the `discovery_runtime.learn`
contract. `v0.2.0` is reserved for the coordinated release milestone across
`runtime-contracts` and this package, and nothing before it may claim a `0.2.x` or
higher number.

#### Superseded tags

`v0.3.0` and `v0.4.0` were published in error. This package had never released
a tag — its `pyproject.toml` said `0.2.0` and nothing was ever pushed — so those
two took numbers off a line that had not been opened.

They point at the same commits as the correct tags and are left in place rather
than deleted, because a published tag is immutable and deleting one breaks
anybody who already pinned it:

    v0.3.0  ==  v0.1.3   (superseded — do not pin)
    v0.4.0  ==  v0.1.4   (superseded — do not pin)

The tags remain and are intentionally not deleted. They are not releases of this package: the real line is `v0.1.x`. See [CHANGELOG.md](../CHANGELOG.md).

Two more tags installed under the wrong number and are frozen in the release-line
test's ledger rather than deleted (a published tag is immutable): `v0.1.11` was cut
while `pyproject` still said `0.1.10`, so it installs as `0.1.10`; `v0.1.12` declares
`0.1.12` correctly but sits on a line that never reached `master`. Do not pin either.

Pin `v0.1.17` (latest; carries the learn contract). The `v0.1.17` tag predates a one-line fix: its `discovery_runtime.__version__` reads `0.1.16` while the package metadata says `0.1.17`; fixed on `master` after the tag.

> Update (2026-10-15): the "Current: v0.1.17" and "Pin v0.1.17" statements above are
> historical. Current tag is v0.1.19; see below.
