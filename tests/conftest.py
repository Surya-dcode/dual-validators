import json
from pathlib import Path

from dualval import decode_special

ROOT = Path(__file__).resolve().parents[1]
VECTOR_DIR = ROOT / "vectors"


def load_vectors():
    vectors = []
    for path in sorted(VECTOR_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as fh:
            vectors.append((path.name, decode_special(json.load(fh))))
    return vectors
