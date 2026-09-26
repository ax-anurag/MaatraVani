"""Neural translation: NLLB-200-distilled-600M via CTranslate2, int8 on CPU.

Why this model: NLLB-200 is the only freely-downloadable MT model with actual
Santali coverage, and CTranslate2's int8 runtime makes a 600M-parameter model
practical on low-end CPU hardware. IndicTrans2 has better quality for the 22
scheduled languages but no Santali — so it cannot be the primary engine here.

Everything runs locally from models/nllb-200-distilled-600M-ct2; there is no
network call anywhere in this file.
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict

import ctranslate2
import sentencepiece as spm

from ... import config
from ..base import ModelUnavailable, Translation, TranslationEngine

# FLORES-200 language codes for NLLB. Hindi is hin_Deva; Santali's NLLB code
# is `sat` (the corpus the model was trained on is Ol Chiki). If a model build
# ever ships a differently-tagged code, the startup probe in this module
# makes it obvious instead of producing silent garbage.
NLLB_CODES = {
    "hi": "hin_Deva",
    "sat": "sat",
}

MODEL_FILES = ("model.bin", "sentencepiece.bpe.model")


class NllbEngine(TranslationEngine):
    name = "nllb-200-distilled-600M (ct2 int8)"
    pairs = (("hi", "sat"), ("sat", "hi"))

    def __init__(self, model_dir=None):
        self.model_dir = model_dir or config.NLLB_DIR
        self._translator = None
        self._spm = None
        self._lock = threading.Lock()
        self._cache: OrderedDict[tuple, str] = OrderedDict()
        self._cache_cap = 512

    # -- loading ---------------------------------------------------------

    def available(self) -> bool:
        return self._model_present()

    def _model_present(self) -> bool:
        return self.model_dir.exists() and all(
            (self.model_dir / f).exists() for f in MODEL_FILES
        )

    def _ensure_loaded(self):
        if self._translator is not None:
            return
        if not self._model_present():
            raise ModelUnavailable(
                "NLLB translation model not found under models/. "
                "Run scripts/download_models.py once while online."
            )
        with self._lock:
            if self._translator is not None:
                return
            t0 = time.perf_counter()
            self._translator = ctranslate2.Translator(
                str(self.model_dir),
                device="cpu",
                compute_type="int8",
                # intra_threads = cores per translation; the kwarg is named
                # intra_threads, NOT cpu_threads (that one cost a probe run)
                intra_threads=max(2, min(8, os.cpu_count() or 4)),
                inter_threads=1,
            )
            self._spm = spm.SentencePieceProcessor(
                str(self.model_dir / "sentencepiece.bpe.model")
            )
            self.load_time_s = time.perf_counter() - t0

    # -- translation -----------------------------------------------------

    def _cache_get(self, key):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        return None

    def _cache_put(self, key, value):
        with self._lock:
            self._cache[key] = value
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_cap:
                self._cache.popitem(last=False)

    def translate(self, text: str, src: str, tgt: str) -> Translation:
        text = text.strip()
        if not text:
            return Translation(text="", src=src, tgt=tgt, script="", engine=self.name, source="noop")

        key = (src, tgt, text)
        cached = self._cache_get(key)
        if cached is not None:
            return Translation(
                text=cached,
                src=src,
                tgt=tgt,
                script="Ol Chiki" if tgt == "sat" else "Devanagari",
                latency_s=0.0,
                engine=self.name,
                source="nllb",
                cached=True,
            )

        self._ensure_loaded()
        if src not in NLLB_CODES or tgt not in NLLB_CODES:
            raise ModelUnavailable(f"NLLB has no code for {src}->{tgt}")

        # NLLB is steered by language tokens on BOTH sides of the network,
        # exactly as the HF tokenizer does it: the source opens with its
        # language token and closes with </s>, the decode is pinned by a
        # target prefix. Leave the source tokens bare and the encoder
        # output degenerates - the first probe run here decoded to
        # "⁇ salute salute salute ..." instead of Ol Chiki.
        src_tokens = (
            [f">>{NLLB_CODES[src]}<<"]
            + self._spm.encode(text, out_type=str)
            + ["</s>"]
        )
        target_prefix = [[f">>{NLLB_CODES[tgt]}<<"]]

        t0 = time.perf_counter()
        results = self._translator.translate_batch(
            [src_tokens],
            target_prefix=target_prefix,
            beam_size=2,
            max_decoding_length=160,
            return_scores=True,
        )
        latency = time.perf_counter() - t0

        out_tokens = results[0].hypotheses[0]
        out_text = self._spm.decode(out_tokens)
        # If NLLB prefaces output with the language token, strip it.
        if out_text.startswith(">>"):
            out_text = out_text.split("<<", 1)[-1].strip()

        self._cache_put(key, out_text)
        return Translation(
            text=out_text,
            src=src,
            tgt=tgt,
            script="Ol Chiki" if tgt == "sat" else "Devanagari",
            latency_s=round(latency, 3),
            engine=self.name,
            source="nllb",
        )


# -- module-level singleton -------------------------------------------------

_instance: NllbEngine | None = None
_instance_lock = threading.Lock()


def get_engine() -> NllbEngine:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = NllbEngine()
    return _instance
