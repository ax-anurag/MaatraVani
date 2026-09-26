"""Hindi ASR with Vosk (small model, ~45 MB, real-time on CPU).

Chosen for the demo pipeline because recognition of short classroom
utterances completes in well under a second on modest hardware, which is
what keeps the voice-to-voice pipeline inside the 3-second target budget.
faster-whisper (asr/whisper.py) is the higher-accuracy alternative engine.
"""

from __future__ import annotations

import json
import threading
import time

from ... import config
from .. import audio
from ..base import ModelUnavailable, ASREngine, Transcript

try:
    from vosk import KaldiRecognizer, Model as VoskModel
    _VOSK_IMPORT_ERROR = None
except ImportError as e:  # package not installed — reported, never hidden
    VoskModel = None
    KaldiRecognizer = None
    _VOSK_IMPORT_ERROR = str(e)


class VoskEngine(ASREngine):
    name = "vosk-small-hi-0.22"
    languages = ("hi",)

    def __init__(self, model_dir=None):
        self.model_dir = model_dir or config.VOSK_HI_DIR
        self._model = None
        self._lock = threading.Lock()

    def _model_present(self) -> bool:
        return self.model_dir.exists() and any(self.model_dir.iterdir())

    def unavailable_reason(self) -> str | None:
        if _VOSK_IMPORT_ERROR:
            return f"vosk package not importable: {_VOSK_IMPORT_ERROR}"
        if not self._model_present():
            return (
                "Vosk Hindi model not downloaded; run scripts/download_models.py"
            )
        return None

    def available(self) -> bool:
        return self.unavailable_reason() is None

    def _ensure_model(self):
        if self._model is not None:
            return
        reason = self.unavailable_reason()
        if reason:
            raise ModelUnavailable(reason)
        with self._lock:
            if self._model is None:
                self._model = VoskModel(str(self.model_dir))

    def transcribe(self, wav_bytes: bytes, lang: str) -> Transcript:
        if lang not in self.languages:
            raise ModelUnavailable(f"vosk engine cannot do '{lang}'")
        self._ensure_model()
        pcm = audio.to_pcm16k_mono(wav_bytes)

        t0 = time.perf_counter()
        rec = KaldiRecognizer(self._model, audio.TARGET_RATE)
        rec.SetWords(False)
        chunk = 4096
        for i in range(0, len(pcm), chunk):
            rec.AcceptWaveform(pcm[i:i + chunk])
        result = rec.FinalResult()
        latency = time.perf_counter() - t0

        # vosk's Python binding returns the final result as a JSON *string*
        # on some builds and as an already-parsed dict on others - accept
        # both rather than assume.
        if isinstance(result, str):
            result = json.loads(result)
        text = (result or {}).get("text", "").strip()
        return Transcript(text=text, lang=lang, latency_s=round(latency, 3), engine=self.name)
