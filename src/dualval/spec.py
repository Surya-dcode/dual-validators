"""Load the embedded copy of spec/invariants.json.

The copy next to this file is written by scripts/sync_spec.py. Do not edit it
by hand; edit spec/invariants.json and run the script.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any


def _load() -> dict[str, Any]:
    with resources.files("dualval").joinpath("invariants.json").open(encoding="utf-8") as fh:
        return json.load(fh)


SPEC: dict[str, Any] = _load()

#: Invariant entries keyed by code, in spec order.
INVARIANTS: dict[str, dict[str, Any]] = {inv["code"]: inv for inv in SPEC["invariants"]}

#: Default validation options. Callers override them per call.
DEFAULTS: dict[str, Any] = SPEC["defaults"]

#: Characters that do not count as label content (see E_EMPTY_LABEL).
BLANK_CHARS: frozenset[str] = frozenset(chr(int(cp[2:], 16)) for cp in SPEC["blankCodePoints"])

#: Codes that repair() is allowed to fix.
AUTO_REPAIR_CODES: frozenset[str] = frozenset(
    code for code, inv in INVARIANTS.items() if inv["repair"] == "auto"
)
