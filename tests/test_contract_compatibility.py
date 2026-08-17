"""The declared contracts version is the one this package is tested against.

This file exists because these two repositories drifted apart silently and nobody found out until a
third one tried to use both. `discovery-runtime` 0.2.0 declared a dependency on `runtime-contracts`
and was written against an older shape of it:

    DecisionEvidence(field, value, source_type, source_ref)     what this package expected
    DecisionEvidence(reader_id, kind, value, confidence, ...)   what the contract has

Positionally that put free text where a decimal string belongs, and the contract refused it —
correctly. `VerifiedIntent` had moved further still: no `interpreted`, no top-level `evidence`, no
`content_hash`, and `fields` mapping each dimension to an `IntentField` that carries its own author,
provenance and evidence. Every conformance test failed, and none of it was visible from inside
either repository alone.

So these tests assert the *seam*: that the names this package imports exist, mean what it assumes,
and come from the version it declares. They fail on the day the contract moves rather than on the
day a consumer integrates.
"""
from __future__ import annotations

import dataclasses
import pathlib
import tomllib
from importlib.metadata import version

import pytest

import runtime_contracts

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _declared_dependency() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    for entry in data["project"]["dependencies"]:
        if entry.replace("_", "-").startswith("runtime-contracts"):
            return entry
    raise AssertionError("runtime-contracts is not declared as a dependency")


def test_the_contracts_dependency_is_declared():
    """It is a hard dependency, not an optional one.

    A package whose core types come from somewhere else and that starts anyway when that somewhere
    is missing will fail later, further from the cause.
    """
    assert _declared_dependency()


def test_the_installed_contracts_version_is_the_one_under_test():
    """What is installed is what these tests prove something about.

    A green suite against a version nobody deploys is the shape of the failure this file exists to
    prevent — and it is not hypothetical here, since the whole incompatibility survived a green
    suite in each repository separately.
    """
    installed = version("runtime-contracts")
    assert installed, "runtime-contracts is not installed"

    declared = _declared_dependency()
    pinned = ""
    for marker in ("==", "@v"):
        if marker in declared:
            pinned = declared.split(marker, 1)[1].strip().strip("'\"")
            break
    if pinned:
        assert installed == pinned, (
            f"pyproject declares runtime-contracts {pinned} and {installed} is installed; "
            "these tests describe the installed one")


#: What this package constructs, and the fields it passes by name. Checked against the contract's
#: own dataclass definition rather than by constructing and hoping — a constructor that silently
#: accepts an unexpected keyword would pass a smoke test and mean nothing.
REQUIRED_FIELDS = {
    "DecisionEvidence": {"reader_id", "kind", "value", "source_ref"},
    "IntentField": {"value", "author", "produced_by", "source_span", "evidence", "contested"},
    "Unresolved": {"dimension", "reason", "detail", "evidence", "result_changing"},
    "Amendment": {"dimension", "from_value", "to_value", "author"},
    "VerifiedIntent": {"objective", "fields", "unresolved", "amendments", "state",
                       "produced_by", "utterance_ref"},
}


@pytest.mark.parametrize("name,expected", sorted(REQUIRED_FIELDS.items()))
def test_the_contract_types_have_the_fields_this_package_passes(name, expected):
    """Named per type, so a failure says which one moved."""
    kind = getattr(runtime_contracts, name, None)
    assert kind is not None, f"runtime_contracts no longer exports {name}"

    present = {f.name for f in dataclasses.fields(kind)}
    missing = expected - present
    assert not missing, (
        f"{name} no longer has {sorted(missing)}. This package constructs it by those names; "
        f"it now has {sorted(present)}.")


def test_decision_evidence_does_not_carry_its_own_dimension():
    """The absence is load-bearing, so it is asserted rather than assumed.

    Evidence is filed under the dimension it supports — `VerifiedIntent.fields` maps a name to an
    `IntentField` and the evidence hangs off that. A `field` attribute on the evidence itself would
    be a second answer to "which dimension is this about", with no rule for which wins. This
    package had one, and reintroducing it is how the last incompatibility started.
    """
    present = {f.name for f in dataclasses.fields(runtime_contracts.DecisionEvidence)}
    assert "field" not in present and "dimension" not in present, (
        "DecisionEvidence has grown a dimension attribute; evidence is filed under the dimension "
        "it supports, and carrying it in both places lets them disagree")


#: The behaviour this package delegates rather than implements. Sealing and identity belong to the
#: contract: every consumer must agree on them or an intent sealed by one is not the intent another
#: reads back.
DELEGATED = ("seal", "intent_hash", "unsealable", "blocking", "is_verified", "value")


@pytest.mark.parametrize("member", DELEGATED)
def test_the_contract_still_owns_what_this_package_delegates(member):
    assert hasattr(runtime_contracts.VerifiedIntent, member), (
        f"VerifiedIntent.{member} is gone; this package forwards to it rather than reimplementing "
        "it, and two implementations of sealing is the duplication the extraction removed")


def test_not_sealable_is_the_contracts_error():
    """The error a caller catches must be the contract's.

    This package raised a `SealError` of its own, which no other consumer of the same contract
    could catch — so a domain handling a failed seal would work against one runtime and not the
    other.
    """
    from discovery_runtime import NotSealable

    assert NotSealable is runtime_contracts.NotSealable
