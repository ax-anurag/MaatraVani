"""Verified-classroom-lexicon translation layer.

A small, human-checked Hindi<->Santali dataset for exactly the phrases a
primary classroom actually uses. It sits *in front* of the neural MT engine:
a verified entry always beats a machine translation, because for the demo we
would rather be reliably right on "गाय हमें दूध देती है।" than occasionally
wrong everywhere.

Entries live in content/vocabulary/lexicon.json. Every entry records where it
came from (see PROVENANCE.md); anything the team could not verify is simply
not in this file. No entry is ever machine-translated in secret.
"""

from __future__ import annotations

import json
import re
import threading

from ... import config
from ..base import ModelUnavailable, Translation, TranslationEngine

# Punctuation we ignore when matching (Hindi danda included).
_STRIP = re.compile(r"[\s।!.,;:?\"'()\-–—।]+")

# Ol Chiki is the script Santali is written in; range U+1C50..U+1C7F.
_OLCHIKI = re.compile(r"[᱐-᱿]")


def _normalize(text: str) -> str:
    return _STRIP.sub("", text)


class LexiconEngine(TranslationEngine):
    name = "lexicon"
    pairs = (("hi", "sat"), ("sat", "hi"))

    def __init__(self, path=None):
        self.path = path or config.LEXICON_PATH
        self._lock = threading.Lock()
        self.entries = []
        self._by_hi = {}
        self._by_sat = {}
        self._loaded = False
        self._load()

    def _load(self):
        if not self.path.exists():
            # Not fatal — the app still works through the neural engine,
            # but we report honestly that the lexicon layer is absent.
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.entries = data.get("entries", [])
        self._by_hi = {_normalize(e["hi"]): e for e in self.entries if e.get("hi")}
        self._by_sat = {
            _normalize(e["sat"]): e for e in self.entries if e.get("sat")
        }
        self._loaded = True

    def available(self) -> bool:
        return self._loaded and len(self.entries) > 0

    def size(self) -> int:
        return len(self.entries)

    def words_in(self, category: str, limit: int = 12) -> list[dict]:
        """Word entries for a category — used by the curriculum generator."""
        return [
            e
            for e in self.entries
            if e.get("category") == category and e.get("kind") == "word"
        ][:limit]

    def categories(self) -> list[str]:
        seen = []
        for e in self.entries:
            c = e.get("category")
            if c and c not in seen:
                seen.append(c)
        return seen

    def _hit(self, text: str, src: str, tgt: str) -> Translation | None:
        if src == "hi":
            entry = self._by_hi.get(_normalize(text))
            out = entry.get("sat", "") if entry else None
        else:
            entry = self._by_sat.get(_normalize(text))
            out = entry.get("hi", "") if entry else None
        if not entry or not out:
            return None
        return Translation(
            text=out,
            src=src,
            tgt=tgt,
            script="Ol Chiki" if tgt == "sat" else "Devanagari",
            engine=self.name,
            source="lexicon (verified)",
        )

    def translate(self, text: str, src: str, tgt: str) -> Translation:
        hit = self._hit(text, src, tgt)
        if hit is not None:
            return hit
        # The lexicon is exact-match by design; miss = "not my job".
        raise ModelUnavailable("not in lexicon")


def is_olchiki(text: str) -> bool:
    """True if the string contains Ol Chiki codepoints (U+1C50..U+1C7F)."""
    return bool(_OLCHIKI.search(text))
