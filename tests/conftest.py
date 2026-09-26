"""Shared test fixtures.

The suite is split by design:
  * logic tests (limiter, wav, lexicon, mesh) run anywhere, no models needed;
  * engine tests (translation, asr, tts, pipeline, materials) SKIP with an
    explicit reason when the model/binary they need was not downloaded yet.
Skipping is honest: a skipped test says "not installed", it never says
"works".

No test file ever hard-codes Santali text: the autonym fixture is read
straight out of CLAUDE.md so a mistyped glyph can never sneak in here.
"""

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import config  # noqa: E402

# Ol Chiki is exactly U+1C50..U+1C7F. Neighbouring blocks (Balinese,
# Sundanese, Batak, Lepcha) carry visually confusable glyphs - a stray
# character from any of them means someone re-typed Santali by hand and
# got it wrong. Hence: never retype it; always copy it from a source.
_OLCHIKI_RUN = re.compile("[\U00001c50-\U00001c7f]+")


def brief_autonym() -> str:
    """The Santali autonym in Ol Chiki, lifted straight out of the project
    brief (CLAUDE.md, 'Test using actual Unicode characters') so tests and
    fixtures never depend on anyone re-typing the glyphs - including me."""
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    tokens = _OLCHIKI_RUN.findall(text)
    if not tokens:
        raise RuntimeError("CLAUDE.md should contain an Ol Chiki example string")
    return max(tokens, key=len)


@pytest.fixture(scope="session")
def autonym():
    return brief_autonym()


def nllb_ready() -> bool:
    return (config.MODELS_DIR / "nllb-200-distilled-600M-ct2" / "model.bin").exists()


def fonts_ready() -> bool:
    return (
        (config.FRONTEND_DIR / "fonts" / "NotoSansOlChiki-Regular.ttf").exists()
        and (config.FRONTEND_DIR / "fonts" / "NotoSansDevanagari-Regular.ttf").exists()
    )


def espeak_ready() -> bool:
    return shutil.which("espeak-ng") is not None


def demo_audio_dir() -> Path:
    return config.GENERATED_DIR / "demo_audio"


def demo_audio_ready() -> bool:
    d = demo_audio_dir()
    return d.exists() and any(d.glob("*.wav"))


requires_nllb = pytest.mark.skipif(
    not nllb_ready(), reason="NLLB model not downloaded - run scripts/download_models.py")
requires_fonts = pytest.mark.skipif(
    not fonts_ready(), reason="Noto fonts not downloaded - run scripts/download_models.py")
requires_espeak = pytest.mark.skipif(
    not espeak_ready(), reason="espeak-ng not installed (see README)")
requires_demo_audio = pytest.mark.skipif(
    not demo_audio_ready(),
    reason="demo WAVs not generated - run scripts/make_demo_audio.py")


@pytest.fixture
def temp_lexicon(tmp_path):
    """A tiny verified lexicon on disk, so lexicon logic is tested against
    a file we control rather than the (growing) real dataset.

    The one pairing it holds is real and checkable: the language's own
    name (Hindi side in Devanagari, Santali side in Ol Chiki). The Ol
    Chiki value is read out of CLAUDE.md at runtime - nobody re-types it.
    """
    entry = {
        "id": "santali",
        "kind": "word",
        "category": "classroom",
        "hi": "संथाली",
        "sat": brief_autonym(),
        "en": "Santali",
        "icon": "",
        "source": "test fixture (language autonym)",
    }
    path = tmp_path / "lexicon.json"
    path.write_text(
        json.dumps({"meta": {"version": "test"}, "entries": [entry]}),
        encoding="utf-8",
    )
    return path
