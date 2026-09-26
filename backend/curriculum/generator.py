"""Bilingual lesson generation.

Design notes, because the "how" matters for honesty:

* Lessons are TEMPLATE-DRIVEN, built around the selected NIPUN/FLN learning
  outcome - not a blind sentence-by-sentence translation of some arbitrary
  text. Templates preserve the pedagogy; only the slots (topic, vocabulary,
  question stems) vary.
* Vocabulary comes from the verified lexicon where we have it. Everything
  else is run through the same lexicon-first, NLLB-second translation chain
  as the voice module, and every machine-generated line carries
  review_warning so a teacher reviews it before class.
* Nothing here calls the network. Ever.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from ..engines.base import ModelUnavailable, Translation
from ..engines.translation import translation_engine
from . import outcomes as outcomes_mod

# Maps a catalog topic to the lexicon category that holds its vocabulary.
TOPIC_CATEGORY = {
    "animals": "animals",
    "colours": "colours",
    "numbers 1-10": "numbers",
    "family": "family",
    "fruits and vegetables": "food",
    "body parts": "body",
    "classroom objects": "classroom",
    "greetings": "greetings",
}


@dataclass
class LessonRequest:
    grade: str = "2"
    subject: str = "Foundational Literacy"
    topic: str = "Animals"
    outcome: str = ""  # free text; auto-picked from the catalog when blank
    target_language: str = "sat"

    def __post_init__(self):
        if self.target_language != "sat":
            # Extensible by design: Ho and Mundari stay selectable in the UI
            # as "Planned / Future Language" and are refused here, honestly.
            raise ModelUnavailable(
                f"Lesson generation is implemented for Santali only; "
                f"'{self.target_language}' is a planned future language."
            )


def _mt(text: str, src: str = "hi", tgt: str = "sat") -> tuple[str, bool]:
    """Translate one line. Returns (santali, was_verified_lexicon)."""
    try:
        t = translation_engine().translate(text, src, tgt)
        verified = "lexicon" in (t.source or "")
        return t.text, verified
    except Exception as err:
        raise ModelUnavailable(f"translation failed for: {text[:40]}... ({err})") from err


def _line(hi: str) -> dict:
    sat, verified = _mt(hi)
    return {"hi": hi, "sat": sat, "verified": verified}


def _category_for(topic: str) -> str | None:
    key = topic.strip().lower()
    return TOPIC_CATEGORY.get(key)


def generate_lesson(req: LessonRequest) -> dict:
    cat = outcomes_mod.catalog()
    if req.grade not in cat.grades():
        raise ModelUnavailable(f"grade '{req.grade}' not in catalog")
    if req.subject not in cat.subjects():
        raise ModelUnavailable(f"subject '{req.subject}' not in catalog")

    # Resolve the learning outcome (auto-pick if the teacher left it blank).
    outcome_text = req.outcome.strip()
    outcome_id = None
    matches = cat.outcomes_for(req.grade, req.subject, req.topic)
    if not outcome_text:
        if not matches:
            raise ModelUnavailable(
                f"no {req.subject} outcome found for grade {req.grade}"
            )
        outcome_text = matches[0]["text"]
        outcome_id = matches[0]["id"]
    else:
        for o in matches:
            if o["text"] == outcome_text:
                outcome_id = o["id"]
                break

    # Vocabulary from the verified lexicon, when we have the category.
    mt = translation_engine()
    category = _category_for(req.topic)
    words: list[dict] = []
    if category:
        for entry in mt.lexicon.words_in(category, limit=8):
            words.append(
                {
                    "hi": entry["hi"],
                    "sat": entry["sat"],
                    "sat_latin": entry.get("sat_latin", ""),
                    "en": entry.get("en", ""),
                    "icon": entry.get("icon", ""),
                    "verified": True,
                }
            )
    vocab_verified = bool(words)

    script_lines: list[dict] = []

    # -- lesson script -----------------------------------------------------
    opening = _line(
        f"नमस्ते बच्चों! आज हम {req.topic} के बारे में सीखेंगे।"
    )
    script_lines.append(opening)
    if words:
        intro = _line(f"पहले हम {req.topic} के नाम सीखेंगे।")
        script_lines.append(intro)
        for w in words[:5]:
            # The lexicon stores verified words, not sentence frames - we
            # frame the Hindi sentence and machine-translate it, so the
            # teacher sees the verified word inside a reviewed line.
            script_lines.append(_line(f"यह {w['hi']} है।"))
    else:
        script_lines.append(_line(f"आज का विषय है: {req.topic}।"))
    script_lines.append(_line("अब मिलकर इसे दोहराते हैं।"))

    # -- activity -------------------------------------------------------------
    if req.subject == "Foundational Numeracy":
        activity_hi = [
            f"कक्षा में {req.topic} से जुड़ी चीज़ें गिनकर बताइए।",
            "हर गिनती को साथ मिलकर बोलिए।",
            "अब अपनी कॉपी में उतने चिह्न बनाइए।",
        ]
    else:
        activity_hi = [
            f"बोर्ड पर {req.topic} के चित्र दिखाए जाएँगे।",
            "हर चित्र का नाम बच्चे मिलकर बोलेंगे।",
            "अंत में कोई एक बच्चा पूरी सूची बोलकर दिखाएगा।",
        ]
    activity = [_line(a) for a in activity_hi]

    # -- assessment -------------------------------------------------------------
    assessment = []
    if words:
        for w in words[:3]:
            q = _line(f"प्रश्न: क्या यह {w['hi']} है?")
            assessment.append({"question": q, "answer_hi": w["hi"], "answer_sat": w["sat"]})
    else:
        assessment.append(
            {"question": _line(f"प्रश्न: आज हमने क्या सीखा?"), "answer_hi": "", "answer_sat": ""}
        )

    lesson = {
        "title_hi": f"पाठ: {req.topic}",
        "title_sat": _mt(f"पाठ: {req.topic}")[0],
        "grade": req.grade,
        "subject": req.subject,
        "topic": req.topic,
        "outcome_id": outcome_id,
        "outcome": _line(f"सीखने का उद्देश्य: {outcome_text}"),
        "target_language": req.target_language,
        "script": script_lines,
        "activity": {"name": _line("कक्षा-क्रियाकलाप"), "steps": activity},
        "assessment": assessment,
        "vocabulary": words,
        "vocabulary_source": "verified lexicon" if vocab_verified else "none (topic not in lexicon yet)",
        "review_warning": (
            "Machine-generated translation. Please review before classroom use."
        ),
    }
    return lesson
