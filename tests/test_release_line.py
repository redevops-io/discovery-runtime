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


@pytest.mark.parametrize("wrong,correct", sorted(SUPERSEDED.items()))
def test_the_superseded_tags_are_documented(wrong, correct):
    """A wrong tag that nobody wrote down is a wrong tag somebody will pin.

    It cannot be deleted, so the only remaining protection is that the
    repository says what it is and what to use instead.
    """
    readme = (ROOT / "README.md").read_text()
    assert wrong in readme, f"{wrong} was published in error and is not named in the README"
    assert correct in readme, f"the README does not say {wrong} is superseded by {correct}"
