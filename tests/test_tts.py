"""Santali TTS tests (acceptance test 4 on the CLAUDE.md list).

No offline Santali TTS exists anywhere - upstream espeak-ng has no `sat`
voice - so Santali audio comes from the labelled transliteration path
(backend/engines/tts/sat_translit.py): Ol Chiki mapped to Devanagari,
read by the Hindi voice. The mapping itself is pure logic and tested
without espeak-ng; synthesis runs whenever espeak-ng is installed. If the
binary is missing, those skip and the app's own error message becomes the
tested behaviour (test_missing_binary_says_so).

The synthesized text is the autonym from the project brief via the
`autonym` fixture - no hand-typed Ol Chiki sentences in this file. Single
letters inside the transliteration unit tests are the map under test.
"""

import pytest

from backend.engines.base import ModelUnavailable
from backend.engines.tts.espeak import EspeakEngine
from backend.engines.tts.sat_translit import olchiki_to_devanagari
from conftest import requires_espeak


def test_missing_binary_says_so(monkeypatch):
    """No espeak-ng -> the exact honest error, never unrelated audio."""
    import backend.engines.tts.espeak as mod
    monkeypatch.setattr(mod.shutil, "which", lambda _: None)
    eng = mod.EspeakEngine()
    assert not eng.available()
    with pytest.raises(ModelUnavailable, match="espeak-ng"):
        eng.synthesize("anything", "sat")


def test_unknown_language_refused():
    with pytest.raises(ModelUnavailable):
        EspeakEngine().synthesize("hello", "hoc")


def test_empty_text_refused():
    with pytest.raises(ModelUnavailable):
        EspeakEngine().synthesize("   ", "sat")


class TestTransliteration:
    """Pure logic - runs on any machine, espeak or not."""

    def test_autonym_letterwise(self, autonym):
        # s + AA -> सा, n, t, AA -> सानता, RRA -> ड़, I -> ि
        assert olchiki_to_devanagari(autonym) == "सानताड़ि"

    def test_independent_vowel_at_word_start(self):
        assert olchiki_to_devanagari("ᱟ") == "आ"

    def test_vowel_after_consonant_takes_matra(self):
        assert olchiki_to_devanagari("ᱠᱟ") == "का"

    def test_vowel_after_vowel_stays_independent(self):
        assert olchiki_to_devanagari("ᱟᱠ") == "आक"

    def test_space_resets_matra_context(self):
        assert olchiki_to_devanagari("ᱠ ᱟ") == "क आ"

    def test_nasalisation_becomes_anusvara(self):
        assert olchiki_to_devanagari("ᱟᱸ") == "आं"

    def test_digits_pass_through_as_ascii(self):
        assert olchiki_to_devanagari("᱑᱒") == "12"

    def test_non_olchiki_passes_through(self):
        assert olchiki_to_devanagari("a ᱠ b") == "a क b"


@requires_espeak
class TestEspeakSynthesis:
    def test_santali_speaks(self, autonym):
        eng = EspeakEngine()
        wav = eng.synthesize(autonym, "sat")
        assert wav.wav_bytes[:4] == b"RIFF", "output must be a WAV"
        assert len(wav.wav_bytes) > 200, "silent/empty audio is refused"
        # a genuine sat voice wins if installed; otherwise the honest label
        assert wav.voice == "sat" or "transliteration" in wav.voice

    def test_hindi_voice_works(self):
        eng = EspeakEngine()
        wav = eng.synthesize("नमस्ते बच्चों।", "hi")
        assert wav.wav_bytes[:4] == b"RIFF"
        assert len(wav.wav_bytes) > 200

    def test_latency_is_measured(self):
        eng = EspeakEngine()
        wav = eng.synthesize("नमस्ते", "hi")
        assert wav.latency_s >= 0.0
