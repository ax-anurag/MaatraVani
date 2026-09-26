"""Ol Chiki -> Devanagari transliteration for Santali speech output.

There is no offline Santali TTS voice anywhere today, and upstream
espeak-ng ships none either (checked against its dictsource/ on master,
Sept 2026). So this is how Santali speech output actually works: the
text is transliterated letter-by-letter into Devanagari - a script
espeak-ng's Hindi voice already reads aloud - and spoken through that
voice, labelled as transliteration everywhere it appears.

Ol Chiki is phonemic (30 letters, no case, no ligature rules beyond a few
extension marks), so the mapping is honest and deterministic: what you
hear is the actual Santali text, with Hindi phonology, clearly labelled
"transliteration" everywhere it appears. A native-quality Santali voice
remains future work (swap point: TTSEngine).

The letter values follow the public Ol Chiki references (see PROVENANCE.md).
"""

from __future__ import annotations

# Independent Devanagari vowels. Ol Chiki vowels are full letters, so the
# same char must sometimes surface as a matra (k + AA -> का) and sometimes
# independent (AA -> आ); handled by olchiki_to_devanagari() below.
_INDEPENDENT = {
    "ᱚ": "अ",   # /ɔ/
    "ᱟ": "आ",
    "ᱤ": "इ",
    "ᱩ": "उ",
    "ᱮ": "ए",
    "ᱳ": "ओ",
    "ᱶ": "ओ",   # rare "ov"; closest single vowel
}

# The matra (post-consonant) form of the same vowels. अ has no matra here:
# a consonant letter already carries the inherent 'a'.
_MATRA = {
    "ᱚ": "ा",   # /ɔ/ lengthened in post-consonant position
    "ᱟ": "ा",
    "ᱤ": "ि",
    "ᱩ": "ु",
    "ᱮ": "े",
    "ᱳ": "ो",
    "ᱶ": "ो",
}

# Consonants: one Ol Chiki letter, one Devanagari. The retroflex set
# (ᱴ ᱰ ᱬ ᱲ) maps to the Devanagari retroflexes; ᱲ goes to precomposed ड़.
_CONSONANTS = {
    "ᱠ": "क", "ᱜ": "ग", "ᱝ": "ङ",
    "ᱪ": "च", "ᱡ": "ज", "ᱧ": "ज",
    "ᱴ": "ट", "ᱰ": "ड", "ᱬ": "ण",
    "ᱛ": "त", "ᱫ": "द", "ᱱ": "न",
    "ᱯ": "प", "ᱵ": "ब", "ᱢ": "म",
    "ᱭ": "य", "ᱞ": "ल", "ᱨ": "र", "ᱣ": "व",
    "ᱥ": "स", "ᱦ": "ह", "ᱷ": "ह",  # ᱷ is the aspiration mark
    "ᱲ": "ड़",
}

# Extension marks. Nasalisation becomes anusvara; the prolongation marks
# lengthen the vowel. The remaining marks (ᱼ ᱽ and friends) have no good
# spoken equivalent - dropping them is the right minimal-voice behaviour.
_MARKS = {
    "ᱸ": "ं",
    "ᱹ": "ा",
    "ᱺ": "ा",
}

# Ol Chiki digits ᱐..᱙ (U+1C50..U+1C59) read as ASCII digits; espeak-ng's
# Hindi voice reads those with Hindi number words.

_CONSONANT_SET = frozenset(_CONSONANTS)


def olchiki_to_devanagari(text: str) -> str:
    """Transliterate Ol Chiki text into Devanagari for the Hindi voice.

    A vowel letter takes its matra form after a consonant and its
    independent form everywhere else (word-initially, after a vowel,
    after a space). Anything outside the Ol Chiki block passes through
    unchanged so punctuation and spaces survive.
    """
    out: list[str] = []
    prev_consonant = False
    for ch in text:
        if ch in _CONSONANTS:
            out.append(_CONSONANTS[ch])
            prev_consonant = True
        elif ch in _MATRA:
            if prev_consonant:
                out.append(_MATRA[ch])
            else:
                out.append(_INDEPENDENT[ch])
            prev_consonant = False
        elif ch in _MARKS:
            out.append(_MARKS[ch])
            prev_consonant = False
        elif "᱐" <= ch <= "᱙":
            out.append(chr(ord("0") + ord(ch) - ord("᱐")))
            prev_consonant = False
        else:
            # Non-Ol-Chiki (spaces, danda, punctuation, any Latin that
            # slipped in) - keep it, reset the matra context.
            out.append(ch)
            prev_consonant = False
    return "".join(out)
