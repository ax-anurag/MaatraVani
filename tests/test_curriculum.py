"""Curriculum tests: lessons, worksheets, flashcards (acceptance 9-13).

FLN/NIPUN outcome association, template-driven bilingual generation,
locally-rendered PDFs with real text shaping for both scripts.
"""

import json

import pytest

from backend import config
from backend.curriculum import flashcards, generator, outcomes, worksheets
from backend.engines.base import ModelUnavailable
from conftest import requires_fonts, requires_nllb


def _vocab_of(lesson):
    return lesson["vocabulary"] or []


def test_catalog_loads():
    cat = outcomes.catalog()
    assert cat.grades() == ["1", "2", "3"]
    assert "Foundational Literacy" in cat.subjects()
    data_outcomes = [o for o in cat.data["outcomes"]]
    assert len(data_outcomes) >= 12, "representative FLN subset expected"
    for o in data_outcomes:
        assert o["id"] and o["grade"] and o["subject"] and o["text"]
        assert isinstance(o["topics"], list)


def test_outcomes_filter_by_grade_subject_topic():
    cat = outcomes.catalog()
    matches = cat.outcomes_for("2", "Foundational Literacy", "Animals")
    assert matches, "grade 2 literacy Animals should have outcomes"
    for o in matches:
        assert o["grade"] == "2"
        assert o["subject"] == "Foundational Literacy"
        assert "Animals" in o["topics"]


def test_planned_languages_refused_not_faked():
    with pytest.raises(ModelUnavailable, match="planned future language"):
        generator.LessonRequest(grade="2", target_language="hoc")


def test_unknown_grade_refused():
    req = generator.LessonRequest(grade="12")
    with pytest.raises(ModelUnavailable):
        generator.generate_lesson(req)


@requires_nllb
class TestLessonGeneration:
    def test_grade2_animals_lesson(self):
        req = generator.LessonRequest(grade="2", topic="Animals")
        lesson = generator.generate_lesson(req)
        assert lesson["grade"] == "2"
        assert lesson["topic"] == "Animals"
        # outcome must be associated (FLN requirement)
        assert lesson["outcome_id"], "NIPUN outcome must be linked"
        assert lesson["outcome"]["hi"] and lesson["outcome"]["sat"]
        # bilingual script with per-line provenance
        for line in lesson["script"]:
            assert line["hi"] and line["sat"] and isinstance(line["verified"], bool)
        assert lesson["activity"]["steps"], "activity steps missing"
        assert lesson["assessment"], "assessment questions missing"
        # review warning always travels with the lesson
        assert "review" in lesson["review_warning"].lower()
        # vocabulary from the verified lexicon, when the category exists
        for w in lesson["vocabulary"]:
            assert w["verified"] is True
            assert w["hi"] and w["sat"]

    def test_explicit_outcome_is_kept(self):
        cat = outcomes.catalog()
        target = cat.outcomes_for("2", "Foundational Literacy", "Animals")[0]
        req = generator.LessonRequest(grade="2", topic="Animals",
                                      outcome=target["text"])
        lesson = generator.generate_lesson(req)
        assert lesson["outcome_id"] == target["id"]

    def test_numeracy_lesson_also_works(self):
        req = generator.LessonRequest(
            grade="1", subject="Foundational Numeracy", topic="Numbers 1-10")
        lesson = generator.generate_lesson(req)
        assert lesson["subject"] == "Foundational Numeracy"
        assert lesson["outcome_id"].startswith("N")


# --- worksheets -----------------------------------------------------------

def test_worksheet_refuses_without_fonts(monkeypatch):
    monkeypatch.setattr(worksheets, "DEVA_FONT", config.ROOT / "nope.ttf")
    with pytest.raises(ModelUnavailable, match="fonts"):
        worksheets.build_worksheet(
            topic="Animals", grade="2", outcome="x",
            vocabulary=[{"hi": "गाय", "sat": "x", "icon": ""}])


def test_worksheet_refuses_empty_vocabulary():
    with pytest.raises(ModelUnavailable):
        worksheets.build_worksheet(
            topic="Animals", grade="2", outcome="x", vocabulary=[])


@requires_fonts
def test_worksheet_pdf_renders_locally(temp_lexicon):
    entry = json.loads(temp_lexicon.read_text(encoding="utf-8"))["entries"][0]
    vocab = [{**entry, "verified": True}] * 3  # any {hi, sat} dicts will do
    instruction = {"hi": "गतिविधि: सही जोड़े मिलाइए।", "sat": entry["sat"]}
    pdf = worksheets.build_worksheet(
        topic="Animals", grade="2", outcome="identify and name animals",
        vocabulary=vocab, instruction=instruction)
    assert pdf[:5] == b"%PDF-", "must be a real PDF"
    assert len(pdf) > 4000, "suspiciously tiny worksheet"


# --- flashcards -----------------------------------------------------------

# Mechanism-test vocabulary. The Santali side is the brief's autonym read
# at runtime (conftest.brief_autonym) - never re-typed glyphs, which is how
# corrupted script characters sneak in. The values are opaque to every
# assertion below; only their presence matters.
from conftest import brief_autonym  # noqa: E402

CARD_WORDS = [
    {"hi": f"शब्द{i}", "sat": brief_autonym(), "sat_latin": f"sat{i}", "icon": "🐄"}
    for i in range(10)
]


def test_flashcard_counts_are_exactly_1_4_8():
    assert flashcards.CARD_COUNTS == (1, 4, 8)
    assert len(flashcards.build_cards(CARD_WORDS, 1)) == 1
    assert len(flashcards.build_cards(CARD_WORDS, 4)) == 4
    assert len(flashcards.build_cards(CARD_WORDS, 8)) == 8
    with pytest.raises(ValueError):
        flashcards.build_cards(CARD_WORDS, 7)
    with pytest.raises(ModelUnavailable):
        flashcards.build_cards([], 4)


def test_flashcards_are_deterministic():
    a = flashcards.build_cards(CARD_WORDS, 4)
    b = flashcards.build_cards(CARD_WORDS, 4)
    assert a == b, "same request must produce the same cards (seeded rng)"


def test_flashcard_svg_contains_both_scripts():
    cards = flashcards.build_cards(CARD_WORDS, 4)
    svg = flashcards.render_svg(cards[0])
    assert svg.startswith("<svg") and "viewBox" in svg
    assert cards[0]["sat"] in svg, "Ol Chiki word must be on the card"
    assert cards[0]["hi"] in svg
    assert cards[0]["icon"] in svg, "locally-available glyph illustration"


@requires_fonts
def test_flashcard_pdf_renders_locally():
    cards = flashcards.build_cards(CARD_WORDS, 4)
    pdf = flashcards.render_pdf(cards, topic="Animals")
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 3000
