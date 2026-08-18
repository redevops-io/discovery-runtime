"""Nothing before the coordinated milestone may claim v0.2.0 or higher.

`v0.3.0` and `v0.4.0` were published from this repository in error. It had never
released a tag — `pyproject.toml` said `0.2.0` and nothing had ever been pushed —
so those two took numbers off a line that had not been opened, and `v0.2.0` is
reserved for the coordinated release across `runtime-contracts` and this package.

A published tag is immutable, so the wrong ones stay: deleting a tag breaks
anybody who already pinned it, and a version number that once meant something
and later means something else is worse than a number that is merely wrong. They
point at the same commits as `v0.1.3` and `v0.1.4` and the README says so.

What this guards is the next one. The mistake was invisible at the moment it was
made: nothing in the repository said which line was in use, and the declared
version in `pyproject.toml` was itself the thing that was wrong.
"""
from __future__ import annotations

import pathlib
import tomllib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: The first version this package may claim once the coordinated release
#: happens. Until then every release is a `0.1.x`.
RESERVED = (0, 2, 0)

#: Published in error, kept because deleting a tag breaks whoever pinned it.
SUPERSEDED = {"v0.3.0": "v0.1.3", "v0.4.0": "v0.1.4"}


def _declared() -> tuple:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    raw = data["project"]["version"]
    parts = raw.split(".")
    return tuple(int(p) for p in parts[:3]), raw


def test_the_declared_version_is_below_the_reserved_line():
    """The check that would have caught it.

    `pyproject.toml` said `0.2.0` while nothing had shipped, and that number is
    what made `0.3.0` look like the natural next one.
    """
    parsed, raw = _declared()
    assert parsed < RESERVED, (
        f"pyproject declares {raw}, at or above the reserved "
        f"{'.'.join(str(n) for n in RESERVED)}. That version is held for the "
        "coordinated release across runtime-contracts and this package; "
        "pre-milestone work releases as 0.1.x.")


def test_the_module_version_matches_the_package_version():
    """Two places state it, so they are required to agree.

    They disagreed during the renumbering — the metadata read 0.2.0 while the
    module reported 0.3.0 — and a package whose two version strings differ can
    satisfy a pin while running something else.
    """
    import discovery_runtime

    _, raw = _declared()
    assert discovery_runtime.__version__ == raw, (
        f"pyproject says {raw} and the module says "
        f"{discovery_runtime.__version__}")


def test_the_installed_version_is_the_declared_one():
    """And both of those are source files, so they can agree and both be stale.

    The two checks above compare `pyproject.toml` with `discovery_runtime.
    __version__` — two files in this repository, which a single edit keeps in
    step. Neither says anything about the version actually *installed*, which
    is the number `importlib.metadata` reports and therefore the number any
    downstream "which runtime served this?" check reads.

    They diverged the moment the version was bumped: the source said 0.1.8 and
    the installed metadata went on saying 0.1.4 until the package was
    reinstalled. A deployment verifying its runtime version would have been
    told 0.1.4 about a 0.1.8 it was running.

    Same shape as the release-advance check below: a guard that verifies the
    parts agree with each other rather than with the world.
    """
    from importlib.metadata import PackageNotFoundError, version

    import discovery_runtime

    try:
        installed = version("discovery-runtime")
    except PackageNotFoundError:
        pytest.skip("not installed as a distribution")

    assert installed == discovery_runtime.__version__, (
        f"the installed distribution reports {installed} and the module says "
        f"{discovery_runtime.__version__}. Reinstall after bumping — until "
        "then anything reading the metadata is told the old version.")


@pytest.mark.parametrize("wrong,correct", sorted(SUPERSEDED.items()))
def test_the_superseded_tags_are_documented(wrong, correct):
    """A wrong tag that nobody wrote down is a wrong tag somebody will pin.

    It cannot be deleted, so the only remaining protection is that the
    repository says what it is and what to use instead.
    """
    readme = (ROOT / "README.md").read_text()
    assert wrong in readme, f"{wrong} was published in error and is not named in the README"
    assert correct in readme, f"the README does not say {wrong} is superseded by {correct}"


