#!/usr/bin/env python3
"""Repair the Santali autonym copies in the UI, from the brief.

Why this exists: the Ol Chiki glyphs were retyped by hand while writing the
frontend and twice a visually-identical character from a neighbouring
block (Balinese/Sundanese/Lepcha) slipped in. Hand-typing Santali is the
bug; the fix is to stop typing it entirely.

This script reads the autonym out of CLAUDE.md (the project's own brief,
which carries the string as its Ol Chiki example) and overwrites every
script-range run in the five UI files with that exact string. The UI's
only hand-written Santali is the autonym - real content always arrives
from the API at runtime - so a blanket replace there is safe.

Usage:
    python scripts/sync_autonym.py          # fix
    python scripts/sync_autonym.py --check  # exit 1 if anything is off
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Invariant: each file in this list contains ONLY the autonym as hand-written
# Ol Chiki. Real content strings must come from content/ or the API at
# runtime, never from literals - that invariant is what makes a blanket
# replace inside these files safe.
UI_FILES = [
    "frontend/index.html",
    "frontend/js/dashboard.js",
    "frontend/js/voice.js",
    "frontend/js/materials.js",
    "frontend/js/mesh.js",
    "backend/curriculum/worksheets.py",  # the worksheet table header
]

# Ol Chiki proper...
OLCHIKI = re.compile("[\U00001c50-\U00001c7f]+")
# ...plus the confusable neighbours, so corrupted fragments get swept too.
ANY_SCRIPT_RUN = re.compile("[\U00001b00-\U00001c4f\U00001c50-\U00001c7f]+")


def brief_autonym() -> str:
    tokens = OLCHIKI.findall((ROOT / "CLAUDE.md").read_text(encoding="utf-8"))
    if not tokens:
        sys.exit("CLAUDE.md contains no Ol Chiki example - cannot source the autonym")
    return max(tokens, key=len)


def main() -> int:
    check_only = "--check" in sys.argv
    autonym = brief_autonym()
    changed = 0
    for rel in UI_FILES:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        runs = ANY_SCRIPT_RUN.findall(text)
        bad = [r for r in runs if r != autonym]
        if not bad:
            continue
        if check_only:
            print(f"{rel}: {len(bad)} off-brief script run(s) {bad!r}")
            changed += 1
            continue
        fixed = ANY_SCRIPT_RUN.sub(autonym, text)
        path.write_text(fixed, encoding="utf-8")
        print(f"{rel}: replaced {len(bad)} run(s) with the brief's autonym")
        changed += 1
    if check_only:
        print("CHECK FAILED" if changed else "all autonym copies match the brief")
        return 1 if changed else 0
    print("done" if changed else "nothing to fix - every copy already matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
