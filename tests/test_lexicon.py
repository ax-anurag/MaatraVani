"""Lexicon layer tests - the verified-first translation tier.

Mechanics only: normalization, exact matching both directions, category
lookup, script checks, honest miss. The Ol Chiki literals are NOT retyped
here; the tests read them out of the temp fixture, so the suite can never
drift from (or invent) the script content it checks.
"""

import json

import pytest

from backend.engines.base import ModelUnavailable
from backend.engines.translation.lexicon import LexiconEngine, _normalize, is_olchiki


def _entry(temp_lexicon):
    return json.loads(temp_lexicon.read_text(encoding="utf-8"))["entries"][0]


def test_normalize_ignores_punctuation_and_danda():
    assert _normalize("नमस्ते बच्चों।") == _normalize("नमस्तेबच्चों")
    assert _normalize("  hello , world ! ") == "helloworld"


def test_exact_hit_hi_to_sat(temp_lexicon):
    eng = LexiconEngine(path=temp_lexicon)
    entry = _entry(temp_lexicon)
    t = eng.translate(entry["hi"], "hi", "sat")
    assert t.text == entry["sat"]
    assert t.script == "Ol Chiki"
    assert "lexicon" in t.source


def test_exact_hit_sat_to_hi(temp_lexicon):
    eng = LexiconEngine(path=temp_lexicon)
    entry = _entry(temp_lexicon)
    t = eng.translate(entry["sat"], "sat", "hi")
    assert t.text == entry["hi"]
    assert t.script == "Devanagari"
    assert "lexicon" in t.source


def test_punctuation_insensitive_match(temp_lexicon):
    eng = LexiconEngine(path=temp_lexicon)
    entry = _entry(temp_lexicon)
    t = eng.translate(entry["hi"] + "।", "hi", "sat")
    assert t.text == entry["sat"]


def test_miss_is_honest(temp_lexicon):
    eng = LexiconEngine(path=temp_lexicon)
    with pytest.raises(ModelUnavailable):
        eng.translate("यह वाक्य शब्दकोश में नहीं है", "hi", "sat")


def test_words_in_category(temp_lexicon):
    eng = LexiconEngine(path=temp_lexicon)
    words = eng.words_in("classroom")
    assert len(words) == 1
    assert eng.words_in("animals") == []


def test_is_olchiki(temp_lexicon):
    entry = _entry(temp_lexicon)
    assert is_olchiki(entry["sat"])
    assert not is_olchiki(entry["hi"])
    assert not is_olchiki("plain ascii")


def test_real_lexicon_is_valid_and_sourced():
    """The shipped dataset must load, and every entry must carry a source
    (the 'verified' claim lives or dies with that field)."""
    from backend import config
    data = json.loads(config.LEXICON_PATH.read_text(encoding="utf-8"))
    for e in data.get("entries", []):
        assert e.get("hi") and e.get("sat"), "entry missing a side"
        assert e.get("source"), f"entry {e.get('id')} has no source"
        assert is_olchiki(e["sat"]), f"entry {e.get('id')} sat value is not Ol Chiki"
