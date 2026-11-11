import io
import json
import math

import pytest

from dualval import decode_special, encode_special, has_errors, repair, validate
from dualval.__main__ import main
from dualval._doc import is_blank, is_finite_number
from dualval.validate import path_key


def node(ident, **fields):
    base = {"id": ident, "label": "N", "x": 0, "y": 0, "w": 1, "h": 1}
    base.update(fields)
    return base


def test_non_object_doc_is_rejected():
    for bad in (None, [], "doc", 3):
        with pytest.raises(TypeError):
            validate(bad)
        with pytest.raises(TypeError):
            repair(bad)


def test_unknown_option_is_rejected():
    with pytest.raises(ValueError, match="max_nodes"):
        validate({}, {"max_nodes": 3})


def test_options_do_not_leak_between_calls():
    doc = {"nodes": [node("a"), node("b")]}
    assert validate(doc, {"maxNodes": 1})
    assert validate(doc) == []


def test_messages_are_filled_in():
    doc = {"nodes": [node("a")], "edges": [{"id": "e1", "from": "a", "to": "zz"}]}
    (issue,) = validate(doc)
    assert issue["message"] == 'Edge "e1" field to points to missing node "zz"'


def test_has_errors_ignores_warnings():
    assert not has_errors(validate({"nodes": [node("a", label="")]}))
    assert has_errors(validate({"nodes": [node("a", w=-1)]}))


def test_finite_number_rules():
    assert is_finite_number(0)
    assert is_finite_number(-0.0)
    assert is_finite_number(10**300)
    assert not is_finite_number(10**400)
    assert not is_finite_number(True)
    assert not is_finite_number(math.nan)
    assert not is_finite_number("1")


def test_blank_differs_from_str_strip():
    # These are exactly the characters where str.strip() and the spec disagree.
    assert not is_blank("\x1c") and "\x1c".strip() == ""
    assert not is_blank("\x85") and "\x85".strip() == ""
    assert is_blank("\ufeff") and "\ufeff".strip() != ""


def test_path_key_orders_indexes_numerically():
    paths = ["/nodes/10/w", "/nodes/2/x", "/nodes/2", "/edges/0/to", "/edges/0"]
    assert sorted(paths, key=path_key) == [
        "/edges/0",
        "/edges/0/to",
        "/nodes/2",
        "/nodes/2/x",
        "/nodes/10/w",
    ]


def test_codec_round_trip():
    value = {"a": [math.nan, math.inf, -math.inf, 1.5, {"$num": "other"}]}
    encoded = encode_special(value)
    assert json.dumps(encoded, allow_nan=False)
    decoded = decode_special(encoded)
    assert math.isnan(decoded["a"][0])
    assert decoded["a"][1:] == [math.inf, -math.inf, 1.5, {"$num": "other"}]


def test_cli_reports_and_exits_nonzero(tmp_path, capsys):
    doc_path = tmp_path / "doc.json"
    doc_path.write_text(json.dumps({"nodes": [node("a", x={"$num": "NaN"})]}))
    assert main([str(doc_path)]) == 1
    issues = json.loads(capsys.readouterr().out)
    assert [i["code"] for i in issues] == ["E_BAD_NUMBER"]


def test_cli_repair_from_stdin(monkeypatch, capsys):
    doc = {"nodes": [node("a")], "edges": [{"id": "e", "from": "a", "to": "b"}]}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(doc)))
    assert main(["--repair", "-"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["doc"]["edges"] == []
    assert out["changes"][0]["code"] == "E_DANGLING_EDGE"
