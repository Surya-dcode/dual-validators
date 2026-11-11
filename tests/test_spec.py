"""The Python side implements exactly the invariants in spec/invariants.json."""

import json

from conftest import ROOT
from dualval import CHECKS, INVARIANTS, REPAIRS, SPEC


def repo_spec():
    return json.loads((ROOT / "spec" / "invariants.json").read_text(encoding="utf-8"))


def test_embedded_spec_matches_repo_spec():
    assert repo_spec() == SPEC


def test_checks_cover_exactly_the_spec_codes():
    spec_codes = [inv["code"] for inv in repo_spec()["invariants"]]
    assert list(CHECKS) == spec_codes


def test_repairs_cover_exactly_the_auto_codes():
    auto = {inv["code"] for inv in repo_spec()["invariants"] if inv["repair"] == "auto"}
    assert set(REPAIRS) == auto


def test_spec_entries_are_well_formed():
    codes = [inv["code"] for inv in SPEC["invariants"]]
    assert len(codes) == len(set(codes))
    for inv in INVARIANTS.values():
        assert inv["code"].startswith("E_")
        assert inv["severity"] in {"error", "warning"}
        assert inv["repair"] in {"auto", "refuse"}
        assert inv["description"] and inv["message"]


def test_blank_code_points_parse():
    for cp in SPEC["blankCodePoints"]:
        assert cp.startswith("U+") and len(cp) == 6
        int(cp[2:], 16)
