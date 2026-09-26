"""Engine facade — the single import surface for the rest of the app."""

from .asr import best_for as best_asr, engines as asr_engines, status as asr_status
from .base import (
    ASREngine,
    EngineError,
    ModelUnavailable,
    Speech,
    Transcript,
    Translation,
    TranslationEngine,
    TTSEngine,
)
from .providers import bhashini
from .translation import get_engine as translation_engine
from .tts import best_for as best_tts, status as tts_status


def snapshot() -> dict:
    """What is actually loaded/available right now. Powers /api/status —
    the UI shows exactly this, so the demo can't overstate itself."""
    from .. import config

    mt = translation_engine()
    return {
        "offline_mode": config.OFFLINE_MODE,
        "translation": mt.status(),
        "asr": asr_status(),
        "tts": tts_status(),
        "bhashini": {
            "configured": bhashini.provider().configured(),
            "enabled": bhashini.provider().available(),
        },
        "languages": config.LANGUAGES,
    }


__all__ = [
    "ASREngine", "EngineError", "ModelUnavailable", "Speech",
    "Transcript", "Translation", "TranslationEngine", "TTSEngine",
    "asr_engines", "asr_status", "best_asr", "best_tts",
    "bhashini", "translation_engine", "snapshot", "tts_status",
]
