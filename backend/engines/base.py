"""Engine abstractions — the provider boundary of MaatraVani.

No part of the application calls a concrete ASR/translation/TTS stack
directly; it talks to these interfaces. That is what lets us run the best
local engine today (CTranslate2 NLLB, Vosk, espeak-ng) and swap in a better
one — or a cloud fallback, or future Ho/Mundari engines — without touching
the rest of the app.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class EngineError(Exception):
    """Something an engine wants to report. Never silently faked."""


class ModelUnavailable(EngineError):
    """The model/binary behind an engine is not present on this machine.

    The API layer turns this into an honest 503 with a clear message —
    e.g. "Santali TTS model unavailable" — instead of pretending.
    """


@dataclass
class Transcript:
    text: str
    lang: str
    latency_s: float
    engine: str


@dataclass
class Translation:
    text: str
    src: str
    tgt: str
    script: str = ""
    latency_s: float = 0.0
    engine: str = ""
    source: str = ""  # "lexicon" | "nllb" | "bhashini" | ...
    cached: bool = False


@dataclass
class Speech:
    wav_bytes: bytes
    sample_rate: int
    latency_s: float
    engine: str
    voice: str = ""


class ASREngine(ABC):
    name: str = "asr"
    languages: tuple[str, ...] = ()

    @abstractmethod
    def transcribe(self, wav_bytes: bytes, lang: str) -> Transcript:
        """Audio (16 kHz mono WAV) in, text out."""

    def available(self) -> bool:
        return True


class TranslationEngine(ABC):
    name: str = "mt"
    pairs: tuple[tuple[str, str], ...] = ()

    @abstractmethod
    def translate(self, text: str, src: str, tgt: str) -> Translation:
        """Text in, translated text out (Santali rendered in Ol Chiki)."""

    def supports(self, src: str, tgt: str) -> bool:
        return (src, tgt) in self.pairs or (tgt, src) in self.pairs

    def available(self) -> bool:
        return True


class TTSEngine(ABC):
    name: str = "tts"
    languages: tuple[str, ...] = ()

    @abstractmethod
    def synthesize(self, text: str, lang: str) -> Speech:
        """Text in, WAV audio out (mono, 16-bit PCM)."""

    def available(self) -> bool:
        return True
