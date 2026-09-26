"""Voice-to-voice pipeline: ASR -> translation -> TTS, with honest meters.

Every stage reports its own measured latency. The number the UI displays is
the number we actually observed — if the pipeline takes 6 seconds, the
screen says 6 seconds and DEMO.md explains why. No stage ever invents output:
if ASR or TTS cannot run, the response carries an explicit error for that
stage and everything else still runs.
"""

from __future__ import annotations

import base64
import time

from ..engines import asr as asr_mod
from ..engines import bhashini
from ..engines import tts as tts_mod
from ..engines.base import ModelUnavailable
from ..engines.translation import translation_engine, is_olchiki

REVIEW_WARNING = (
    "Machine-generated translation. Please review before classroom use."
)


def _fail(stage: str, err: Exception) -> dict:
    return {"stage": stage, "error": str(err), "available": False}


def run_pipeline(wav_bytes: bytes, src: str = "hi", tgt: str = "sat") -> dict:
    """Full voice pipeline. Returns a dict the voice API serialises."""
    out: dict = {
        "src": src,
        "tgt": tgt,
        "stages": {},
        "latency": {},
        "review_warning": None,
    }

    # ---- ASR -----------------------------------------------------------
    t0 = time.perf_counter()
    try:
        if src == "sat":
            # No offline Santali ASR exists. Bhashini (online, if the user
            # configured it) is the only honest option; otherwise we say so.
            engine = bhashini.provider()
            if not engine.available():
                raise ModelUnavailable(
                    "Santali speech recognition is not available offline. "
                    "No open Santali ASR model exists today; configure the "
                    "Bhashini fallback (see .env.example) for the reverse "
                    "voice direction."
                )
            transcript = engine.transcribe(wav_bytes, src)
        else:
            transcript = asr_mod.best_for(src).transcribe(wav_bytes, src)
        out["stages"]["asr"] = {
            "engine": transcript.engine,
            "text": transcript.text,
            "available": True,
        }
    except Exception as err:  # stage failure reported honestly, never faked
        out["stages"]["asr"] = _fail("asr", err)
        out["latency"]["asr"] = round(time.perf_counter() - t0, 3)
        out["error"] = f"ASR failed: {err}"
        return out
    asr_ms = time.perf_counter() - t0

    # ---- Translation -----------------------------------------------------
    t1 = time.perf_counter()
    try:
        translation = translation_engine().translate(transcript.text, src, tgt)
        out["stages"]["translation"] = {
            "engine": translation.engine,
            "source": translation.source,
            "text": translation.text,
            "script": translation.script,
            "available": True,
        }
        if translation.source and "lexicon" not in translation.source:
            out["review_warning"] = REVIEW_WARNING
    except Exception as err:
        out["stages"]["translation"] = _fail("translation", err)
        out["latency"]["asr"] = round(asr_ms, 3)
        out["latency"]["translation"] = round(time.perf_counter() - t1, 3)
        out["error"] = f"translation failed: {err}"
        return out
    mt_ms = time.perf_counter() - t1

    # ---- TTS --------------------------------------------------------------
    t2 = time.perf_counter()
    try:
        speech = tts_mod.best_for(tgt).synthesize(translation.text, tgt)
        out["stages"]["tts"] = {
            "engine": speech.engine,
            "voice": speech.voice,
            "sample_rate": speech.sample_rate,
            "available": True,
        }
        if "transliteration" in speech.voice:
            out["stages"]["tts"]["note"] = (
                "Santali audio is read via transliteration through the Hindi "
                "voice - no offline Santali TTS exists (labelled, not hidden)."
            )
        out["audio_b64"] = base64.b64encode(speech.wav_bytes).decode()
    except Exception as err:
        # Voice-out is genuinely optional: the Ol Chiki text result stands.
        out["stages"]["tts"] = _fail("tts", err)
        out["tts_unavailable"] = True
    tts_ms = time.perf_counter() - t2

    out["latency"] = {
        "asr": round(asr_ms, 3),
        "translation": round(mt_ms, 3),
        "tts": round(tts_ms, 3),
        "total": round(asr_ms + mt_ms + tts_ms, 3),
    }
    out["target_latency_budget_s"] = 3.0
    if tgt == "sat" and not is_olchiki(translation.text):
        out["script_note"] = (
            "Translation engine returned Santali in a non-Ol-Chiki script; "
            "shown as produced."
        )
    return out


def translate_text(text: str, src: str, tgt: str, speak: bool = False) -> dict:
    """Text-in path (typing + curriculum generation + tests)."""
    t0 = time.perf_counter()
    translation = translation_engine().translate(text, src, tgt)
    mt_ms = time.perf_counter() - t0
    out = {
        "src": src,
        "tgt": tgt,
        "text": translation.text,
        "script": translation.script,
        "engine": translation.engine,
        "source": translation.source,
        "latency": {"translation": round(mt_ms, 3)},
        "review_warning": None if translation.source == "lexicon (verified)" else REVIEW_WARNING,
    }
    if speak:
        t1 = time.perf_counter()
        try:
            speech = tts_mod.best_for(tgt).synthesize(translation.text, tgt)
            out["audio_b64"] = base64.b64encode(speech.wav_bytes).decode()
            out["latency"]["tts"] = round(time.perf_counter() - t1, 3)
            out["tts_engine"] = speech.engine
            out["tts_voice"] = speech.voice
            if "transliteration" in speech.voice:
                out["tts_note"] = (
                    "Santali audio is read via transliteration through the "
                    "Hindi voice - no offline Santali TTS exists."
                )
        except Exception as err:
            out["tts_unavailable"] = True
            out["tts_error"] = str(err)
    return out


def speak(text: str, lang: str) -> dict:
    """TTS only (replay button)."""
    t0 = time.perf_counter()
    speech = tts_mod.best_for(lang).synthesize(text, lang)
    return {
        "audio_b64": base64.b64encode(speech.wav_bytes).decode(),
        "sample_rate": speech.sample_rate,
        "engine": speech.engine,
        "voice": speech.voice,
        "latency_s": round(time.perf_counter() - t0, 3),
    }
