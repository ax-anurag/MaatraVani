"""Script-integrity tests: the Ol Chiki in this repo is real or it fails.

Santali is rendered in Ol Chiki, a Unicode block with visually confusable
neighbours (Balinese, Sundanese, Batak, Lepcha). Retyping the glyphs by
hand is exactly how a stray foreign character gets in - it happened twice
while building this project, which is why this file exists.

Two rules, enforced repo-wide:
  1. no character from the neighbouring blocks may appear anywhere in
     our source/content files (corruption detector);
  2. every Ol Chiki token that ships in the UI must equal the autonym
     token from the project brief itself (CLAUDE.md), copied - not
     retyped - at runtime by this test.
"""

import re
from pathlib import Path

from conftest import ROOT, brief_autonym

# Blocks that are NOT Ol Chiki but look like it: Balinese, Sundanese,
# Sundanese Supplement, Batak, Lepcha, and the gap above Ol Chiki.
# Ol Chiki proper is U+1C50..U+1C7F; anything else in U+1B00..U+1C7F is a
# red flag. (U+1C80+ is Cyrillic Extended-C, included for the same reason.)
_SUSPECT = re.compile("[\U00001b00-\U00001c4f\U00001c80-\U00001cbf]")
_OLCHIKI = re.compile("[\U00001c50-\U00001c7f]+")

SCAN_EXCLUDE = {".git", ".venv", ".venv-convert", "__pycache__", "models",
                "generated", "fonts", "node_modules", ".pytest_cache",
                # .venv-convert is the one-time NLLB conversion venv (see
                # scripts/download_models.py): third-party sources, git-ignored,
                # same story as .venv itself.
                # .cache holds raw fetched evidence dumps (see
                # scripts/collect_lexicon_evidence.py): external pages that
                # may legitimately contain other scripts. They are git-ignored
                # raw material; only what we ship gets scanned. The *extracted*
                # record at content/vocabulary/evidence.json is checked in
                # and stays inside the scan.
                ".cache"}
SCAN_SUFFIXES = {".py", ".js", ".html", ".css", ".json", ".md", ".sh", ".txt", ".example"}


def _repo_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
            continue
        if any(part in SCAN_EXCLUDE for part in path.parts):
            continue
        yield path


def test_no_confusable_script_characters_anywhere():
    """A Balinese/Sundanese/Batak/Lepcha glyph in our sources means
    corrupted Santali text - fail loudly with the exact location."""
    offenders = []
    for path in _repo_text_files():
        text = path.read_text(encoding="utf-8")
        for m in _SUSPECT.finditer(text):
            offenders.append(
                f"{path.relative_to(ROOT)}: U+{ord(m.group(0)):04X}")
    assert not offenders, (
        "Confusable non-Ol-Chiki script characters found (retyped-glyph "
        "corruption):\n" + "\n".join(offenders)
    )


def test_ui_autonym_matches_the_brief():
    """Every Ol Chiki token shown by the UI must be the brief's own
    autonym string - copied from CLAUDE.md, byte for byte."""
    expected = brief_autonym()
    assert _OLCHIKI.search(expected), "brief autonym must be Ol Chiki"
    ui_files = [
        ROOT / "frontend" / "index.html",
        ROOT / "frontend" / "js" / "dashboard.js",
        ROOT / "frontend" / "js" / "voice.js",
        ROOT / "frontend" / "js" / "materials.js",
        ROOT / "frontend" / "js" / "mesh.js",
    ]
    checked = 0
    for path in ui_files:
        tokens = _OLCHIKI.findall(path.read_text(encoding="utf-8"))
        for tok in tokens:
            assert tok == expected, (
                f"{path.name} shows an Ol Chiki token that is not the "
                f"brief's autonym - fix it by copying from CLAUDE.md, not "
                f"by retyping. token={tok!r}"
            )
            checked += 1
    assert checked >= 5, "expected the autonym in every page of the UI"


def test_olchiki_examples_in_backend_are_in_range():
    """Any Ol Chiki in backend/content sources must be in the real block
    (the regex guarantees it) - this test documents the scan and catches
    files added later that smuggle in other scripts."""
    for path in _repo_text_files():
        text = path.read_text(encoding="utf-8")
        for tok in _OLCHIKI.findall(text):
            assert all("\U00001c50" <= ch <= "\U00001c7f" for ch in tok), (
                f"{path.relative_to(ROOT)}: token outside Ol Chiki block: {tok!r}"
            )
