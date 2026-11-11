"""Carry NaN and Infinity through plain JSON.

Standard JSON has no NaN or Infinity, but bad documents contain them: Python's
json module reads and writes the bare tokens NaN and Infinity, and a
JavaScript client holds them in memory before JSON.stringify turns them into
null. The test vectors and the fuzzer need to describe such documents in files
both languages can read, so a non-finite number is written as a marker object:

    {"$num": "NaN"}   {"$num": "Infinity"}   {"$num": "-Infinity"}

js/src/codec.js is the JavaScript twin of this module.
"""

from __future__ import annotations

import math
from typing import Any

MARKER = "$num"
_DECODE = {"NaN": math.nan, "Infinity": math.inf, "-Infinity": -math.inf}


def decode_special(value: Any) -> Any:
    """Replace marker objects with real float values, recursively."""
    if isinstance(value, dict):
        if len(value) == 1 and value.get(MARKER) in _DECODE:
            return _DECODE[value[MARKER]]
        return {key: decode_special(item) for key, item in value.items()}
    if isinstance(value, list):
        return [decode_special(item) for item in value]
    return value


def encode_special(value: Any) -> Any:
    """Replace non-finite floats with marker objects, recursively."""
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return {MARKER: "NaN"}
        return {MARKER: "Infinity" if value > 0 else "-Infinity"}
    if isinstance(value, dict):
        return {key: encode_special(item) for key, item in value.items()}
    if isinstance(value, list):
        return [encode_special(item) for item in value]
    return value
