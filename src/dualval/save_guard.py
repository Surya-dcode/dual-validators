"""Server-side save guard, independent of any web framework.

The browser runs the same checks before it sends a save, so why check again?
Because the browser is not the only writer, and not always the current one:

* an old client cached in someone's tab still runs last month's validator;
* scripts, imports and other API consumers never run the browser code at all;
* anyone can send a request by hand.

The server is the last place every write passes through, so it re-runs the
full check on every save. guard_save() applies the safe repairs first, then
refuses the save if any error-level issue is left.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .repair import repair
from .validate import validate

log = logging.getLogger("dualval.save_guard")


@dataclass
class SaveDecision:
    ok: bool
    status: int
    doc: dict[str, Any] | None
    issues: list[dict[str, str]] = field(default_factory=list)
    changes: list[dict[str, Any]] = field(default_factory=list)


def guard_save(
    doc: dict[str, Any], options: dict[str, Any] | None = None, *, doc_id: str = "?"
) -> SaveDecision:
    """Decide whether doc may be stored.

    Returns status 200 with the repaired doc (and any warnings) when it may,
    or 422 with the remaining issues when an error is left after repair.
    """
    repaired, changes = repair(doc)
    issues = validate(repaired, options)
    errors = [issue for issue in issues if issue["severity"] == "error"]
    if errors:
        log.info("refused save of %s: %s", doc_id, ", ".join(sorted({e["code"] for e in errors})))
        return SaveDecision(False, 422, None, issues, changes)
    for change in changes:
        log.info(
            "repaired %s: %s %s (%s)", doc_id, change["action"], change["path"], change["code"]
        )
    return SaveDecision(True, 200, repaired, issues, changes)
