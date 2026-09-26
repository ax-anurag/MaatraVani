"""One-time model/font downloader.

Run this ONCE while online; everything it fetches lands under models/ and
frontend/fonts/, and the app then works fully offline. Downloads are
sequential and modest - a handful of HTTP requests plus the actual files,
kept far under the 25 req/min budget by design.

    .venv/bin/python scripts/download_models.py           # everything
    .venv/bin/python scripts/download_models.py --probe   # verify sat code

What gets downloaded and why (full details in PROVENANCE.md):
  * NLLB-200-distilled-600M  - Hindi<->Santali MT, as a CTranslate2 int8
    model. Third-party prebuilt conversions are tried first (they save the
    2.5 GB fp32 download); if none is reachable, the official facebook
    weights are downloaded and converted locally. The one-time conversion
    runs in its own throwaway venv (.venv-convert) because transformers
    wants a newer tokenizers than faster-whisper's pin in the app venv.
  * vosk-model-small-hi-0.22                      - Hindi ASR, ~45 MB
  * faster-whisper-small                           - alternative ASR engine
  * Noto Sans Ol Chiki + Noto Sans Devanagari      - fonts for UI and PDFs
"""

from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODELS = ROOT / "models"
FONTS = ROOT / "frontend" / "fonts"

NLLB_CT2_DIRNAME = "nllb-200-distilled-600M-ct2"
NLLB_SOURCE_REPO = "facebook/nllb-200-distilled-600M"  # official fp32 weights
# Prebuilt CTranslate2 conversions, tried in order before converting
# ourselves. HF repo ids are case-sensitive, so both spellings are listed;
# the michaelfeil ct2fast family became unreachable in Sept 2026, which is
# exactly why the local conversion fallback below exists.
NLLB_PREBUILT_REPOS = [
    "michaelfeil/ct2fast-nllb-200-distilled-600m",
    "michaelfeil/ct2fast-nllb-200-distilled-600M",
]
NLLB_SOURCE_PATTERNS = [
    "config.json", "pytorch_model.bin", "sentencepiece.bpe.model",
    "tokenizer_config.json", "special_tokens_map.json", "generation_config.json",
]
WHISPER_REPO = "Systran/faster-whisper-small"
VOSK_URL = "https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip"

FONT_CANDIDATES = {
    "NotoSansOlChiki-Regular.ttf": [
        "https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts/NotoSansOlChiki/hinted/ttf/NotoSansOlChiki-Regular.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansolchiki/NotoSansOlChiki-Regular.ttf",
    ],
    "NotoSansDevanagari-Regular.ttf": [
        "https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts/NotoSansDevanagari/hinted/ttf/NotoSansDevanagari-Regular.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansdevanagari/NotoSansDevanagari%5Bwdth%2Cwght%5D.ttf",
    ],
}


def human(n_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n_bytes < 1024 or unit == "GB":
            return f"{n_bytes:.1f} {unit}"
        n_bytes /= 1024
    return f"{n_bytes} B"


def fetch(url: str, dest: Path, desc: str) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  [skip] {desc} (already present)")
        return
    print(f"  [get ] {desc}\n         {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as resp, open(tmp, "wb") as f:
        shutil.copyfileobj(resp, f)
    tmp.rename(dest)
    print(f"  [ ok ] {desc} -> {dest.relative_to(ROOT)} ({human(dest.stat().st_size)})")


def download_font(name: str, candidates: list[str]) -> None:
    for url in candidates:
        try:
            fetch(url, FONTS / name, name)
            data = (FONTS / name).read_bytes()[:4]
            if data[:2] not in (b"\x00\x01", b"OTTO") and data != b"wOFF":
                raise ValueError("not a valid TTF/OTF header")
            return
        except Exception as e:
            print(f"  [fail] {url}: {e}")
            (FONTS / name).unlink(missing_ok=True)
    raise RuntimeError(f"could not download font {name} from any source")


def _uv() -> str:
    exe = shutil.which("uv") or str(Path.home() / ".local" / "bin" / "uv")
    if not Path(exe).exists():
        raise RuntimeError("uv not found - run scripts/bootstrap.sh first")
    return exe


def _app_ct2_version() -> str:
    """The ctranslate2 version the APP venv runs - the conversion venv must
    match it, so the model it writes is loadable by the app."""
    out = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), "-c",
         "import ctranslate2; print(ctranslate2.__version__)"],
        capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _ensure_convert_venv() -> Path:
    """A throwaway venv for the one-time fp32 -> int8 conversion. Kept
    separate on purpose: transformers requires a newer tokenizers than the
    faster-whisper tokenizers==0.13.3 pin in the app venv, and the app must
    keep its pins. Delete .venv-convert afterwards if you like - the model
    it produced stays."""
    venv = ROOT / ".venv-convert"
    converter = venv / "bin" / "ct2-transformers-converter"
    pip = [_uv(), "pip", "install", "--python", str(venv / "bin" / "python")]
    if not converter.exists():
        print("  building one-time conversion venv (.venv-convert; torch CPU ~200 MB)")
        subprocess.run([_uv(), "venv", "--python", "3.11", str(venv)], check=True)
        subprocess.run([*pip, "torch",
                        "--index-url", "https://download.pytorch.org/whl/cpu"], check=True)
    # Conversion deps are re-ensured on EVERY run (uv no-ops fast when
    # already satisfied). Two details learned from real failures:
    #   * protobuf - transformers needs it to read the sentencepiece
    #     vocabulary; without it the converter silently falls back to a
    #     tiktoken path and dies with "tiktoken is required".
    #   * transformers 4.56 - v5 changed slow-tokenizer loading enough to
    #     break the ct2 converter's M2M100 (NLLB) path, while ctranslate2
    #     4.5+ passes `dtype=` to from_pretrained, which only transformers
    #     >=4.56 accepts. 4.56.x is the window where both work.
    subprocess.run([*pip, "transformers==4.56.2", "sentencepiece", "protobuf",
                    f"ctranslate2=={_app_ct2_version()}"], check=True)
    return venv


