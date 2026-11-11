"""Command line: python -m dualval [--repair] FILE

Prints the issues in a diagram document as JSON and exits 1 when any
error-level issue is present. With --repair, prints the repaired document and
the list of changes instead. Use - to read from stdin.
"""

from __future__ import annotations

import argparse
import json
import sys

from .codec import decode_special, encode_special
from .repair import repair
from .validate import has_errors, validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dualval", description="Validate a diagram document.")
    parser.add_argument("file", help="path to a JSON document, or - for stdin")
    parser.add_argument("--repair", action="store_true", help="print the repaired document")
    args = parser.parse_args(argv)

    if args.file == "-":
        doc = decode_special(json.load(sys.stdin))
    else:
        with open(args.file, encoding="utf-8") as fh:
            doc = decode_special(json.load(fh))

    if args.repair:
        repaired, changes = repair(doc)
        out = {"doc": repaired, "changes": changes}
        print(json.dumps(encode_special(out), indent=2, ensure_ascii=False))
        return 0

    issues = validate(doc)
    print(json.dumps(issues, indent=2, ensure_ascii=False))
    return 1 if has_errors(issues) else 0


if __name__ == "__main__":
    sys.exit(main())
