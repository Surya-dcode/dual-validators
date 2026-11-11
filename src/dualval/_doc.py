"""Small helpers shared by validate() and repair().

Each helper has a twin with the same name in js/src/doc.js. When one changes,
the other must change the same way; the shared vectors and the fuzzer check
that they still agree.
"""

from __future__ import annotations

import json
import math
from typing import Any

from .spec import BLANK_CHARS, DEFAULTS

COLLECTIONS = ("nodes", "edges", "groups")
NUMBER_FIELDS = ("x", "y", "w", "h")
SIZE_FIELDS = ("w", "h")


def is_object(value: Any) -> bool:
    """True for a JSON object (a dict)."""
    return isinstance(value, dict)


def as_list(value: Any) -> list[Any]:
    """A collection that is not a list is treated as empty.

    Shape checks (is `nodes` a list of objects?) belong to a schema layer that
    runs before these invariants.
    """
    return value if isinstance(value, list) else []


def is_finite_number(value: Any) -> bool:
    """True for a number that a JavaScript client would hold as a finite double.

    bool is a subclass of int in Python, so it is excluded first. An int too
    large for a 64-bit float parses as Infinity in JavaScript, so it is not
    finite here either.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        try:
            return math.isfinite(float(value))
        except OverflowError:
            return False
    if isinstance(value, float):
        return math.isfinite(value)
    return False


def is_blank(text: str) -> bool:
    """True when every character is in the spec's blank set.

    This deliberately does not use str.strip(): Python treats U+001C..U+001F
    and U+0085 as whitespace and does not treat U+FEFF as whitespace, while
    JavaScript's String.prototype.trim does the opposite.
    """
    return all(ch in BLANK_CHARS for ch in text)


def node_ids(nodes: list[Any]) -> frozenset[str]:
    """String ids of every node object. Duplicated ids still count as present."""
    return frozenset(
        node["id"] for node in nodes if is_object(node) and isinstance(node.get("id"), str)
    )


def is_node_ref(value: Any, ids: frozenset[str]) -> bool:
    return isinstance(value, str) and value in ids


def resolve_options(options: dict[str, Any] | None) -> dict[str, Any]:
    resolved = {key: (list(val) if isinstance(val, list) else val) for key, val in DEFAULTS.items()}
    if options:
        unknown = sorted(set(options) - set(DEFAULTS))
        if unknown:
            raise ValueError(f"unknown option(s): {', '.join(unknown)}")
        resolved.update(options)
    return resolved


def show(value: Any) -> str:
    """Render a document value for a human-readable message."""
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(value)
