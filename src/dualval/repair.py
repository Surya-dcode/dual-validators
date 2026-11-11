"""repair(doc): fix only the problems that have one obviously right answer.

Fixed automatically (each fix only removes a reference that points nowhere or
points twice, and never invents data):

* E_DANGLING_EDGE: the edge is removed.
* E_GROUP_MEMBER_MISSING: the member entry is removed.
* E_NODE_IN_TWO_GROUPS: the node stays in the first group that lists it and is
  removed from later groups.

Everything else (duplicate ids, bad numbers, negative sizes, self-loops,
oversized documents, empty labels) needs a person to decide, so repair leaves
it alone and validate() keeps reporting it.

repair is idempotent: repair(repair(doc)[0]) returns the same doc and no
changes. Node ids are never touched, so the set of valid references does not
move between runs.
"""

from __future__ import annotations

import copy
from typing import Any

from ._doc import is_node_ref, is_object, node_ids

#: Codes this function fixes. tests/test_spec.py checks it against the spec.
REPAIRS: frozenset[str] = frozenset(
    {"E_DANGLING_EDGE", "E_GROUP_MEMBER_MISSING", "E_NODE_IN_TWO_GROUPS"}
)


def repair(doc: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return (repaired copy of doc, list of changes). doc is not modified.

    Each change has code, action, path (a JSON Pointer into the input doc) and
    value (the removed edge's id, or the removed member entry).
    """
    if not is_object(doc):
        raise TypeError("doc must be a JSON object")
    out = copy.deepcopy(doc)
    changes: list[dict[str, Any]] = []
    ids = node_ids(out["nodes"] if isinstance(out.get("nodes"), list) else [])

    edges = out.get("edges")
    if isinstance(edges, list):
        kept = []
        for i, edge in enumerate(edges):
            if is_object(edge) and not (
                is_node_ref(edge.get("from"), ids) and is_node_ref(edge.get("to"), ids)
            ):
                changes.append(
                    {
                        "code": "E_DANGLING_EDGE",
                        "action": "remove_edge",
                        "path": f"/edges/{i}",
                        "value": edge.get("id"),
                    }
                )
                continue
            kept.append(edge)
        out["edges"] = kept

    groups = out.get("groups")
    if isinstance(groups, list):
        owner: dict[str, int] = {}
        for gi, group in enumerate(groups):
            if not is_object(group) or not isinstance(group.get("members"), list):
                continue
            members = []
            for mj, member in enumerate(group["members"]):
                path = f"/groups/{gi}/members/{mj}"
                if not is_node_ref(member, ids):
                    changes.append(_member_change("E_GROUP_MEMBER_MISSING", path, member))
                    continue
                if owner.setdefault(member, gi) != gi:
                    changes.append(_member_change("E_NODE_IN_TWO_GROUPS", path, member))
                    continue
                members.append(member)
            group["members"] = members

    return out, changes


def _member_change(code: str, path: str, member: Any) -> dict[str, Any]:
    return {"code": code, "action": "remove_member", "path": path, "value": member}
