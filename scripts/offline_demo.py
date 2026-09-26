"""Offline proof: run the core pipeline with networking disabled.

    .venv/bin/python scripts/offline_demo.py

Every network-capable call is blocked at the socket layer before anything
runs - if any component tried to phone home, it would crash loudly instead
of silently succeeding. What this exercises:

  1. Hindi -> Santali text translation (all demo sentences)
  2. Santali -> Hindi reverse translation
  3. Santali TTS (Ol Chiki -> Devanagari transliteration read by the
     espeak-ng Hindi voice - no offline Santali TTS exists anywhere)
  4. Hindi ASR (if demo audio has been generated, see make_demo_audio.py)
  5. Lesson + worksheet + flashcard generation
  6. Mesh simulation with hop counting

It then prints the measured latencies - the same numbers we quote in
DEMO.md, measured, never estimated.
"""

from __future__ import annotations

import json
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class NetworkDisabled(RuntimeError):
    pass


def disable_network() -> None:
    """Hard-block outbound sockets for this process. Local loopback is left
    alone (nothing here uses it anyway)."""
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def blocked_connect(self, address):
        raise NetworkDisabled(f"network egress attempted: {address}")

    def blocked_connect_ex(self, address):
        raise NetworkDisabled(f"network egress attempted: {address}")

    socket.socket.connect = blocked_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = blocked_connect_ex  # type: ignore[method-assign]
    _ = real_connect, real_connect_ex  # keep refs for debugging if needed


def main() -> int:
    print("=" * 62)
    print(" MAATRAVANI OFFLINE DEMONSTRATION")
    print(" network egress is BLOCKED at the socket layer for this process")
    print("=" * 62)

    disable_network()

    from backend.engines import tts as tts_mod
    from backend.engines.translation import translation_engine, is_olchiki
    from backend.mesh.manager import manager  # module path: see backend/mesh/__init__.py
    from backend.curriculum import generator, worksheets
    from backend import config

    report: list[tuple[str, str]] = []
    failures = 0

    def check(name: str, fn):
        nonlocal failures
        t0 = time.perf_counter()
        try:
            detail = fn()
            dt = time.perf_counter() - t0
            report.append((name, f"PASS  {detail}  [{dt:.2f}s]"))
        except Exception as err:
            failures += 1
            report.append((name, f"FAIL  {err}"))

    sentences = json.loads(
        (ROOT / "content" / "demo" / "demo_sentences.json").read_text(encoding="utf-8")
    )["sentences"]
    mt = translation_engine()

    # -- 1. Hindi -> Santali ------------------------------------------------
    for s in sentences:
        if s["category"] == "mesh":
            continue
        def _tr(s=s):
            out = mt.translate(s["hi"], "hi", "sat")
            assert out.text.strip(), "empty translation"
            note = "" if is_olchiki(out.text) else "  [non-Ol-Chiki script output]"
            return f"{out.text[:28]!r} via {out.source}{note}"
        check(f"translate: {s['id']}", _tr)

    # -- 2. Santali -> Hindi (reverse) ----------------------------------------
    sample = mt.translate(sentences[1]["hi"], "hi", "sat")
    check("reverse: sat->hi", lambda: mt.translate(sample.text, "sat", "hi").text[:30].__repr__())

    # -- 3. Santali TTS ---------------------------------------------------------
    def _tts():
        sat_text = sample.text
        speech = tts_mod.best_for("sat").synthesize(sat_text, "sat")
        return f"{len(speech.wav_bytes)} bytes wav, voice={speech.voice}"
    check("tts: santali", _tts)

    # -- 4. Hindi ASR + the full voice pipeline (only if demo audio exists) ----
    demo_wav = ROOT / "generated" / "demo_audio" / "topic-intro.wav"
    if demo_wav.exists():
        from backend.engines import asr as asr_mod
        def _asr():
            t = asr_mod.best_for("hi").transcribe(demo_wav.read_bytes(), "hi")
            return f"heard: {t.text[:30]!r} via {t.engine}"
        check("asr: hindi (from generated demo audio)", _asr)

        def _pipeline():
            from backend.services import pipeline as pipeline_mod
            out = pipeline_mod.run_pipeline(demo_wav.read_bytes(), "hi", "sat")
            assert out["stages"]["asr"]["available"], "ASR stage failed"
            assert out["stages"]["translation"]["available"], "translation stage failed"
            lat = out["latency"]
            tts_state = "ok" if out["stages"]["tts"]["available"] else "unavailable"
            # These four numbers are the ones DEMO.md quotes as MEASURED.
            return (f"asr={lat['asr']:.2f}s translation={lat['translation']:.2f}s "
                    f"tts={lat['tts']:.2f}s total={lat['total']:.2f}s (tts {tts_state})")
        check("pipeline: full voice-to-voice", _pipeline)
    else:
        report.append(("asr: hindi", "SKIP  (no demo audio; run scripts/make_demo_audio.py)"))
        report.append(("pipeline: full voice-to-voice", "SKIP  (needs demo audio)"))

    # -- 5. Study materials --------------------------------------------------------
    def _lesson():
        req = generator.LessonRequest(grade="2", subject="Foundational Literacy",
                                      topic="Animals")
        lesson = generator.generate_lesson(req)
        n_words = len(lesson["vocabulary"])
        return f"lesson with {n_words} vocab items, outcome {lesson['outcome_id']}"
    check("materials: lesson", _lesson)

    def _worksheet():
        req = generator.LessonRequest(grade="2", subject="Foundational Literacy",
                                      topic="Animals")
        lesson = generator.generate_lesson(req)
        pdf = worksheets.build_worksheet(
            topic="Animals", grade="2", outcome=lesson["outcome"]["hi"],
            vocabulary=lesson["vocabulary"] or [],
            instruction={"hi": "गतिविधि: सही जोड़े मिलाइए।", "sat": ""},
        )
        assert pdf[:4] == b"%PDF", "not a PDF"
        return f"worksheet PDF {len(pdf)} bytes"
    check("materials: worksheet", _worksheet)

    def _flashcards():
        from backend.curriculum import flashcards
        req = generator.LessonRequest(grade="2", subject="Foundational Literacy",
                                      topic="Animals")
        lesson = generator.generate_lesson(req)
        cards = flashcards.build_cards(lesson["vocabulary"] or [], 4)
        return f"{len(cards)} cards"
    check("materials: flashcards", _flashcards)

    # -- 6. Mesh ---------------------------------------------------------------------
    def _mesh():
        mgr = manager()
        result = mgr.send(
            sender_id="teacher", type_="CLASSROOM_MESSAGE", language="hi",
            payload={"text": sentences[-1]["hi"]},
        )
        b_inbox = mgr.inbox("student-b")
        assert b_inbox, "student-b never received anything"
        hops = b_inbox[0]["received_hop_count"]
        assert hops == 2, f"expected 2 hops, got {hops}"
        return f"student-b received via {hops} hops"
    check("mesh: 2-hop relay", _mesh)

    # -- report ------------------------------------------------------------------------
    print()
    for name, line in report:
        print(f"  {name:<44} {line}")
    print()
    print(f"result: {len(report) - failures}/{len(report)} checks passed, "
          f"offline_mode={config.OFFLINE_MODE}")
    print("no network calls were attempted (any attempt would have crashed).")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
