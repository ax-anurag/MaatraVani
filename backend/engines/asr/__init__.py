"""ASR engine selection: best available local engine wins.

Santali speech recognition does not exist as an offline model today — that
is a real gap, not something we paper over. The reverse (Santali -> Hindi)
voice direction therefore reports honestly unless an online provider with
credentials is configured.
"""

from __future__ import annotations

from ..base import ASREngine, ModelUnavailable
from . import vosk as vosk_mod
from . import whisper as whisper_mod

_ENGINES = None


def engines() -> list[ASREngine]:
    """All engine candidates, in preference order."""
    global _ENGINES
    if _ENGINES is None:
        _ENGINES = [vosk_mod.VoskEngine(), whisper_mod.WhisperEngine()]
    return _ENGINES


def best_for(lang: str) -> ASREngine:
    for e in engines():
        if e.available() and lang in e.languages:
            return e
    raise ModelUnavailable(
        f"No local ASR engine available for '{lang}'. "
        "Run scripts/download_models.py while online."
    )


def status() -> list[dict]:
    return [
        {
            "engine": e.name,
            "languages": list(e.languages),
            "available": e.available(),
            "reason": e.unavailable_reason() if hasattr(e, "unavailable_reason") else None,
        }
        for e in engines()
    ]
