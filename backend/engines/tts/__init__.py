"""TTS engine selection. espeak-ng is the only local engine we ship; the
optional Bhashini provider (providers/bhashini.py) is the online fallback
and is invisible unless credentials are configured."""

from __future__ import annotations

from ..base import ModelUnavailable, TTSEngine
from . import espeak as espeak_mod


def engine() -> TTSEngine:
    return espeak_mod.get_engine()


def best_for(lang: str) -> TTSEngine:
    e = espeak_mod.get_engine()
    if e.available() and lang in e.languages:
        return e
    raise ModelUnavailable(
        f"No local TTS engine available for '{lang}'. "
        f"({e.unavailable_reason() or 'voice missing'})"
    )


def status() -> list[dict]:
    e = espeak_mod.get_engine()
    reason = e.unavailable_reason()
    voices = {}
    if reason is None:
        voices = {lang: e.language_available(lang) for lang in e.languages}
    return [
        {
            "engine": e.name,
            "available": reason is None,
            "reason": reason,
            "voices": voices,
        }
    ]
