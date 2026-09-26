"""Translation tests - both directions, lexicon-first, honest warnings.

Requires the NLLB model (skips with the exact reason otherwise). These are
acceptance tests 1 and 2 on CLAUDE.md's list: Hindi text -> Santali text,
Santali text -> Hindi text, locally.
"""

import json

import pytest

from conftest import requires_nllb
from backend import config
from backend.engines.base import ModelUnavailable
from backend.engines.translation.composite import ClassroomTranslationEngine
from backend.engines.translation.lexicon import is_olchiki


def _demo_sentences():
    data = json.loads(config.DEMO_SENTENCES_PATH.read_text(encoding="utf-8"))
    # the mesh-category sentence is a relay payload, not a translation
    # utterance - it has no verified Santali and the mesh never translates
    return [s["hi"] for s in data["sentences"] if s["category"] != "mesh"]


def test_engine_reports_what_it_has():
    eng = ClassroomTranslationEngine()
    st = eng.status()
    assert st["lexicon_entries"] >= 0
    assert isinstance(st["nllb_available"], bool)


def test_lexicon_takes_priority_over_nllb(temp_lexicon, monkeypatch):
    """A verified lexicon hit must win even when NLLB would answer too."""
    eng = ClassroomTranslationEngine()
    monkeypatch.setattr(eng, "lexicon", type(eng.lexicon)(path=temp_lexicon))
    entry = json.loads(temp_lexicon.read_text(encoding="utf-8"))["entries"][0]
    t = eng.translate(entry["hi"], "hi", "sat")
    assert "lexicon" in t.source
    assert t.text == entry["sat"]


@requires_nllb
class TestHindiToSantali:
    def test_every_demo_sentence_translates(self):
        eng = ClassroomTranslationEngine()
        for hi in _demo_sentences():
            t = eng.translate(hi, "hi", "sat")
            assert t.text and t.text != hi, f"empty/echo translation for: {hi}"
            assert is_olchiki(t.text), \
                f"Santali output must be in Ol Chiki, got: {t.text!r}"

    def test_pipeline_flag_set_has_latency(self):
        from backend.services import pipeline
        out = pipeline.translate_text("नमस्ते बच्चों।", "hi", "sat")
        assert out["latency"]["translation"] >= 0.0
        assert out["review_warning"] is not None, \
            "machine output must carry the teacher-review warning"


@requires_nllb
class TestSantaliToHindi:
    def test_reverse_direction(self):
        eng = ClassroomTranslationEngine()
        fwd = eng.translate("नमस्ते बच्चों।", "hi", "sat")
        back = eng.translate(fwd.text, "sat", "hi")
        assert back.text
        assert any("ा" in c or "ि" in c or "े" in c for c in back.text), \
            "Hindi output should contain Devanagari characters"
        assert back.script == "Devanagari"


def test_planned_languages_are_refused_not_faked():
    """Ho and Mundari must fail loudly, never produce a 'best effort' fake."""
    eng = ClassroomTranslationEngine()
    with pytest.raises((ModelUnavailable, Exception)):
        eng.translate("नमस्ते", "hi", "hoc")
