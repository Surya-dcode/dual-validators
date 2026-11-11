# dual-validators

Keep a Python validator (on the server) and a JavaScript validator (in the browser) for the same JSON document in exact agreement, using one spec and one shared set of test vectors.

The example document is a diagram: `nodes`, `edges` between them, and `groups` of nodes. The pattern applies to any document that is edited in a browser and stored by a server.

## The problem

A document that is edited in the browser and saved by a server usually gets checked twice: once in the browser, so the user sees a problem right away, and once on the server, because the server cannot trust what it receives. Those are two validators written by hand in two languages, and they drift.

Drift lets bad data in through whichever side has the weaker check:

- A check exists in the browser but not on the server. Anything that does not go through the current browser code (an old cached client, a script, an import job, another team calling the API) writes the bad data straight in.
- A check exists on the server but not in the browser. Users build up work that the server then refuses, and the browser cannot explain why.
- Both sides have the check, but they disagree on an edge case. The two languages really do differ in places a validator cares about:

| Input | Python | JavaScript |
|---|---|---|
| `NaN` in a request body | `json.loads` accepts it | `JSON.parse` rejects it, and `JSON.stringify(NaN)` writes `null` |
| `1` followed by 400 zeros | an exact `int` | `Infinity` |
| `true` as a coordinate | `isinstance(True, int)` is `True` | `typeof true` is `"boolean"` |
| label `"\u001c"` or `"\u0085"` | `str.strip()` removes it | `trim()` keeps it |
| label `"\ufeff"` | `str.strip()` keeps it | `trim()` removes it |
| id `"constructor"` | an ordinary string | found on every plain object through the prototype |
| `-0` | `-0.0 < 0` is `False` | `-0 < 0` is `false`, but `JSON.stringify(-0)` writes `0` |

Each of these is a real way for the two sides to give different answers for the same document, and each one has a vector.

## The approach

1. **One spec.** `spec/invariants.json` lists every invariant: its code, severity, repair policy, description and message. It also holds the default options and the exact set of characters that count as blank. Both implementations embed a copy (`scripts/sync_spec.py` writes them), and a test on each side checks that its copy matches.
2. **One vector set.** `vectors/*.json` holds 45 documents, each with the issues it must produce, the repaired document and the list of changes. Both test suites load every file.
3. **Two implementations** that mirror each other function by function: `src/dualval/` (Python, standard library only) and `js/src/` (plain ES modules, no dependencies). Each one registers its checks by code, and a test on each side checks that the registry holds exactly the spec's codes.
4. **A coverage check.** `scripts/check_coverage.py` fails if a spec code has no vector, if either implementation has a check for a code that is not in the spec (or lacks one that is), or if an embedded spec copy is stale.
5. **A fuzzer.** `scripts/fuzz_parity.py` generates random documents from a seed, runs both validators (Node through `js/cli.js`), and fails on any disagreement. It shrinks the failing document before printing it, so you get a few lines to debug instead of a page.

The vectors pin down the cases someone thought of. The fuzzer looks for the ones nobody thought of.

## Invariants

`validate(doc)` returns a list of issues sorted by path (array indexes compare as numbers), then by code. Each issue has `code`, `severity`, `path` and `message`. `path` is a JSON Pointer to the offending item. `code`, `severity` and `path` are the contract shared by both sides; `message` is for people and may differ in small details between languages.

| Code | Severity | Example path | Rule |
|---|---|---|---|
| `E_DUP_ID` | error | `/edges/0/id` | String ids are unique across nodes, edges and groups together. They are compared exactly, so `"a"` and `"A"` are different. Each later use is reported. |
| `E_DANGLING_EDGE` | error | `/edges/0/from` | An edge's `from` and `to` must each be the string id of an existing node. Numbers are not coerced, and a group or edge id does not count. |
| `E_SELF_LOOP` | error | `/edges/0` | `from` equal to `to` is only allowed when `kind` is in the `selfLoopKinds` option (default `["self"]`). |
| `E_GROUP_MEMBER_MISSING` | error | `/groups/0/members/1` | Every group member must be the string id of an existing node. |
| `E_NODE_IN_TWO_GROUPS` | error | `/groups/1/members/0` | A node belongs to at most one group. The first group that lists it owns it. |
| `E_BAD_NUMBER` | error | `/nodes/0/x` | `x`, `y`, `w` and `h` must be present and finite. NaN, Infinity, numbers too big for a double, strings, booleans and null all fail. |
| `E_NEGATIVE_SIZE` | error | `/nodes/0/w` | `w` and `h` must not be below zero. `-0` counts as zero. |
| `E_EMPTY_LABEL` | warning | `/nodes/0/label` | A label needs at least one character outside the spec's blank set. Missing and non-string labels also get the warning. |
| `E_TOO_LARGE` | error | `/nodes` | At most `maxNodes` nodes (default 10000) and `maxEdges` edges (default 50000). |

