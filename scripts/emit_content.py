"""Generate the JSON data files under content/ from content/seed.py.

Usage:
    python3 scripts/emit_content.py

Idempotent - safe to re-run after editing the seed. The generated files are
the ones the app actually loads (see backend/config.py paths).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from content.seed import DEMO_SENTENCES, FLN_OUTCOMES, LEXICON  # noqa: E402

TARGETS = {
    ROOT / "content" / "vocabulary" / "lexicon.json": LEXICON,
    ROOT / "content" / "lessons" / "fln_outcomes.json": FLN_OUTCOMES,
    ROOT / "content" / "demo" / "demo_sentences.json": DEMO_SENTENCES,
}


def main() -> None:
    for path, data in TARGETS.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