def fetch_nllb(snapshot_download) -> None:
    """Get the NLLB ct2 model onto disk: prebuilt if one is reachable,
    otherwise download the official weights and convert locally."""
    ct2_dir = MODELS / NLLB_CT2_DIRNAME
    if (ct2_dir / "model.bin").exists() and (ct2_dir / "sentencepiece.bpe.model").exists():
        print("  [skip] NLLB ct2 model (already present)")
        return

    for repo in NLLB_PREBUILT_REPOS:
        try:
            print(f"  [try ] prebuilt conversion: {repo}")
            snapshot_download(
                repo_id=repo,
                local_dir=str(ct2_dir),
                allow_patterns=["model.bin", "sentencepiece.bpe.model",
                                "config.json", "shared_vocabs/*"],
            )
            missing = [f for f in ("model.bin", "sentencepiece.bpe.model")
                      if not (ct2_dir / f).exists()]
            if not missing:
                print(f"  -> {ct2_dir} (prebuilt)")
                return
            print(f"  [fail] {repo}: incomplete download {missing}")
        except Exception as e:
            print(f"  [fail] {repo}: {type(e).__name__}")

    print("  no prebuilt conversion reachable - converting the official weights")
    print("  (downloads ~2.5 GB fp32 once, produces ~0.7 GB int8)")
    src_dir = MODELS / "nllb-200-distilled-600M-src"
    snapshot_download(
        repo_id=NLLB_SOURCE_REPO,
        local_dir=str(src_dir),
        allow_patterns=NLLB_SOURCE_PATTERNS,
    )
    venv = _ensure_convert_venv()
    print("  converting to CTranslate2 int8 (a few minutes on CPU)")
    ct2_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(venv / "bin" / "ct2-transformers-converter"),
         "--model", str(src_dir),
         "--output_dir", str(ct2_dir),
         "--quantization", "int8",
         # --force: a failed prebuilt attempt may have left the (empty)
         # output dir behind, and re-runs must overwrite cleanly
         "--force"],
        check=True,
    )
    # The engine loads the sentencepiece model directly; make sure it sits
    # next to model.bin (the converter usually copies it, older builds don't).
    sp = ct2_dir / "sentencepiece.bpe.model"
    if not sp.exists():
        shutil.copy2(src_dir / "sentencepiece.bpe.model", sp)
    missing = [f for f in ("model.bin", "sentencepiece.bpe.model")
               if not (ct2_dir / f).exists()]
    if missing:
        raise RuntimeError(f"conversion left the model dir incomplete: {missing}")
    print(f"  -> {ct2_dir} (converted locally, int8)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true",
                        help="after download, verify the NLLB Santali language code")
    args = parser.parse_args()

    from huggingface_hub import snapshot_download

    MODELS.mkdir(exist_ok=True)
    FONTS.mkdir(parents=True, exist_ok=True)

    print("== fonts ==")
    for name, urls in FONT_CANDIDATES.items():
        download_font(name, urls)

    print("== NLLB-200-distilled-600M (CTranslate2 int8) ==")
    fetch_nllb(snapshot_download)
    nllb_dir = MODELS / NLLB_CT2_DIRNAME
    print(f"  -> {nllb_dir} ({human(sum(p.stat().st_size for p in nllb_dir.rglob('*') if p.is_file()))})")

    print("== faster-whisper small ==")
    whisper_dir = MODELS / "faster-whisper-small"
    snapshot_download(
        repo_id=WHISPER_REPO,
        local_dir=str(whisper_dir),
        allow_patterns=["model.bin", "config.json", "tokenizer.json", "vocabulary*"],
    )
    print(f"  -> {whisper_dir}")

    print("== vosk small Hindi ==")
    vosk_zip = MODELS / "vosk-small-hi-0.22.zip"
    vosk_dir = MODELS / "vosk-small-hi-0.22"
    if vosk_dir.exists() and any(vosk_dir.iterdir()):
        print("  [skip] vosk model (already present)")
    else:
        fetch(VOSK_URL, vosk_zip, "vosk-model-small-hi-0.22.zip")
        with zipfile.ZipFile(io.BytesIO(vosk_zip.read_bytes())) as zf:
            zf.extractall(MODELS)
        inner = MODELS / "vosk-model-small-hi-0.22"
        if inner.exists() and inner != vosk_dir:
            inner.rename(vosk_dir)
        vosk_zip.unlink(missing_ok=True)
        print(f"  -> {vosk_dir}")

    if args.probe:
        print("\n== probe: hin -> sat with NLLB ==")
        from backend.engines.translation.nllb import NllbEngine
        eng = NllbEngine()
        result = eng.translate("नमस्ते बच्चों।", "hi", "sat")
        print(f"  output: {result.text!r}")
        has_olchiki = any("᱐" <= ch <= "᱿" for ch in result.text)
        print(f"  contains Ol Chiki: {has_olchiki}")
        if not has_olchiki:
            print("  NOTE: model returned non-Ol-Chiki output - the transliteration")
            print("  layer (docs/limitations) applies; see README 'Translation output'.")

    print("\ndone. Models are local; the app no longer needs the network.")


if __name__ == "__main__":
    main()
