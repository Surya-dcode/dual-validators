"""validate(doc) for diagram documents.

Every check is registered in CHECKS under the code it reports. A check yields
(path, message params) pairs and never chooses its own code, so a check cannot
report a code it does not own. tests/test_spec.py checks that CHECKS holds
exactly the codes in spec/invariants.json.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from ._doc import (
    NUMBER_FIELDS,
    SIZE_FIELDS,
    as_list,
    is_blank,
    is_finite_number,
    is_node_ref,
    is_object,
    node_ids,
    resolve_options,
    show,
)
from .spec import INVARIANTS

Finding = tuple[str, dict[str, str]]


@dataclass(frozen=True)
class Context:
    nodes: list[Any]
    edges: list[Any]
    groups: list[Any]
    node_ids: frozenset[str]
    options: dict[str, Any]


def build_context(doc: dict[str, Any], options: dict[str, Any] | None) -> Context:
    if not is_object(doc):
        raise TypeError("doc must be a JSON object")
    nodes = as_list(doc.get("nodes"))
    return Context(
        nodes=nodes,
        edges=as_list(doc.get("edges")),
        groups=as_list(doc.get("groups")),
        node_ids=node_ids(nodes),
        options=resolve_options(options),
    )


def check_dup_id(ctx: Context) -> Iterator[Finding]:
    first_seen: dict[str, str] = {}
    for name, items in (("nodes", ctx.nodes), ("edges", ctx.edges), ("groups", ctx.groups)):
        for i, item in enumerate(items):
            if not is_object(item) or not isinstance(item.get("id"), str):
                continue
            ident = item["id"]
            path = f"/{name}/{i}/id"
            if ident in first_seen:
                yield path, {"id": show(ident), "first": first_seen[ident]}
            else:
                first_seen[ident] = path


def check_dangling_edge(ctx: Context) -> Iterator[Finding]:
    for i, edge in enumerate(ctx.edges):
        if not is_object(edge):
            continue
        for end in ("from", "to"):
            ref = edge.get(end)
            if not is_node_ref(ref, ctx.node_ids):
                yield (
                    f"/edges/{i}/{end}",
                    {"edge": show(edge.get("id")), "end": end, "ref": show(ref)},
                )


def check_self_loop(ctx: Context) -> Iterator[Finding]:
    allowed = ctx.options["selfLoopKinds"]
    for i, edge in enumerate(ctx.edges):
        if not is_object(edge):
            continue
        start, end = edge.get("from"), edge.get("to")
        if not isinstance(start, str) or start != end:
            continue
        kind = edge.get("kind")
        if isinstance(kind, str) and kind in allowed:
            continue
        yield f"/edges/{i}", {"edge": show(edge.get("id")), "node": show(start), "kind": show(kind)}


def check_group_member_missing(ctx: Context) -> Iterator[Finding]:
    for gi, group in enumerate(ctx.groups):
        if not is_object(group) or not isinstance(group.get("members"), list):
            continue
        for mj, member in enumerate(group["members"]):
            if not is_node_ref(member, ctx.node_ids):
                yield (
                    f"/groups/{gi}/members/{mj}",
                    {"group": show(group.get("id")), "ref": show(member)},
                )


def check_node_in_two_groups(ctx: Context) -> Iterator[Finding]:
    owner: dict[str, int] = {}
    for gi, group in enumerate(ctx.groups):
        if not is_object(group) or not isinstance(group.get("members"), list):
            continue
        for mj, member in enumerate(group["members"]):
            if not is_node_ref(member, ctx.node_ids):
                continue
            if member not in owner:
                owner[member] = gi
            elif owner[member] != gi:
                first = ctx.groups[owner[member]]
                yield (
                    f"/groups/{gi}/members/{mj}",
                    {"node": show(member), "first": show(first.get("id"))},
                )


def check_bad_number(ctx: Context) -> Iterator[Finding]:
    for i, node in enumerate(ctx.nodes):
        if not is_object(node):
            continue
        for field in NUMBER_FIELDS:
            if not is_finite_number(node.get(field)):
                yield f"/nodes/{i}/{field}", {"node": show(node.get("id")), "field": field}


def check_negative_size(ctx: Context) -> Iterator[Finding]:
    for i, node in enumerate(ctx.nodes):
        if not is_object(node):
            continue
        for field in SIZE_FIELDS:
            value = node.get(field)
            if is_finite_number(value) and value < 0:
                yield f"/nodes/{i}/{field}", {"node": show(node.get("id")), "field": field}


def check_empty_label(ctx: Context) -> Iterator[Finding]:
    for i, node in enumerate(ctx.nodes):
        if not is_object(node):
            continue
        label = node.get("label")
        if not isinstance(label, str) or is_blank(label):
            yield f"/nodes/{i}/label", {"node": show(node.get("id"))}


def check_too_large(ctx: Context) -> Iterator[Finding]:
    limits = (
        ("nodes", ctx.nodes, ctx.options["maxNodes"]),
        ("edges", ctx.edges, ctx.options["maxEdges"]),
    )
    for name, items, limit in limits:
        if len(items) > limit:
            yield f"/{name}", {"collection": name, "count": str(len(items)), "limit": str(limit)}


#: code -> check function, in spec order.
CHECKS: dict[str, Callable[[Context], Iterator[Finding]]] = {
    "E_DUP_ID": check_dup_id,
    "E_DANGLING_EDGE": check_dangling_edge,
    "E_SELF_LOOP": check_self_loop,
    "E_GROUP_MEMBER_MISSING": check_group_member_missing,
    "E_NODE_IN_TWO_GROUPS": check_node_in_two_groups,
    "E_BAD_NUMBER": check_bad_number,
    "E_NEGATIVE_SIZE": check_negative_size,
    "E_EMPTY_LABEL": check_empty_label,
    "E_TOO_LARGE": check_too_large,
}

_PLACEHOLDER = re.compile(r"\{([A-Za-z]+)\}")
_INDEX = re.compile(r"[0-9]+")


def render(template: str, params: dict[str, str]) -> str:
    return _PLACEHOLDER.sub(lambda m: params.get(m.group(1), m.group(0)), template)


def path_key(path: str) -> tuple[tuple[int, int | str], ...]:
    """Sort key for a JSON Pointer: array indexes compare as numbers and sort
    before names, and a path sorts before the paths below it."""
    return tuple(
        (0, int(seg)) if _INDEX.fullmatch(seg) else (1, seg) for seg in path.split("/")[1:]
    )


def issue_sort_key(issue: dict[str, str]) -> tuple[Any, str]:
    return path_key(issue["path"]), issue["code"]


def validate(doc: dict[str, Any], options: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """Return every invariant problem in doc, sorted by path then code.

    Each issue is a dict with code, severity, path (a JSON Pointer into doc)
    and message. code, severity and path are the contract shared with the
    JavaScript implementation; message is for people and may differ in detail.
    """
    ctx = build_context(doc, options)
    issues = []
    for code, check in CHECKS.items():
        inv = INVARIANTS[code]
        for path, params in check(ctx):
            issues.append(
                {
                    "code": code,
                    "severity": inv["severity"],
                    "path": path,
                    "message": render(inv["message"], params),
                }
            )
    issues.sort(key=issue_sort_key)
    return issues


def has_errors(issues: list[dict[str, str]]) -> bool:
    return any(issue["severity"] == "error" for issue in issues)
