"""Optional online fallback: Bhashini (ULCA) cloud services.

Honest contract for this module:

* It is OFF by default and invisible in the UI when credentials are absent.
* It is disabled outright when MATR_OFFLINE=1 — offline mode never touches
  the network, not even "just this once".
* It is NOT exercised in our demo (we had no credentials), so treat it as
  scaffolding: it exists so a school with connectivity and an ULCA key gets
  better Santali TTS/ASR, and so the local pipeline is provably not the only
  possible backend thanks to the engine abstractions.
* Every outbound call is throttled by the same 25-req/min budget as the API.
"""

from __future__ import annotations

import base64
import time

import httpx

from ... import config
from ...ratelimit import OutboundThrottle
from ..base import EngineError, ModelUnavailable, Speech, Transcript, Translation

# Bhashini ULCA pipeline endpoint. Model IDs are per-account, configured via
# .env (see .env.example) because they come from the ULCA console.
PIPELINE_URL = "https://api.bhashini.cg.gov.in/services/inference/pipeline/v2"

_throttle = OutboundThrottle(config.RATE_LIMIT_PER_MIN)


class BhashiniProvider:
    name = "bhashini"

    def __init__(self, creds: dict | None = None):
        self.creds = creds or config.BHASHINI
        self.client = httpx.Client(timeout=20)

    def configured(self) -> bool:
        return bool(self.creds.get("api_key") and self.creds.get("user_id"))

    def available(self) -> bool:
        # Offline mode is absolute: even with credentials we stay dark.
        return self.configured() and not config.OFFLINE_MODE

    def _pipeline(self, service: str, payload: dict) -> dict:
        if not self.available():
            raise ModelUnavailable(
                "Bhashini online fallback disabled (no credentials, or offline mode)."
            )
        _throttle.wait_for_slot()
        headers = {
            "userID": self.creds["user_id"],
            "ulcaApiKey": self.creds["api_key"],
        }
        model_key = {
            "asr": "asr_model_id",
            "translation": "mt_model_id",
            "tts": "tts_model_id",
        }[service]
        model_id = self.creds.get(model_key, "")
        if not model_id:
            raise ModelUnavailable(
                f"Bhashini {service} model id not configured ({model_key})."
            )
        body = {"pipelineTasks": [{"taskType": service, "config": {"modelId": model_id}}],
                "inputData": payload}
        t0 = time.perf_counter()
        resp = self.client.post(PIPELINE_URL, json=body, headers=headers)
        if resp.status_code != 200:
            raise EngineError(f"Bhashini returned HTTP {resp.status_code}")
        data = resp.json()
        latency = time.perf_counter() - t0
        data["_latency_s"] = round(latency, 3)
        return data

    # -- engine-shaped methods -------------------------------------------

    def translate(self, text: str, src: str, tgt: str) -> Translation:
        codes = {"hi": "hi", "sat": "sat"}
        out = self._pipeline(
            "translation",
            {"input": [{"sourceValue": text}],
             "language": {"sourceLanguage": codes.get(src, src),
                          "targetLanguage": codes.get(tgt, tgt)}},
        )
        try:
            value = out["pipelineResponse"][0]["output"][0]["targetValue"]
        except (KeyError, IndexError) as e:
            raise EngineError(f"unexpected Bhashini response shape: {e}") from e
        return Translation(
            text=value, src=src, tgt=tgt,
            script="Ol Chiki" if tgt == "sat" else "Devanagari",
            latency_s=out["_latency_s"], engine=self.name, source="bhashini",
        )

    def transcribe(self, wav_bytes: bytes, lang: str) -> Transcript:
        audio_b64 = base64.b64encode(wav_bytes).decode()
        out = self._pipeline(
            "asr",
            {"audio": [{"audioContent": audio_b64}],
             "language": {"sourceLanguage": lang}},
        )
        try:
            value = out["pipelineResponse"][0]["output"][0]["source"]
        except (KeyError, IndexError) as e:
            raise EngineError(f"unexpected Bhashini response shape: {e}") from e
        return Transcript(text=value, lang=lang,
                           latency_s=out["_latency_s"], engine=self.name)

    def synthesize(self, text: str, lang: str) -> Speech:
        out = self._pipeline(
            "tts",
            {"input": [{"source": text}], "language": {"sourceLanguage": lang}},
        )
        try:
            audio_b64 = out["pipelineResponse"][0]["audio"][0]["audioContent"]
        except (KeyError, IndexError) as e:
            raise EngineError(f"unexpected Bhashini response shape: {e}") from e
        wav = base64.b64decode(audio_b64)
        return Speech(wav_bytes=wav, sample_rate=22050,
                      latency_s=out["_latency_s"], engine=self.name, voice="bhashini")


_instance: BhashiniProvider | None = None


def provider() -> BhashiniProvider:
    global _instance
    if _instance is None:
        _instance = BhashiniProvider()
    return _instance