Shape is out of scope here. A collection that is not a list is treated as empty, and an item that is not an object is skipped. A JSON Schema check is the right tool for shape, and it would run before these invariants.

## Repair policy

`repair(doc)` returns a repaired copy and a list of changes. It never modifies its input, and it is idempotent: repairing a repaired document returns the same document and no changes.

A problem is repaired automatically only when the fix removes a reference that points nowhere (or points twice) and there is only one sensible answer. Anything that would mean guessing at the user's intent is reported and left alone.

| Code | Policy | What repair does |
|---|---|---|
| `E_DANGLING_EDGE` | fixed | Removes the edge. |
| `E_GROUP_MEMBER_MISSING` | fixed | Removes the member entry. |
| `E_NODE_IN_TWO_GROUPS` | fixed | Keeps the node in the first group that lists it and removes it from later groups. |
| `E_DUP_ID` | refused | Which of the two is the real one? Renaming either could break references held elsewhere. |
| `E_BAD_NUMBER` | refused | Replacing NaN with 0 would hide a bug and move the node. |
| `E_NEGATIVE_SIZE` | refused | Flipping the sign or clamping both change what the user drew. |
| `E_SELF_LOOP` | refused | The edge may mean something. Removing it loses data. |
| `E_TOO_LARGE` | refused | There is no safe subset to drop. |
| `E_EMPTY_LABEL` | refused | It is a warning, and there is no label to invent. |

Each change looks like `{"code": "E_DANGLING_EDGE", "action": "remove_edge", "path": "/edges/3", "value": "e7"}`. Paths refer to the input document, so they line up with the issues `validate` reported. The policy is also recorded in the spec (`"repair": "auto"` or `"refuse"`), and a test on each side checks that the implementation repairs exactly the `auto` codes.

## Quick start

### Python

```bash
pip install -e .
```

```python
from dualval import has_errors, repair, validate

doc = {
    "nodes": [{"id": "a", "label": "Start", "x": 0, "y": 0, "w": 40, "h": 20}],
    "edges": [{"id": "e1", "from": "a", "to": "gone", "kind": "flow"}],
    "groups": [],
}

validate(doc)
# [{'code': 'E_DANGLING_EDGE', 'severity': 'error', 'path': '/edges/0/to',
#   'message': 'Edge "e1" field to points to missing node "gone"'}]

fixed, changes = repair(doc)
# fixed["edges"] == []
# changes == [{'code': 'E_DANGLING_EDGE', 'action': 'remove_edge',
#              'path': '/edges/0', 'value': 'e1'}]

has_errors(validate(fixed))  # False
```

Options are passed per call and use the same names on both sides, for example `validate(doc, {"maxNodes": 500, "selfLoopKinds": ["self", "retry"]})`. An unknown option name raises an error, so a typo such as `max_nodes` cannot silently fall back to the default.

There is also a command line: `python -m dualval doc.json` prints the issues and exits 1 if any are errors, and `python -m dualval --repair doc.json` prints the repaired document and the changes.

### JavaScript

```js
import { hasErrors, repair, validate } from './js/src/index.js';

const issues = validate(doc);
const { doc: fixed, changes } = repair(doc);
hasErrors(validate(fixed)); // false
```

The modules have no dependencies and run unchanged in a browser or in Node 20 and later. `node js/cli.js validate doc.json` and `node js/cli.js repair doc.json` mirror the Python command line.

### Save guard (Flask, optional)

`examples/flask_save_guard.py` is a small endpoint built on `dualval.guard_save`. On every save it applies the safe repairs, then validates what is left. If any error remains, it answers 422 with the issue list and stores nothing. Otherwise it stores the repaired document, logs each repair, and returns the changes and any warnings.

```bash
pip install -e ".[flask]"
flask --app examples/flask_save_guard.py run
```

