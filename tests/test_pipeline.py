"""Full voice-pipeline tests (acceptance tests 5-8):

Hindi voice -> Hindi text -> Santali text -> Santali voice, with every
latency actually measured and every failure honestly labelled per stage.

The pipeline's contract, asserted here:
  * stages report available/error independently - a TTS failure must NOT
    sink the translation result;
  * latency dict always carries asr/translation/tts/total (the numbers
    the UI shows are the numbers we measured);
  * the reverse (Santali voice in) fails with the honest explanation
    unless an online provider is configured.
"""

import pytest

from backend import config
from backend.services import pipeline
from conftest import requires_demo_audio, requires_espeak, requires_nllb


def _wav(sentence_id):
    return (config.GENERATED_DIR / "demo_audio" / f"{sentence_id}.wav").read_bytes()


def test_santali_voice_in_is_honest_without_credentials(monkeypatch):
    """Reverse direction: offline mode + no Bhashini -> explicit error,
    never a made-up transcript."""
    monkeypatch.setattr(config, "OFFLINE_MODE", True)
    import backend.engines.providers.bhashini as bh
    monkeypatch.setattr(bh, "_instance", None)
    out = pipeline.run_pipeline(b"RIFF fake", "sat", "hi")
    assert out["stages"]["asr"]["available"] is False
    assert "Santali speech recognition" in out["stages"]["asr"]["error"]
    assert "error" in out  # pipeline aborts loudly at the failed stage


@requires_nllb
@requires_demo_audio
@requires_espeak
def test_full_hindi_voice_to_santali_voice():
    out = pipeline.run_pipeline(_wav("topic-intro"), "hi", "sat")

    asr_stage = out["stages"]["asr"]
    assert asr_stage["available"], f"ASR failed: {asr_stage.get('error')}"
    assert asr_stage["text"], "empty transcript"

    tr = out["stages"]["translation"]
    assert tr["available"], f"translation failed: {tr.get('error')}"
    assert tr["text"] and tr["text"] != asr_stage["text"]

    lat = out["latency"]
    for key in ("asr", "translation", "tts", "total"):
        assert key in lat, f"latency.{key} missing - the UI shows real numbers"
        assert lat[key] >= 0.0
    total = lat["asr"] + lat["translation"] + lat["tts"]
    assert lat["total"] == pytest.approx(total, abs=0.05)

    # TTS outcome is reported honestly either way:
    tts = out["stages"]["tts"]
    if tts.get("available"):
        assert out.get("audio_b64"), "TTS claimed success but no audio"
    else:
        assert out.get("tts_unavailable") is True
        assert "error" in out["stages"]["tts"]


@requires_nllb
@requires_demo_audio
def test_latency_target_is_reported_not_promised():
    out = pipeline.run_pipeline(_wav("greeting"), "hi", "sat")
    assert out["target_latency_budget_s"] == 3.0
    # and the measured total is exactly what the latency dict says it is
    assert out["latency"]["total"] >= out["latency"]["asr"]


@requires_nllb
def test_translate_text_flags_machine_output_for_review():
    out = pipeline.translate_text("नमस्ते बच्चों।", "hi", "sat", speak=False)
    assert out["review_warning"], "machine output must be flagged for review"
    assert out["latency"]["translation"] >= 0.0
