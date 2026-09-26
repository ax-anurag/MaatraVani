"""Offline tests (acceptance tests 6-7, and CLAUDE.md's OFFLINE TEST block).

The premise: unplug the network. Implementation: socket.connect and
socket.connect_ex are monkeypatched to raise, so ANY outbound attempt would
crash the test immediately - if the suite passes, nothing even tried.
"""

import socket

import pytest

import backend.engines.providers.bhashini as bhashini
from backend import config
from backend.services import pipeline
from conftest import requires_espeak, requires_nllb


@pytest.fixture(autouse=True)
def network_dead(monkeypatch):
    """Kill every outbound socket in this process - the whole point."""
    def _blocked(*args, **kwargs):
        raise RuntimeError("NETWORK ATTEMPTED in a test that must be offline")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    # Belt and braces: the optional cloud provider is force-disabled, so
    # even credentials in the environment cannot make it reachable.
    monkeypatch.setattr(config, "OFFLINE_MODE", True)
    monkeypatch.setattr(bhashini, "_instance", None)


def test_mesh_never_needed_the_network(tmp_path):
    from backend.mesh import manager as manager_mod
    m = manager_mod.MeshManager(log_path=tmp_path / "log.jsonl")
    result = m.send(sender_id="teacher", type_="ANNOUNCEMENT",
                    language="hi", payload={"text": "कल गणित की कॉपी साथ लाईये।"})
    delivered = [e for e in result["events"] if e["event"] == "delivered"]
    assert any(e["to_node"] == "student-b" and e["hop_count"] == 2 for e in delivered)


def test_bhashini_stays_dark_in_offline_mode():
    assert not bhashini.provider().available(), \
        "offline mode must disable the cloud fallback completely"


def test_lexicon_translation_is_purely_local(temp_lexicon):
    from backend.engines.translation.lexicon import LexiconEngine
    eng = LexiconEngine(path=temp_lexicon)
    entry = eng.entries[0]
    t = eng.translate(entry["hi"], "hi", "sat")
    assert t.text == entry["sat"]


@requires_nllb
def test_neural_translation_is_purely_local():
    out = pipeline.translate_text("नमस्ते बच्चों।", "hi", "sat", speak=False)
    assert out["text"], "NLLB must answer with sockets dead"


@requires_nllb
def test_lesson_generation_is_purely_local():
    from backend.curriculum import generator
    lesson = generator.generate_lesson(
        generator.LessonRequest(grade="2", topic="Animals"))
    assert lesson["script"], "lesson generation must work offline"
    assert lesson["outcome_id"]


@requires_espeak
def test_santali_tts_is_purely_local(autonym):
    from backend.engines.tts.espeak import EspeakEngine
    eng = EspeakEngine()
    if not eng.language_available("sat"):
        pytest.skip("espeak-ng on this machine has no 'sat' voice")
    wav = eng.synthesize(autonym, "sat")
    assert wav.wav_bytes[:4] == b"RIFF"


@requires_nllb
@requires_espeak
def test_full_text_pipeline_with_voice_is_purely_local():
    out = pipeline.translate_text(
        "आज हम जानवरों के नाम सीखेंगे।", "hi", "sat", speak=True)
    assert out["text"]
    if not out.get("tts_unavailable"):
        assert out["audio_b64"], "TTS ran but produced no audio"
