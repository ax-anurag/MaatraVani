"""Central configuration: paths, env flags, language registry.

Everything the app needs lives under the repo root — models, content and
fonts are all local files, which is what makes offline mode real.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MODELS_DIR = ROOT / "models"
CONTENT_DIR = ROOT / "content"
GENERATED_DIR = ROOT / "generated"
FRONTEND_DIR = ROOT / "frontend"

LEXICON_PATH = CONTENT_DIR / "vocabulary" / "lexicon.json"
OUTCOMES_PATH = CONTENT_DIR / "lessons" / "fln_outcomes.json"
DEMO_SENTENCES_PATH = CONTENT_DIR / "demo" / "demo_sentences.json"

# Model subdirectories, downloaded once by scripts/download_models.py
NLLB_DIR = MODELS_DIR / "nllb-200-distilled-600M-ct2"
VOSK_HI_DIR = MODELS_DIR / "vosk-small-hi-0.22"
WHISPER_DIR = MODELS_DIR / "faster-whisper-small"


def _load_dotenv() -> None:
    """Tiny .env reader — avoids a dependency for one build-time nicety."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes")


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


# When MATR_OFFLINE=1 the app refuses every network egress path, even if
# online credentials happen to be present. This is how the offline demo stays
# honest: nothing can phone home by accident.
OFFLINE_MODE = env_flag("MATR_OFFLINE")

# Hard cap on API usage: N requests per rolling 60 s across all /api/* routes.
RATE_LIMIT_PER_MIN = env_int("MATR_RATE_LIMIT", 25)

HOST = os.environ.get("MATR_HOST", "127.0.0.1")
PORT = env_int("MATR_PORT", 8000)

# Optional Bhashini/ULCA fallback. Empty credentials => provider stays disabled
# and hidden in the UI. Offline mode overrides this even when set.
BHASHINI = {
    "api_key": os.environ.get("BHASHINI_API_KEY", ""),
    "user_id": os.environ.get("BHASHINI_USER_ID", ""),
    "mt_model_id": os.environ.get("BHASHINI_TRANSLATION_MODEL_ID", ""),
    "asr_model_id": os.environ.get("BHASHINI_ASR_MODEL_ID", ""),
    "tts_model_id": os.environ.get("BHASHINI_TTS_MODEL_ID", ""),
}

# The languages we can honestly serve today, and the ones we deliberately
# do NOT pretend to serve. "planned" shows in the UI as
# "Planned / Future Language" and is not selectable.
LANGUAGES = {
    "hi": {"name": "Hindi", "script": "Deva", "status": "available"},
    "sat": {"name": "Santali", "script": "Ol Chiki", "status": "available"},
    "hoc": {"name": "Ho", "script": "Varang Kshiti", "status": "planned"},
    "muq": {"name": "Mundari", "script": "Nag Mundari", "status": "planned"},
}
