"""Generate random diagram documents and check that both validators agree.

For each document, the Python implementation runs in this process and the
JavaScript one runs in Node through js/cli.js (one Node process per batch).
The two must return the same issues (code, severity, path), the same repaired
document and the same list of changes. On the first disagreement the document
is shrunk to a small one that still disagrees, printed, and the script exits 1.

    python scripts/fuzz_parity.py --n 500 --seed 1

The generator leans on the values where Python and JavaScript differ: NaN and
Infinity, integers too large for a double, -0, booleans (an int in Python),
numeric strings, ids that are Object.prototype names, ids that differ only by
case or Unicode normalization, and characters that str.strip() and
String.prototype.trim() disagree about.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dualval import decode_special, encode_special, repair, validate  # noqa: E402

CLI = ROOT / "js" / "cli.js"
MISSING = object()

ID_POOL = [
    "a",
    "A",
    "b",
    "B",
    "n1",
    "N1",
    "",
    "caf\u00e9",  # precomposed e-acute
    "cafe\u0301",  # e plus combining acute accent
    "__proto__",
    "constructor",
    "toString",
    "valueOf",
    "hasOwnProperty",
    "g1",
    "e1",
]
NON_STRING_IDS = [1, 0, None, True, 1.0, ["a"], {"id": "a"}]
ODD_NUMBERS = [
    -0.0,
    1e308,
    -1e308,
    1.7976931348623157e308,
    5e-324,
    2**53 + 1,
    10**400,
    -(10**400),
    math.nan,
    math.inf,
    -math.inf,
    "5",
    "",
    None,
    True,
    False,
    [],
    {},
]
LABELS = [
    "",
    " ",
    "\t\n",
    "\u00a0",
    "\u3000",
    "\u2003",
    "\ufeff",  # blank in the spec and in JS trim, not in Python strip
    "\u001c",  # stripped by Python, not by JS trim, not blank in the spec
    "\u001f",
    "\u0085",
    "\u200b",
    "\u180e",
    "ok",
    " ok ",
    "\u65e5\u672c\u8a9e",
    "\U0001f642",
    None,
    0,
    ["x"],
]
KINDS = ["flow", "data", "self", "retry", "Self", "", None, 3]
NON_OBJECTS = [None, 0, "node", [], True]


def pick_number(rng: random.Random) -> Any:
    roll = rng.random()
    if roll < 0.08:
        return MISSING
    if roll < 0.30:
        return rng.choice(ODD_NUMBERS)
    if roll < 0.65:
        return rng.randint(-5, 200)
    return round(rng.uniform(-50, 500), rng.randint(0, 3))


def pick_id(rng: random.Random) -> Any:
    roll = rng.random()
    if roll < 0.05:
        return MISSING
    if roll < 0.12:
        return rng.choice(NON_STRING_IDS)
    if roll < 0.45:
        return rng.choice(ID_POOL)
    return f"x{rng.randint(0, 12)}"


def pick_ref(rng: random.Random, node_ids: list[Any]) -> Any:
    roll = rng.random()
    if node_ids and roll < 0.70:
        return rng.choice(node_ids)
    if roll < 0.90:
        return pick_id(rng)
    return rng.choice(NON_STRING_IDS + [MISSING])


def put(obj: dict[str, Any], key: str, value: Any) -> None:
    if value is not MISSING:
        obj[key] = value


def maybe_non_object(rng: random.Random, item: dict[str, Any]) -> Any:
    return rng.choice(NON_OBJECTS) if rng.random() < 0.04 else item


def make_doc(rng: random.Random) -> tuple[dict[str, Any], dict[str, Any] | None]:
    nodes = []
    for _ in range(rng.randint(0, 8)):
        node: dict[str, Any] = {}
        put(node, "id", pick_id(rng))
        label = rng.choice(LABELS) if rng.random() < 0.4 else f"Node {rng.randint(0, 99)}"
        put(node, "label", label)
        for field in ("x", "y", "w", "h"):
            put(node, field, pick_number(rng))
        if rng.random() < 0.3:
            put(node, "group", pick_id(rng))
        nodes.append(maybe_non_object(rng, node))
    ids = [n["id"] for n in nodes if isinstance(n, dict) and "id" in n]

    edges = []
    for _ in range(rng.randint(0, 8)):
        edge: dict[str, Any] = {}
        put(edge, "id", pick_id(rng))
        start = pick_ref(rng, ids)
        put(edge, "from", start)
        put(edge, "to", start if rng.random() < 0.15 else pick_ref(rng, ids))
        put(edge, "kind", rng.choice(KINDS) if rng.random() < 0.9 else MISSING)
        edges.append(maybe_non_object(rng, edge))

    groups = []
    for _ in range(rng.randint(0, 4)):
        group: dict[str, Any] = {}
        put(group, "id", pick_id(rng))
        group["name"] = f"Group {rng.randint(0, 9)}"
        if rng.random() < 0.08:
            group["members"] = rng.choice(["a", None, {"0": "a"}])
        elif rng.random() < 0.95:
            group["members"] = [pick_ref(rng, ids) for _ in range(rng.randint(0, 5))]
            group["members"] = [m for m in group["members"] if m is not MISSING]
        groups.append(maybe_non_object(rng, group))

    doc: dict[str, Any] = {}
    for name, items in (("nodes", nodes), ("edges", edges), ("groups", groups)):
        roll = rng.random()
        if roll < 0.04:
            continue
        doc[name] = rng.choice([None, {}, "x"]) if roll < 0.07 else items

    options = None
    if rng.random() < 0.25:
        options = {}
        if rng.random() < 0.5:
            options["maxNodes"] = rng.randint(0, 6)
        if rng.random() < 0.5:
            options["maxEdges"] = rng.randint(0, 6)
        if rng.random() < 0.5:
            options["selfLoopKinds"] = rng.sample(["self", "retry", "flow", ""], rng.randint(0, 3))
    return doc, options


# ---- comparison --------------------------------------------------------------


def canon(value: Any) -> Any:
    """A form in which equal JSON values compare equal across both languages.

    Numbers are compared as the double JavaScript would hold (so a huge int
    equals Infinity, and -0 equals 0); booleans stay distinct from numbers.
    """
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, int | float):
        try:
            number = float(value)
        except OverflowError:
            number = math.inf if value > 0 else -math.inf
        if math.isnan(number):
            return ("num", "NaN")
        return ("num", 0.0 if number == 0 else number)
    if isinstance(value, dict):
        return ("obj", {key: canon(item) for key, item in value.items()})
    if isinstance(value, list):
        return ("arr", [canon(item) for item in value])
    return value


def python_result(doc: dict[str, Any], options: dict[str, Any] | None) -> dict[str, Any]:
    issues = validate(doc, options)
    repaired, changes = repair(doc)
    return {
        "issues": [(i["code"], i["severity"], i["path"]) for i in issues],
        "repaired": canon(repaired),
        "changes": canon(changes),
    }


def js_results(cases: list[tuple[dict[str, Any], dict[str, Any] | None]]) -> list[dict[str, Any]]:
    payload = [{"doc": encode_special(doc), "options": options} for doc, options in cases]
    proc = subprocess.run(
        ["node", str(CLI), "batch"],
        input=json.dumps(payload, allow_nan=False),
        capture_output=True,
        text=True,
        check=True,
    )
    results = []
    for raw in decode_special(json.loads(proc.stdout)):
        if "error" in raw:
            results.append({"error": raw["error"]})
            continue
        results.append(
            {
                "issues": [(i["code"], i["severity"], i["path"]) for i in raw["issues"]],
                "repaired": canon(raw["repaired"]),
                "changes": canon(raw["changes"]),
            }
        )
    return results


def differences(py: dict[str, Any], js: dict[str, Any]) -> list[str]:
    if "error" in js:
        return [f"javascript raised: {js['error']}"]
    return [key for key in ("issues", "repaired", "changes") if py[key] != js[key]]


def disagreeing(cases: list[tuple[dict[str, Any], dict[str, Any] | None]]) -> list[bool]:
    js = js_results(cases)
    return [
        bool(differences(python_result(*case), res)) for case, res in zip(cases, js, strict=True)
    ]


# ---- shrinking ---------------------------------------------------------------


def reductions(doc: dict[str, Any], options: dict[str, Any] | None):
    """Yield smaller variants of (doc, options), one removal at a time."""
    if options:
        yield doc, None
        for key in options:
            smaller = dict(options)
            del smaller[key]
            yield doc, smaller
    for key in list(doc):
        smaller = copy.deepcopy(doc)
        del smaller[key]
        yield smaller, options
    for name in ("nodes", "edges", "groups"):
        items = doc.get(name)
        if not isinstance(items, list):
            continue
        for i in range(len(items)):
            smaller = copy.deepcopy(doc)
            del smaller[name][i]
            yield smaller, options
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            for key in list(item):
                smaller = copy.deepcopy(doc)
                del smaller[name][i][key]
                yield smaller, options
            members = item.get("members")
            if name == "groups" and isinstance(members, list):
                for j in range(len(members)):
                    smaller = copy.deepcopy(doc)
                    del smaller[name][i]["members"][j]
                    yield smaller, options


def shrink(doc: dict[str, Any], options: dict[str, Any] | None):
    while True:
        candidates = list(reductions(doc, options))
        if not candidates:
            return doc, options
        flags = disagreeing(candidates)
        for candidate, bad in zip(candidates, flags, strict=True):
            if bad:
                doc, options = candidate
                break
        else:
            return doc, options


def describe(value: Any) -> str:
    return json.dumps(encode_special(value), ensure_ascii=False, indent=2)


def report(doc, options, seed: int, index: int) -> None:
    py = python_result(doc, options)
    js = js_results([(doc, options)])[0]
    print(f"fuzz_parity: DISAGREEMENT (seed {seed}, document {index})")
    print(f"differs in: {', '.join(differences(py, js))}")
    print("minimal reproducing document (non-finite numbers shown as $num markers):")
    print(describe(doc))
    if options:
        print(f"options: {json.dumps(options)}")
    if "error" in js:
        return
    py_issues, js_issues = set(py["issues"]), set(js["issues"])
    for label, extra in (("python", py_issues - js_issues), ("javascript", js_issues - py_issues)):
        for code, severity, path in sorted(extra):
            print(f"only {label} reports: {code} ({severity}) at {path}")
    if py["issues"] != js["issues"] and py_issues == js_issues:
        print("same issues, different order")
    for key in ("repaired", "changes"):
        if py[key] != js[key]:
            print(f"repair {key} differ; python gives:")
            py_doc, py_changes = repair(doc)
            print(describe(py_doc if key == "repaired" else py_changes))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fuzz the two validators against each other.")
    parser.add_argument("--n", type=int, default=500, help="number of documents (default 500)")
    parser.add_argument("--seed", type=int, default=1, help="random seed (default 1)")
    parser.add_argument("--batch", type=int, default=500, help="documents per Node process")
    args = parser.parse_args(argv)

    rng = random.Random(args.seed)
    cases = [make_doc(rng) for _ in range(args.n)]
    seen: Counter[str] = Counter()

    for start in range(0, len(cases), args.batch):
        chunk = cases[start : start + args.batch]
        for offset, (case, js) in enumerate(zip(chunk, js_results(chunk), strict=True)):
            py = python_result(*case)
            seen.update(code for code, _, _ in py["issues"])
            if differences(py, js):
                doc, options = shrink(*case)
                report(doc, options, args.seed, start + offset)
                return 1

    print(f"fuzz_parity: {args.n} documents, seed {args.seed}, 0 disagreements")
    for code, count in sorted(seen.items()):
        print(f"  {code:<24} {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
