"""Run every shared vector in vectors/ through the Python implementation.

js/test/vectors.test.js runs the same files through the JavaScript one.
"""

import copy

import pytest

from conftest import load_vectors
from dualval import encode_special, repair, validate
from dualval.repair import REPAIRS

VECTORS = load_vectors()
IDS = [name for name, _ in VECTORS]


def triples(issues):
    return [{"code": i["code"], "severity": i["severity"], "path": i["path"]} for i in issues]


def comparable(doc):
    # NaN != NaN, so compare the marker form instead.
    return encode_special(doc)


def test_enough_vectors():
    assert len(VECTORS) >= 25


@pytest.mark.parametrize(("name", "vector"), VECTORS, ids=IDS)
def test_validate(name, vector):
    issues = validate(vector["input"], vector.get("options"))
    assert triples(issues) == vector["expected_issues"]
    assert all(issue["message"] for issue in issues)


@pytest.mark.parametrize(("name", "vector"), VECTORS, ids=IDS)
def test_repair(name, vector):
    before = comparable(vector["input"])
    repaired, changes = repair(vector["input"])
    assert comparable(repaired) == comparable(vector["expected_repaired"])
    assert changes == vector["expected_changes"]
    assert comparable(vector["input"]) == before, "repair must not modify its input"


@pytest.mark.parametrize(("name", "vector"), VECTORS, ids=IDS)
def test_repair_is_idempotent(name, vector):
    once, _ = repair(vector["input"])
    twice, changes = repair(copy.deepcopy(once))
    assert changes == []
    assert comparable(twice) == comparable(once)


@pytest.mark.parametrize(("name", "vector"), VECTORS, ids=IDS)
def test_repaired_doc_has_no_repairable_issues(name, vector):
    repaired, _ = repair(vector["input"])
    left = {i["code"] for i in validate(repaired, vector.get("options"))}
    assert not left & REPAIRS


@pytest.mark.parametrize(("name", "vector"), VECTORS, ids=IDS)
def test_changes_match_reported_issues(name, vector):
    """Every repair change answers an issue validate() reported at that place."""
    issues = validate(vector["input"], vector.get("options"))
    reported = {(i["code"], i["path"]) for i in issues}
    for change in vector["expected_changes"]:
        if change["action"] == "remove_edge":
            assert any(
                code == change["code"] and path.startswith(change["path"] + "/")
                for code, path in reported
            )
        else:
            assert (change["code"], change["path"]) in reported
