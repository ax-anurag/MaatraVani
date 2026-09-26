"""Speech synthesis via espeak-ng.

Reality check, stated plainly: there is no offline Santali TTS anywhere
today, and upstream espeak-ng ships no `sat` voice either (verified
against dictsource/ on master, Sept 2026). MaatraVani therefore says
Santali text out loud through a labelled transliteration path: the Ol
Chiki text is mapped letter-by-letter into Devanagari
(backend/engines/tts/sat_translit.py) and read by espeak-ng's Hindi
voice. Same actual Santali words, Hindi phonology - the UI names the
voice "hi (Santali transliteration)" wherever the audio plays, never a
native voice.

The engine still prefers a genuine `sat` voice if the installed
espeak-ng ever grows one (checked live against `espeak-ng --voices`,
nothing is assumed).

If espeak-ng or the `hi` voice is missing, the engine raises
ModelUnavailable and the app says "Santali TTS unavailable" rather than
playing unrelated audio.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from ..base import ModelUnavailable, Speech, TTSEngine
from .sat_translit import olchiki_to_devanagari

VOICES = {"sat": "sat", "hi": "hi"}

# What the UI shows for the voice that actually spoke. Honest labelling:
# the fallback is named as the transliteration it is.
SAT_FALLBACK_VOICE = "hi (Santali transliteration)"


class EspeakEngine(TTSEngine):
    name = "espeak-ng"
    languages = ("sat", "hi")

    def __init__(self):
        self._voices_cache: set[str] | None = None
        self._probe_error: str | None = None
        self._lock = threading.Lock()

    def _binary(self) -> str | None:
        return shutil.which("espeak-ng")

    def _known_voices(self) -> set[str]:
        if self._voices_cache is not None:
            return self._voices_cache
        binary = self._binary()
        if not binary:
            return set()
        out = subprocess.run(
            [binary, "--voices"], capture_output=True, text=True, timeout=10
        )
        if out.returncode != 0 or not out.stdout.strip():
            # The binary is on disk but cannot start (on the demo box: a
            # missing shared library). Reporting "no such voice" here would
            # hide the real problem, so keep the loader's own words.
            first = out.stderr.strip().splitlines()[:1]
            self._probe_error = (
                "espeak-ng is installed but fails to run: "
                + (first[0] if first else f"exit code {out.returncode}")
            )
            self._voices_cache = set()
            return self._voices_cache
        langs = set()
        for line in out.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                langs.add(parts[1].split("-")[0])
        self._voices_cache = langs
        return langs

    def unavailable_reason(self) -> str | None:
        if not self._binary():
            return "espeak-ng binary not found (install espeak-ng)"
        # A binary that cannot even start is unavailable too - probe once
        # so the status endpoint can say why instead of guessing.
        self._known_voices()
        if self._probe_error:
            return self._probe_error
        if "hi" not in self._known_voices():
            # Santali rides on the Hindi voice (transliteration fallback),
            # so hi missing means BOTH languages are mute.
            return "espeak-ng has no Hindi voice installed"
        return None

    def available(self) -> bool:
        return self.unavailable_reason() is None

    def language_available(self, lang: str) -> bool:
        if lang not in VOICES:
            return False
        # sat needs a genuine sat voice OR the hi fallback voice.
        need = "sat" if lang == "sat" and "sat" in self._known_voices() else "hi"
        return need in self._known_voices()

    def synthesize(self, text: str, lang: str) -> Speech:
        binary = self._binary()
        if not binary:
            raise ModelUnavailable("Santali TTS unavailable: espeak-ng is not installed.")
        if lang not in VOICES:
            raise ModelUnavailable(f"espeak-ng engine has no voice for '{lang}'")
        if not self.language_available(lang):
            if self._probe_error:
                raise ModelUnavailable(f"TTS unavailable: {self._probe_error}")
            raise ModelUnavailable(
                "espeak-ng has no usable voice here - install espeak-ng "
                "with its Hindi voice (scripts/install_espeak_nosudo.sh)."
            )
        text = text.strip()
        if not text:
            raise ModelUnavailable("nothing to say")

        # A genuine `sat` voice wins when the machine really has one - but
        # a voice can be *listed* yet unusable (its compiled dictionary
        # missing, for instance). If speaking through it fails we still owe
        # the teacher audio, so we fall through to the labelled
        # transliteration on the Hindi voice instead of raising.
        if lang == "sat" and "sat" in self._known_voices():
            attempts = (
                ("sat", text, "sat"),
                ("hi", olchiki_to_devanagari(text), SAT_FALLBACK_VOICE),
            )
        elif lang == "sat":
            attempts = (("hi", olchiki_to_devanagari(text), SAT_FALLBACK_VOICE),)
        else:
            attempts = (("hi", text, "hi"),)

        t0 = time.perf_counter()
        wav = None
        label = attempts[0][2]
        failure = "espeak-ng produced no audio"
        for voice, spoken, label in attempts:
            try:
                wav = self._speak_to_wav(voice, spoken)
                if len(wav) >= 200:  # header alone is ~44 bytes; near-empty = nothing spoken
                    break
                failure = f"espeak-ng voice '{voice}' produced silent audio"
                wav = None
            except subprocess.CalledProcessError as err:
                detail = (err.stderr or b"").decode(errors="replace").strip()
                failure = f"espeak-ng voice '{voice}' failed: {detail or err}"
        latency = time.perf_counter() - t0

        if wav is None:
            # Both attempts failed: report it, never play unrelated audio.
            raise ModelUnavailable(f"refusing to fake it - {failure}")
        return Speech(
            wav_bytes=wav, sample_rate=22050, latency_s=round(latency, 3),
            engine=self.name, voice=label,
        )

    def _speak_to_wav(self, voice: str, spoken: str) -> bytes:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out_path = Path(tmp.name)
        try:
            # -s words/min: slow it down a little for classroom clarity
            subprocess.run(
                [self._binary(), "-v", voice, "-s", "140", "-w", str(out_path), spoken],
                check=True,
                capture_output=True,
                timeout=30,
            )
            return out_path.read_bytes()
        finally:
            out_path.unlink(missing_ok=True)


_instance: EspeakEngine | None = None


def get_engine() -> EspeakEngine:
    global _instance
    if _instance is None:
        _instance = EspeakEngine()
    return _instance
