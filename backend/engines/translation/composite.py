"""The translation engine the rest of the app actually talks to.

Order of precedence, per the language-quality policy in the project brief:

    1. verified lexicon (human-checked classroom phrases)
    2. NLLB neural translation (local, offline)
    3. nothing — we never invent a translation.

Every result carries its provenance ("lexicon (verified)" vs "nllb"), and the
UI shows the review warning for anything machine-generated.
"""

from __future__ import annotations

import re
import time

from ..base import ModelUnavailable, Translation, TranslationEngine
from . import lexicon as lexicon_mod
from . import nllb as nllb_mod
from .lexicon import is_olchiki

# Devanagari word runs (U+0980 block is Bengali; Hindi lives in 0900-097F).
_DEVA_WORD = re.compile(r"[ऀ-ॿ]+")

# Hindi inflection endings tried longest-first when a word misses the
# lexicon: "जानवरों" -> "जानवर", "सीखेंगे" -> "सीख", and so on. Crude on
# purpose - it only ever feeds the word gloss below, which is labelled
# partial and carries the review warning.
_HI_SUFFIXES = ("ों", "ेंगे", "ोंगे", "ेगे", "ोगे", "े�ं", "ें", "ीं", "ाए", "ी", "े", "ो", "ा", "ि")

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


class ClassroomTranslationEngine(TranslationEngine):
    name = "lexicon+nllb"
    pairs = (("hi", "sat"), ("sat", "hi"))

    def __init__(self, lexicon=None, nllb=None):
        self.lexicon = lexicon or lexicon_mod.LexiconEngine()
        self.nllb = nllb or nllb_mod.get_engine()

    def supports(self, src: str, tgt: str) -> bool:
        return (src, tgt) in self.pairs

    def available(self) -> bool:
        return self.lexicon.available() or self.nllb.available()

    def translate(self, text: str, src: str, tgt: str) -> Translation:
        if (src, tgt) not in self.pairs:
            raise ModelUnavailable(f"unsupported pair {src}->{tgt}")
        try:
            return self.lexicon.translate(text, src, tgt)
        except ModelUnavailable:
            pass

        # Neural attempt. If the model is missing we still try the word
        # gloss below - the demo keeps working without the 604 MB download.
        nllb_error: Exception | None = None
        try:
            neural = self.nllb.translate(text, src, tgt)
        except ModelUnavailable as err:
            nllb_error = err
        else:
            in_script = is_olchiki(neural.text) if tgt == "sat" else bool(_DEVANAGARI.search(neural.text))
            if in_script:
                return neural

        # The distilled NLLB build does not actually produce Ol Chiki for
        # Santali on this hardware (see PROVENANCE.md), so a neural answer in
        # the wrong script is no answer at all. Fall back to a word-by-word
        # gloss from the *verified* lexicon: known words come out in real
        # Santali, unknown words stay in Hindi, visibly. Labelled partial and
        # carrying the review warning - never passed off as a translation.
        glossed, hits = self._word_gloss(text, src, tgt)
        if hits:
            return Translation(
                text=glossed,
                src=src,
                tgt=tgt,
                script="Ol Chiki" if tgt == "sat" else "Devanagari",
                engine=self.name,
                source="word gloss (partial, verified words only)",
            )
        if nllb_error is not None:
            raise nllb_error
        return neural  # unscripted neural output, honestly labelled upstream

    def _word_gloss(self, text: str, src: str, tgt: str) -> tuple[str, int]:
        """Swap in every lexicon word we can verify; count the swaps."""
        if src == "hi":
            table, out_key = self.lexicon._by_hi, "sat"
        else:
            table, out_key = self.lexicon._by_sat, "hi"

        def lookup(word: str):
            # the Devanagari range swallows the danda (U+0964), so a match
            # can arrive as "बच्चों।" - strip sentence punctuation first,
            # or no suffix rule below ever fires
            word = word.rstrip("।॥")
            if not word:
                return None
            if src == "hi":
                # try the bare word, then progressively de-inflected forms
                candidates = [word]
                for suffix in _HI_SUFFIXES:
                    if word.endswith(suffix) and len(word) > len(suffix) + 1:
                        candidates.append(word[: -len(suffix)])
                for cand in candidates:
                    entry = table.get(lexicon_mod._normalize(cand))
                    if entry:
                        return entry[out_key]
                    # "बच्चों" de-inflects to "बच्च" but the entry is "बच्चे"
                    entry = table.get(lexicon_mod._normalize(cand + "े"))
                    if entry:
                        return entry[out_key]
                return None
            entry = table.get(lexicon_mod._normalize(word))
            return entry[out_key] if entry else None

        hits = 0

        def replace(match: re.Match) -> str:
            nonlocal hits
            word = match.group(0)
            sat = lookup(word)
            if sat:
                hits += 1
                return sat
            return word

        pattern = _DEVA_WORD if src == "hi" else re.compile(r"[᱐-᱿]+")
        return pattern.sub(replace, text), hits

    def status(self) -> dict:
        return {
            "lexicon_entries": self.lexicon.size(),
            "lexicon_available": self.lexicon.available(),
            "nllb_available": self.nllb.available(),
            "nllb_model_dir": str(self.nllb.model_dir),
        }


_instance: ClassroomTranslationEngine | None = None


def get_engine() -> ClassroomTranslationEngine:
    global _instance
    if _instance is None:
        _instance = ClassroomTranslationEngine()
    return _instance
