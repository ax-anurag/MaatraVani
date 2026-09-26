"""Hindi ASR with faster-whisper (CTranslate2 Whisper), int8 on CPU.

The accuracy-minded alternative to Vosk. Whisper has no Santali — this
engine honestly refuses anything except its supported languages. Slower per
utterance than Vosk, but a useful second engine and our fallback if the
vosk wheel is unavailable on a given Python build.
"""

from __future__ import annotations

import io
import time

from ... import config
from ..base import ModelUnavailable, ASREngine, Transcript

try:
    from faster_whisper import WhisperModel
    _FW_IMPORT_ERROR = None
except ImportError as e:
    WhisperModel = None
    _FW_IMPORT_ERROR = str(e)


class WhisperEngine(ASREngine):
    name = "faster-whisper-small (int8)"
    languages = ("hi", "en")  # whisper is multilingual; we only commit to hi

    def __init__(self, model_dir=None):
        self.model_dir = model_dir or config.WHISPER_DIR
        self._model = None

    def unavailable_reason(self) -> str | None:
        if _FW_IMPORT_ERROR:
            return f"faster-whisper not importable: {_FW_IMPORT_ERROR}"
        if not (self.model_dir / "model.bin").exists():
            return "faster-whisper model not downloaded; run scripts/download_models.py"
        return None

    def available(self) -> bool:
        return self.unavailable_reason() is None

    def _ensure_model(self):
        if self._model is not None:
            return
        reason = self.unavailable_reason()
        if reason:
            raise ModelUnavailable(reason)
        self._model = WhisperModel(str(self.model_dir), device="cpu", compute_type="int8")

    def transcribe(self, wav_bytes: bytes, lang: str) -> Transcript:
        if lang not in self.languages:
            raise ModelUnavailable(f"whisper engine cannot do '{lang}'")
        self._ensure_model()
        t0 = time.perf_counter()
        segments, info = self._model.transcribe(io.BytesIO(wav_bytes), language=lang, beam_size=1)
        text = " ".join(s.text.strip() for s in segments).strip()
        latency = time.perf_counter() - t0
        return Transcript(text=text, lang=lang, latency_s=round(latency, 3), engine=self.name)