**Why the server checks again when the browser already did.** The browser check is there for the user. It is not a guarantee, because the browser is not the only writer and is not always running the current code. A tab opened last week still runs last week's validator. Scripts, imports, other services and anyone with `curl` never run the browser code at all. A request body can also carry values a browser could never send: Python's JSON parser accepts the bare token `NaN`, and the test suite sends one to show the endpoint refusing it. The server is the one place every write passes through, so it runs the full check on every save.

## Adding a new invariant

Suppose each node's `group` field should name a real group, and you want a code `E_UNKNOWN_GROUP` for that.

1. **Spec.** Add an entry to `spec/invariants.json` with `code`, `severity`, `repair` (`"auto"` or `"refuse"`), `description` and `message`. Run `python scripts/sync_spec.py` to update both embedded copies.
2. **Python.** Write `check_unknown_group(ctx)` in `src/dualval/validate.py`. It yields `(path, params)` pairs. Register it in `CHECKS`, in spec order. If the policy is `auto`, handle it in `src/dualval/repair.py` and add the code to `REPAIRS`.
3. **JavaScript.** Write `checkUnknownGroup(ctx)` in `js/src/validate.js` the same way and register it in `CHECKS`. Mirror any repair in `js/src/repair.js`.
4. **Vectors.** Add files to `vectors/` for the plain case and the edge cases you can think of (missing field, non-string value, ids that differ by case). For an `auto` code, include the repaired document and the changes.
5. **Fuzzer.** If the rule reads a field the generator does not produce yet, add it to `make_doc` in `scripts/fuzz_parity.py`.
6. **Run everything** (see below).

Forgetting a step fails loudly:

| You forgot | What fails |
|---|---|
| to run `sync_spec.py` | `sync_spec.py --check`, `check_coverage.py`, and the embedded-spec test on each side |
| the Python check | `tests/test_spec.py` and `check_coverage.py` ("python checks: missing E_UNKNOWN_GROUP") |
| the JavaScript check | `js/test/spec.test.js` and `check_coverage.py` ("javascript checks: missing ...") |
| the spec entry, after writing the checks | the same tests ("has E_UNKNOWN_GROUP, which is not in the spec") |
| the vectors | `check_coverage.py` ("no vector expects E_UNKNOWN_GROUP") |
| an edge case where the two sides differ | `fuzz_parity.py`, with a shrunk document that shows the difference |

## Running the tests

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"

ruff check . && ruff format --check .
pytest                                 # Python tests, every vector
(cd js && node --test)                 # JavaScript tests, every vector
python scripts/sync_spec.py --check    # embedded spec copies are current
python scripts/check_coverage.py       # spec, registries and vectors line up
python scripts/fuzz_parity.py --n 2000 --seed 1
```

The tests make no network calls. CI (`.github/workflows/ci.yml`) runs ruff and pytest on Python 3.11 and 3.12, `node --test` on Node 20, and the three parity scripts, including a fuzz run with a new seed each time. The seed is printed so a failure can be reproduced locally.

To watch the fuzzer catch a drift, replace the body of `is_blank` in `src/dualval/_doc.py` with `return text.strip() == ""` and run it. It reports a disagreement and shrinks it to a single node whose label is one control character, such as `"\u001f"`, that Python strips and JavaScript does not.

## Layout

```
spec/invariants.json          the single source of truth
vectors/*.json                shared vectors: input, issues, repaired doc, changes
src/dualval/                  Python implementation (standard library only)
  validate.py, repair.py      the checks and the safe repairs
  _doc.py, codec.py           shared helpers, NaN/Infinity markers for JSON files
  save_guard.py               framework-free server-side guard
  invariants.json             embedded spec copy (generated)
js/                           JavaScript implementation (no dependencies)
  src/validate.js, src/repair.js, src/doc.js, src/codec.js
  src/spec.js                 embedded spec copy (generated)
  cli.js                      command line, also used by the fuzzer
examples/flask_save_guard.py  optional Flask endpoint
scripts/                      sync_spec.py, check_coverage.py, fuzz_parity.py
tests/, js/test/              the two test suites
```

Standard JSON cannot hold NaN or Infinity, so the vectors write them as `{"$num": "NaN"}`, `{"$num": "Infinity"}` and `{"$num": "-Infinity"}`. Both test suites decode these markers before running the validators. Overflowing literals such as `1e400` are written as they are, because how each parser reads them is part of what is being tested.

## License

MIT. See [LICENSE](LICENSE).
