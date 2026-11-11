"""Fail when the spec, the two implementations and the vectors drift apart.

Checks, in order:

1. both embedded copies of the spec match spec/invariants.json;
2. the Python and JavaScript check registries hold exactly the spec's codes
   (a code missing from the spec, or a spec code with no check, both fail);
3. the Python and JavaScript repair registries hold exactly the codes the spec
   marks "auto";
4. every spec code is expected by at least one vector, every "auto" code is
   repaired in at least one vector, and no vector expects a code the spec does
   not define.

    python scripts/check_coverage.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import sync_spec  # noqa: E402

from dualval import CHECKS, REPAIRS  # noqa: E402


def js_registries() -> dict[str, list[str]]:
    out = subprocess.run(
        ["node", str(ROOT / "js" / "cli.js"), "codes"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(out)


def compare(label: str, actual: set[str], expected: set[str], problems: list[str]) -> None:
    for code in sorted(expected - actual):
        problems.append(f"{label}: missing {code}")
    for code in sorted(actual - expected):
        problems.append(f"{label}: has {code}, which is not in the spec")


def main() -> int:
    problems: list[str] = []

    for path in sync_spec.stale_copies():
        problems.append(f"{path.relative_to(ROOT)} is stale; run python scripts/sync_spec.py")

    spec = json.loads((ROOT / "spec" / "invariants.json").read_text(encoding="utf-8"))
    codes = {inv["code"] for inv in spec["invariants"]}
    auto = {inv["code"] for inv in spec["invariants"] if inv["repair"] == "auto"}

    js = js_registries()
    compare("python checks", set(CHECKS), codes, problems)
    compare("javascript checks", set(js["checks"]), codes, problems)
    compare("python repairs", set(REPAIRS), auto, problems)
    compare("javascript repairs", set(js["repairs"]), auto, problems)

    expected: dict[str, int] = dict.fromkeys(sorted(codes), 0)
    repaired: dict[str, int] = dict.fromkeys(sorted(auto), 0)
    vector_files = sorted((ROOT / "vectors").glob("*.json"))
    for path in vector_files:
        vector = json.loads(path.read_text(encoding="utf-8"))
        for issue in vector["expected_issues"]:
            if issue["code"] not in codes:
                problems.append(f"{path.name}: expects unknown code {issue['code']}")
            else:
                expected[issue["code"]] += 1
        for change in vector["expected_changes"]:
            if change["code"] in repaired:
                repaired[change["code"]] += 1
            else:
                problems.append(f"{path.name}: repairs {change['code']}, which is not 'auto'")

    for code, count in expected.items():
        if count == 0:
            problems.append(f"vectors: no vector expects {code}")
    for code, count in repaired.items():
        if count == 0:
            problems.append(f"vectors: no vector shows a repair for {code}")

    if problems:
        print("check_coverage: FAILED")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(f"check_coverage: {len(codes)} codes, {len(vector_files)} vectors")
    width = max(len(code) for code in expected)
    for code, count in expected.items():
        note = f", repaired in {repaired[code]}" if code in repaired else ""
        print(f"  {code:<{width}}  expected {count} times{note}")
    print("  python and javascript registries match the spec")
    return 0


if __name__ == "__main__":
    sys.exit(main())
