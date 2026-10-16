# Changelog

The release line is `v0.1.x`. `v0.2.0` is reserved for a coordinated milestone with
`runtime-contracts`.

## Unreleased

- Version `0.1.20`: documentation wording cleanup only.

- Version `0.1.19`: realign `runtime-contracts` pin v0.3.13 -> v0.3.14. Tags up to
  v0.3.13 commit a stale `build/lib` that pip may install instead of the source; v0.3.14 removes it.
- CI: remove the "Reinstall runtime-contracts from a clean tree" workaround (no longer needed); `fetch-depth: 0`
  is kept for the release-line test.

- CI: add `tests` workflow (pytest on Python 3.12).
- Version `0.1.18` (tag to be cut after merge): `v0.1.17` shipped `discovery_runtime.__version__ = "0.1.16"`, and
  `tests/test_release_line.py` requires each commit after a tag to declare a new version. `v0.1.18` is the first
  tag whose package and `__version__` both agree with its name.
- CI: install `runtime-contracts` v0.3.13 from a tree without its committed `build/` (tags up to v0.3.13 ship a
  stale one that pip installs instead of the source; fixed upstream from v0.3.14).
- Docs: README "Current" version corrected to `v0.1.17` (was `v0.1.13`).

## v0.1.17

- Realign `runtime-contracts` pin v0.3.12 -> v0.3.13.

## Stray tags: v0.3.0 and v0.4.0

These two tags were published in error and are **not releases**. This package had never
tagged a release, so they took numbers off a line that had not been opened. They point at the
same commits as the correct tags and are left in place (not deleted) because a published tag is
immutable and deleting one would break anyone who already pinned it:

- `v0.3.0` == `v0.1.3` (superseded - do not pin)
- `v0.4.0` == `v0.1.4` (superseded - do not pin)

Also do not pin `v0.1.11` (installs as `0.1.10`) or `v0.1.12` (sits on a line that never reached
`master`). Use the latest `v0.1.x` tag.