def _tags() -> dict:
    """Every published tag and the commit it points at."""
    import subprocess

    out = subprocess.run(["git", "tag", "--format=%(refname:short) %(objectname)"],
                         cwd=ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        pytest.skip("not a git checkout")
    return dict(line.split(" ", 1) for line in out.stdout.split("\n") if " " in line)


def test_a_release_advances_the_declared_version():
    """The check that was missing, and what it cost.

    `v0.1.5`, `v0.1.6` and `v0.1.7` were all published from commits declaring
    `0.1.4`. Every one of them installs as 0.1.4 and reports 0.1.4 to
    `importlib.metadata`, so a consumer pinning `v0.1.7` and asking the package
    what it is gets the answer for a release two ahead of it — and any downstream
    check of "which runtime version served this request" is answering about a
    version that was never deployed.

    The two existing checks both passed throughout: the declared version was
    below the reserved line, and the module agreed with the metadata. They
    checked that the number was *self-consistent* and never that it *moved*.
    That is the shape of this whole class — a guard that verifies the parts
    agree with each other rather than with the world.

    Stated as: the version this commit declares must not already belong to a
    tag pointing somewhere else.
    """
    import subprocess

    _, raw = _declared()
    tags = _tags()
    claimed = f"v{raw}"
    if claimed not in tags:
        return                                     # unreleased; nothing to clash

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    peeled = subprocess.run(["git", "rev-list", "-n", "1", claimed], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    assert peeled == head, (
        f"this commit declares {raw}, and {claimed} already points at "
        f"{peeled[:9]}. Cutting a tag here would publish a second, different "
        f"{claimed}, or — as happened for v0.1.5 through v0.1.7 — a new tag "
        "whose package still installs as the old version. Bump the version "
        "before tagging, not after.")


def test_every_released_tag_declared_its_own_version():
    """The same property, checked backwards over what has already shipped.

    A ratchet: the three known-bad tags are frozen by name. A fourth appearing
    here is a new occurrence of the same mistake, and one disappearing means a
    tag was deleted — which breaks whoever pinned it and is worth failing on.
    """
    import subprocess
    import tomllib as _tomllib

    #: Tags published before this check existed, whose package declares a
    #: different version than the tag says. Immutable, so they stay; named so
    #: a new one is visible. Two distinct causes, kept apart because the fix
    #: for one does nothing about the other:
    #:
    #:   v0.1.3, v0.1.4   the renumbering. These point at the same commits as
    #:                    v0.3.0 and v0.4.0, which declare 0.3.0 and 0.4.0.
    #:                    Renaming the line could not rewrite the commits it
    #:                    renamed, so the correct names sit on top of the wrong
    #:                    declarations. Unfixable by construction.
    #:   v0.1.5 .. v0.1.7 three releases cut without bumping the version. Each
    #:                    installs as 0.1.4. This is the one that was
    #:                    preventable and that the check above now prevents.
    KNOWN_STALE = {"v0.1.3", "v0.1.4", "v0.1.5", "v0.1.6", "v0.1.7"}

    stale = set()
    for tag in _tags():
        if tag in SUPERSEDED:                      # already documented as wrong
            continue
        blob = subprocess.run(["git", "show", f"{tag}:pyproject.toml"], cwd=ROOT,
                              capture_output=True, text=True)
        if blob.returncode != 0:
            continue
        declared = _tomllib.loads(blob.stdout)["project"]["version"]
        if f"v{declared}" != tag:
            stale.add(tag)

    new = sorted(stale - KNOWN_STALE)
    assert not new, (
        f"{new} were published declaring a different version than they claim. "
        "The package installs under the declared number, so the tag and what "
        "it installs disagree.")

    healed = sorted(KNOWN_STALE - stale)
    assert not healed, (
        f"{healed} no longer look stale. A published tag is immutable; if one "
        "was moved or deleted, whoever pinned it is now running something "
        "else. Lower this list only when a tag is genuinely gone on purpose.")
