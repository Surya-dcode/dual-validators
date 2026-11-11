import importlib.util
import logging

import pytest

from conftest import ROOT
from dualval import guard_save


def node(ident, **fields):
    base = {"id": ident, "label": "N", "x": 0, "y": 0, "w": 1, "h": 1}
    base.update(fields)
    return base


def test_clean_doc_is_saved_unchanged():
    doc = {"nodes": [node("a")], "edges": [], "groups": []}
    decision = guard_save(doc)
    assert decision.ok and decision.status == 200
    assert decision.doc == doc and decision.changes == []


def test_safe_problems_are_repaired_and_logged(caplog):
    doc = {
        "nodes": [node("a")],
        "edges": [{"id": "e1", "from": "a", "to": "gone"}],
        "groups": [{"id": "g1", "members": ["a", "gone"]}],
    }
    with caplog.at_level(logging.INFO, logger="dualval.save_guard"):
        decision = guard_save(doc, doc_id="d1")
    assert decision.ok
    assert decision.doc["edges"] == []
    assert decision.doc["groups"][0]["members"] == ["a"]
    assert [c["code"] for c in decision.changes] == ["E_DANGLING_EDGE", "E_GROUP_MEMBER_MISSING"]
    assert "repaired d1: remove_edge /edges/0 (E_DANGLING_EDGE)" in caplog.text


def test_unsafe_problems_are_refused():
    doc = {"nodes": [node("a"), node("a", w=-3)]}
    decision = guard_save(doc)
    assert not decision.ok and decision.status == 422 and decision.doc is None
    assert {i["code"] for i in decision.issues} == {"E_DUP_ID", "E_NEGATIVE_SIZE"}


def test_warnings_do_not_block_a_save():
    decision = guard_save({"nodes": [node("a", label=" ")]})
    assert decision.ok
    assert [i["code"] for i in decision.issues] == ["E_EMPTY_LABEL"]


@pytest.fixture
def client():
    pytest.importorskip("flask")
    path = ROOT / "examples" / "flask_save_guard.py"
    spec = importlib.util.spec_from_file_location("flask_save_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    store = {}
    app = module.create_app(store)
    return app.test_client(), store


def test_endpoint_saves_repaired_doc(client):
    http, store = client
    doc = {"nodes": [node("a")], "edges": [{"id": "e1", "from": "a", "to": "gone"}]}
    resp = http.put("/documents/d1", json=doc)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["saved"] is True
    assert body["changes"][0]["path"] == "/edges/0"
    assert store["d1"]["edges"] == []
    assert http.get("/documents/d1").get_json() == store["d1"]


def test_endpoint_refuses_with_422(client):
    http, store = client
    resp = http.put("/documents/d2", json={"nodes": [node("a"), node("a")]})
    assert resp.status_code == 422
    body = resp.get_json()
    assert body["saved"] is False
    assert [i["code"] for i in body["issues"]] == ["E_DUP_ID"]
    assert "d2" not in store


def test_endpoint_catches_nan_a_browser_cannot_send(client):
    http, _ = client
    raw = '{"nodes": [{"id": "a", "label": "A", "x": NaN, "y": 0, "w": 1, "h": 1}]}'
    resp = http.put("/documents/d3", data=raw, content_type="application/json")
    assert resp.status_code == 422
    assert resp.get_json()["issues"][0]["path"] == "/nodes/0/x"


def test_endpoint_rejects_non_object_body(client):
    http, _ = client
    assert http.put("/documents/d4", json=[1, 2]).status_code == 400
