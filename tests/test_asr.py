"""ASR tests (acceptance test 3: Hindi audio -> Hindi text).

Two honest facts shape this file:
  * there is NO offline Santali ASR, and the selection layer must say so
    instead of pretending (test_santali_asr_is_never_pretended);
  * the demo WAVs are espeak-synthesized (no mic in WSL2), so recognition
    quality on them is a lower bound - the test asserts non-empty text,
    not accuracy, and the README documents exactly this caveat.
"""

import json

import pytest

from backend import config
from backend.engines import asr
from backend.engines.base import ModelUnavailable
from conftest import requires_demo_audio, requires_espeak


def test_santali_asr_is_never_pretended():
    with pytest.raises(ModelUnavailable, match="Santali|'sat'"):
        asr.best_for("sat")


def test_status_reports_why_engines_are_missing():
    """available() and unavailable_reason() must agree, whatever the state."""
    for item in asr.status():
        assert item["engine"]
        assert isinstance(item["languages"], list)
        assert item["available"] == (item["reason"] is None)


@requires_demo_audio
@requires_espeak
class TestHindiASR:
    def _wav(self, sentence_id):
        path = config.GENERATED_DIR / "demo_audio" / f"{sentence_id}.wav"
        return path.read_bytes()

    def test_flagship_sentence_recognized_nonempty(self):
        engine = asr.best_for("hi")
        t = engine.transcribe(self._wav("topic-intro"), "hi")
        assert t.text, f"got empty transcript from {engine.name}"
        assert t.engine == engine.name
        assert t.latency_s >= 0.0

    def test_all_demo_sentences_produce_transcripts(self):
        engine = asr.best_for("hi")
        data = json.loads(config.DEMO_SENTENCES_PATH.read_text(encoding="utf-8"))
        empty = []
        for s in data["sentences"]:
            path = config.GENERATED_DIR / "demo_audio" / f"{s['id']}.wav"
            if not path.exists():
                continue
            t = engine.transcribe(path.read_bytes(), "hi")
            if not t.text.strip():
                empty.append(s["id"])
        # Synthetic speech is hard; we accept one miss, not a collapse.
        assert len(empty) <= 1, f"too many empty transcripts: {empty}"
