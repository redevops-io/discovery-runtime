# Changelog

The release line is `v0.1.x`. `v0.2.0` is reserved for a coordinated milestone with
`runtime-contracts`.

## Unreleased

- CI: add `tests` workflow (pytest on Python 3.12).
- Fix: `discovery_runtime.__version__` now reads `0.1.17` (the `v0.1.17` tag shipped it as `0.1.16`,
  failing two tests in `tests/test_release_line.py`).
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
