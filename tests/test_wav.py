"""WAV plumbing tests - stdlib only, no models.

Builds little WAV files with the `wave` module (16-bit stereo, 8-bit mono)
and checks the parser/mixdown/resampler behave. The 8-bit edge case exists
because (255 - 128) * 256 overflows signed 16-bit - a real bug the first
version had.
"""

import array
import io
import math
import wave

import pytest

from backend.engines import audio


def _wav_bytes(rate=8000, nch=1, width=2, samples=800):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(nch)
        w.setsampwidth(width)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(samples):
            v = int(20000 * math.sin(2 * math.pi * 100 * i / rate))
            if width == 2:
                frames += array.array("h", [v] * nch).tobytes()
            else:
                frames.append(128 + (v >> 9))  # 8-bit unsigned
        w.writeframes(bytes(frames))
    return buf.getvalue()


def test_stereo_mixdown():
    pcm, rate = audio.read_wav(_wav_bytes(nch=2))
    assert rate == 8000
    assert len(pcm) == 800 * 2, "stereo must mix down to mono (same sample count)"


def test_eight_bit_clamps_instead_of_overflowing():
    # All-255 bytes: (255-128)*256 == 32768 would overflow int16 -> must clamp.
    raw = _wav_bytes(rate=8000, nch=1, width=1, samples=64)
    pcm, rate = audio.read_wav(raw)
    samples = array.array("h")
    samples.frombytes(pcm)
    assert max(samples) <= 32767, "8-bit conversion must stay in int16 range"


def test_resample_doubles_length():
    pcm, _ = audio.read_wav(_wav_bytes(rate=8000))
    out = audio.resample(pcm, 8000, 16000)
    assert len(out) == pytest.approx(len(pcm) * 2, rel=0.02)


def test_resample_is_identity_when_rate_matches():
    pcm, _ = audio.read_wav(_wav_bytes(rate=16000))
    assert audio.resample(pcm, 16000, 16000) == pcm


def test_to_pcm16k_mono_end_to_end():
    out = audio.to_pcm16k_mono(_wav_bytes(rate=8000))
    assert len(out) > 0
    # 0.1 s of audio at 16 kHz = ~1600 samples = ~3200 bytes
    assert len(out) == pytest.approx(3200, rel=0.05)


def test_duration():
    raw = _wav_bytes(rate=16000, samples=16000)  # exactly 1 second
    assert audio.wav_duration_s(raw) == pytest.approx(1.0)


def test_garbage_is_rejected_honestly():
    with pytest.raises(ValueError):
        audio.read_wav(b"this is not a wav file at all")
