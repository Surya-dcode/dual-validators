"""A minimal Flask endpoint that guards saves with dualval.

    pip install -e ".[flask]"
    flask --app examples/flask_save_guard.py run

    curl -X PUT localhost:5000/documents/demo \
         -H 'Content-Type: application/json' \
         -d '{"nodes": [{"id": "a", "label": "A", "x": 0, "y": 0, "w": 1, "h": 1}],
              "edges": [{"id": "e1", "from": "a", "to": "gone"}]}'

The browser runs the JavaScript validator before it sends a save, and this
endpoint runs the Python one again anyway. A tab opened last week still runs
last week's checks, and scripts, imports and other API consumers never run the
browser code at all. The server is the one place every write passes through.

Responses:

* 200 with the stored (repaired) document, the repairs that were applied and
  any warnings;
* 422 with the issue list when an error is left after the safe repairs;
* 400 when the body is not a JSON object.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, jsonify, request

from dualval import guard_save


def create_app(store: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    documents: dict[str, Any] = {} if store is None else store
    logging.getLogger("dualval.save_guard").setLevel(logging.INFO)

    @app.put("/documents/<doc_id>")
    def save_document(doc_id: str):
        # Python's json module accepts the bare tokens NaN and Infinity, so a
        # hand-written request can carry values a browser could never send.
        doc = request.get_json(silent=True)
        if not isinstance(doc, dict):
            return jsonify(error="body must be a JSON object"), 400

        decision = guard_save(doc, doc_id=doc_id)
        if not decision.ok:
            return jsonify(saved=False, issues=decision.issues, changes=decision.changes), 422

        documents[doc_id] = decision.doc
        return jsonify(
            saved=True,
            doc=decision.doc,
            changes=decision.changes,
            warnings=[i for i in decision.issues if i["severity"] == "warning"],
        )

    @app.get("/documents/<doc_id>")
    def load_document(doc_id: str):
        if doc_id not in documents:
            return jsonify(error="not found"), 404
        return jsonify(documents[doc_id])

    return app


app = create_app()
