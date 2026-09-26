"""Generate Hindi demo audio for tests and the offline demo.

There is no microphone inside WSL2, so for automated tests we synthesize
Hindi speech with espeak-ng (the same engine that provides our Santali TTS).
It is robotic - ASR quality on synthetic speech is a lower bound, and the
README says so. A real demo should use the browser mic (which works fine
from the Windows side against the WSL backend).

    .venv/bin/python scripts/make_demo_audio.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "generated" / "demo_audio"


def main() -> int:
    if not shutil.which("espeak-ng"):
        print("espeak-ng not installed - install it first (see README).")
        return 1
    voices = subprocess.run(["espeak-ng", "--voices"], capture_output=True, text=True)
    if " hi" not in voices.stdout:
        print("espeak-ng has no Hindi voice on this system.")
        return 1

    sentences = json.loads(
        (ROOT / "content" / "demo" / "demo_sentences.json").read_text(encoding="utf-8")
    )["sentences"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for s in sentences:
        out = OUT_DIR / f"{s['id']}.wav"
        subprocess.run(
            ["espeak-ng", "-v", "hi", "-s", "140", "-w", str(out), s["hi"]],
            check=True,
        )
        print(f"  {out.name}  <- {s['hi']}")
    print(f"\ndone: {len(sentences)} files in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
