"""WAV plumbing without ffmpeg and without the removed `audioop` module.

The browser records 16-bit PCM WAV for us (see frontend/services/audio.js),
and espeak-ng writes WAV files, so all we need here is: parse RIFF, convert
to mono 16-bit, resample to 16 kHz for the ASR engines. Pure stdlib.
"""

from __future__ import annotations

import array
import io
import wave

TARGET_RATE = 16000


def read_wav(data: bytes) -> tuple[bytes, int]:
    """Parse a WAV file into (mono 16-bit PCM, sample_rate)."""
    try:
        with wave.open(io.BytesIO(data)) as w:
            nch = w.getnchannels()
            width = w.getsampwidth()
            rate = w.getframerate()
            frames = w.readframes(w.getnframes())
    except wave.Error as e:
        raise ValueError(f"not a readable 16-bit PCM WAV: {e}") from e

    if width == 2:
        samples = array.array("h")
        samples.frombytes(frames)
        if nch == 2:
            mono = array.array("h", ((samples[i] + samples[i + 1]) // 2 for i in range(0, len(samples), 2)))
            samples = mono
        elif nch > 2:
            mono = array.array("h", (sum(samples[i:i + nch]) // nch for i in range(0, len(samples), nch)))
            samples = mono
        pcm = samples.tobytes()
    elif width == 1:
        # 8-bit unsigned -> 16-bit signed. Channel mixdown first if needed,
        # and clamp: (255-128)*256 == 32768 would overflow a signed 16-bit.
        if nch > 1:
            frames = bytes(
                sum(frames[i:i + nch]) // nch for i in range(0, len(frames), nch)
            )
        samples = array.array(
            "h", (max(-32768, min(32767, (b - 128) * 256)) for b in frames)
        )
        pcm = samples.tobytes()
    elif width == 4:
        raw = array.array("i")
        raw.frombytes(frames)
        if nch > 1:
            raw = array.array("i", (sum(raw[i:i + nch]) // nch for i in range(0, len(raw), nch)))
        samples = array.array("h", (s >> 16 for s in raw))
        pcm = samples.tobytes()
    else:
        raise ValueError(f"unsupported sample width: {width} bytes")

    return pcm, rate


def resample(pcm: bytes, rate_from: int, rate_to: int = TARGET_RATE) -> bytes:
    """Linear-interpolation resample of 16-bit mono PCM. Good enough for
    speech; we are not chasing audiophile fidelity on a classroom tablet."""
    if rate_from == rate_to or not pcm:
        return pcm
    samples = array.array("h")
    samples.frombytes(pcm)
    n = len(samples)
    if n == 0:
        return pcm
    step = rate_from / rate_to
    out = array.array("h")
    pos = 0.0
    while pos < n - 1:
        i = int(pos)
        frac = pos - i
        out.append(int(samples[i] * (1 - frac) + samples[i + 1] * frac))
        pos += step
    return out.tobytes()


def to_pcm16k_mono(data: bytes) -> bytes:
    """WAV bytes in -> mono 16-bit PCM at 16 kHz out."""
    pcm, rate = read_wav(data)
    return resample(pcm, rate, TARGET_RATE)


def wav_duration_s(data: bytes) -> float:
    pcm, rate = read_wav(data)
    return len(pcm) / 2.0 / rate
