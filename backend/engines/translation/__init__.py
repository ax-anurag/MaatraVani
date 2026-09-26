from .composite import ClassroomTranslationEngine, get_engine
from .lexicon import LexiconEngine, is_olchiki
from .nllb import NllbEngine

# Factory alias: the pipeline, curriculum generator and offline demo all
# ask for translation_engine() - same object, friendlier name at the
# call sites that read like ASR's best_for() / TTS's best_for().
translation_engine = get_engine

__all__ = [
    "ClassroomTranslationEngine",
    "LexiconEngine",
    "NllbEngine",
    "get_engine",
    "translation_engine",
    "is_olchiki",
]
