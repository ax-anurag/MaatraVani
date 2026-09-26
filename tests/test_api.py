"""HTTP API tests - the contract the frontend actually depends on.

These hit the real FastAPI app through a TestClient, so the route wiring,
form parsing, refusal semantics and engine responses are exercised exactly
as the browser would see them.

Budget note: the app caps /api/* at 25 requests per minute GLOBALLY (that
cap is the project's own constraint and is unit-tested in test_ratelimit).
This file therefore spends ~12 calls, clears the window before it starts,
and does not try to reproduce the 429 path end-to-end - starving the rest
of the suite out of its own API would prove nothing the limiter tests have
not already proven.
"""

import base64

import pytest
from fastapi.testclient import TestClient

from backend import config, main
from conftest import requires_espeak, requires_nllb


@pytest.fixture(scope="module")
def client():
    # Fresh 60 s window for this module - a previous run must not leave us
    # already throttled. (Private attr, but this is exactly what it is for.)
    main.API_LIMITER._hits.clear()
    with TestClient(main.app) as c:
        yield c


# ------------------------------------------------------------- read-only ---

def test_frontend_served_by_same_process(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_status_shape_is_honest(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert body["app"] == "maatravani"
    assert body["rate_limit"] == config.RATE_LIMIT_PER_MIN
    assert "engines" in body and "mesh" in body
    # the transport always labels itself, never claims a radio
    assert "SIMULATION" in body["mesh"]["active_transport"]["label"].upper()


def test_language_registry(client):
    langs = client.get("/api/languages").json()
    assert langs["hi"]["status"] == "available"
    assert langs["sat"]["status"] == "available"
    assert langs["hoc"]["status"] == "planned"
    assert langs["muq"]["status"] == "planned"


def test_materials_catalog(client):
    cat = client.get("/api/materials/catalog").json()
    assert cat["grades"] == ["1", "2", "3"]
    assert "Foundational Literacy" in cat["subjects"]
    assert cat["card_counts"] == [1, 4, 8]
    assert cat["outcomes"], "FLN outcomes must be loaded for the generator"


# ------------------------------------------------------------- refusals ---

def test_planned_language_is_refused_400(client):
    """Ho/Mundari: rejected as not implemented, never silently attempted."""
    r = client.post("/api/voice/translate-text",
                    data={"text": "नमस्ते", "src": "hi", "tgt": "hoc"})
    assert r.status_code == 400
    assert "planned" in r.json()["detail"]


def test_unknown_language_code_refused(client):
    r = client.post("/api/voice/translate-text",
                    data={"text": "नमस्ते", "src": "hi", "tgt": "xx"})
    assert r.status_code == 400


# ----------------------------------------------------------------- mesh ---

def test_mesh_send_and_two_hop_inbox(client):
    client.post("/api/mesh/reset")
    r = client.post("/api/mesh/send", data={
        "sender_id": "teacher", "type": "ANNOUNCEMENT", "language": "hi",
        "title": "homework", "text": "कल गणित की कॉपी साथ लाईये।", "ttl": "5",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["message"]["hop_count"] == 0
    delivered = [e for e in body["events"] if e["event"] == "delivered"]
    assert any(e["to_node"] == "student-b" and e["hop_count"] == 2
               for e in delivered), "the 2-hop relay is the demo's point"

    inbox = client.get("/api/mesh/inbox", params={"node": "student-b"}).json()
    assert inbox["messages"][0]["label"] == "Received via mesh - 2 hops"
    assert inbox["messages"][0]["received_hop_count"] == 2


def test_mesh_rejects_unknown_type(client):
    r = client.post("/api/mesh/send",
                    data={"sender_id": "teacher", "type": "SPAM", "text": "x"})
    assert r.status_code == 400


# ------------------------------------------------- engine-backed routes ---

@requires_nllb
def test_translate_text_endpoint(client):
    r = client.post("/api/voice/translate-text",
                    data={"text": "नमस्ते बच्चों।", "src": "hi", "tgt": "sat"})
    assert r.status_code == 200
    body = r.json()
    assert body["text"], "empty translation"
    assert body["script"] == "Ol Chiki"
    assert body["latency"]["translation"] >= 0.0
    assert body["review_warning"], "machine output must be flagged"


@requires_nllb
def test_lesson_endpoint_associates_outcome(client):
    r = client.post("/api/materials/lesson", data={
        "grade": "2", "subject": "Foundational Literacy", "topic": "Animals",
    })
    assert r.status_code == 200
    lesson = r.json()
    assert lesson["outcome_id"], "FLN outcome must be linked to the lesson"
    assert lesson["script"], "bilingual script lines missing"
    # the animals category is verified in the shipped lexicon
    assert lesson["vocabulary"], "animals vocabulary expected from the lexicon"


@requires_nllb
def test_flashcards_endpoint(client):
    r = client.post("/api/materials/flashcards",
                    data={"topic": "Animals", "count": "4"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 4
    for c in body["cards"]:
        assert c["svg"].startswith("<svg"), "cards must carry their SVG"


@requires_espeak
def test_tts_endpoint_returns_real_wav(client, autonym):
    from backend.engines.tts.espeak import EspeakEngine
    if not EspeakEngine().language_available("sat"):
        pytest.skip("espeak-ng on this machine has no 'sat' voice")
    r = client.post("/api/voice/tts", data={"text": autonym, "lang": "sat"})
    assert r.status_code == 200
    wav = base64.b64decode(r.json()["audio_b64"])
    assert wav[:4] == b"RIFF", "TTS response must be a genuine WAV"
