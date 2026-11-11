"""dualval: one spec, two validators (Python and JavaScript) that agree exactly."""

from .codec import decode_special, encode_special
from .repair import REPAIRS, repair
from .save_guard import SaveDecision, guard_save
from .spec import INVARIANTS, SPEC
from .validate import CHECKS, has_errors, validate

__all__ = [
    "CHECKS",
    "INVARIANTS",
    "REPAIRS",
    "SPEC",
    "SaveDecision",
    "decode_special",
    "encode_special",
    "guard_save",
    "has_errors",
    "repair",
    "validate",
]

__version__ = "0.1.0"
