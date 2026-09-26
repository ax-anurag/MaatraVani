# MaatraVani — Architecture

One teacher who speaks Hindi can teach Santali-speaking children, generate
mother-tongue learning materials, and communicate educational information
even when internet connectivity is poor.

Three backbone modules, one process, zero cloud dependencies at runtime:

```
                             MAATRAVANI
                                 |
                +----------------+----------------+
                |                |                |
                v                v                v
        VOICE TRANSLATION   STUDY MATERIALS   OFFLINE MESH
        Hindi <-> Santali   Bilingual FLN     Bluetooth/BLE
        (flagship)          lessons, work-    relay (simulation
                             sheets, flash-   by default, native
                             cards            BLE behind the same
                                               interface)
```

## The voice pipeline (Module 1)

```
 Teacher speaks Hindi
        |
        |  browser: getUserMedia -> 16 kHz mono 16-bit WAV
        |  (encoded client-side, one POST per utterance)
        v
 POST /api/voice/translate
        |
        v
 [1] ASR ............. Vosk small-hi (fast) or faster-whisper small
        |               both local; engine picked by `asr.best_for()`
        v
 [2] Translation ...... 1. verified classroom lexicon (exact match)
        |               2. NLLB-200-distilled-600M via CTranslate2 (int8, CPU)
        |               3. never invented - a miss is a miss
        v
 [3] TTS .............. espeak-ng `hi` voice reading the Ol Chiki text via
        |               a letter-by-letter Devanagari transliteration
        |               (no offline Santali TTS exists anywhere; the UI
        |               labels the voice "hi (Santali transliteration)")
        v
 Student hears Santali (WAV returned as base64, played in the browser)
```

Every stage reports its **own measured latency**; the UI shows those
numbers, not a promise. Target: < 3 s end to end. Observed values live in
DEMO.md and are re-measured by `scripts/offline_demo.py`.

Reverse direction (Santali voice in): **there is no offline Santali ASR
model today.** The pipeline therefore reports an explicit error for that
direction unless the optional, credentials-gated Bhashini provider is
configured. It never fakes a transcript.

## Study materials (Module 2)

```
 Teacher picks: grade / subject / topic / FLN outcome / language
        |
        v
 outcome catalog (content/lessons/fln_outcomes.json,
                  representative NIPUN Bharat FLN subset)
        |
        v
 template-driven lesson builder (backend/curriculum/generator.py)
   - opening, vocabulary sentences, activity, assessment
   - every Hindi line goes through the SAME lexicon->NLLB chain
   - vocabulary comes from the verified lexicon when the category exists
        |
        +--> lesson JSON (bi-line: {hi, sat, verified})
        |
        +--> worksheet PDF  (fpdf2 + uharfbuzz text shaping, local fonts)
        +--> flashcards      (SVG on screen; fpdf2 PDF for print)
```

PDFs are rendered locally with real text shaping — Devanagari conjuncts
and Ol Chiki both need HarfBuzz; glyph-by-glyph PDF libraries render them
wrong. Fonts (Noto Sans Ol Chiki / Devanagari) ship in `frontend/fonts/`
after a one-time download.

Every machine-translated line carries:
> Machine-generated translation. Please review before classroom use.

## Offline mesh (Module 3)

```
 Teacher Device ──Bluetooth──> Student Device A ──Bluetooth──> Student Device B
     (origin)                    (hop 1, relays)                 (hop 2)
```

Message format (`backend/mesh/message.py`):

```
Message {
    id          uuid4 - duplicate detection key
    sender_id   teacher | student-a | student-b
    timestamp   ISO-8601
    ttl         starts at 5, -1 per relay, dies at 0
    hop_count   +1 per relay, shown as "Received via mesh - N hops"
    type        LESSON | WORKSHEET | ANNOUNCEMENT | CLASSROOM_MESSAGE | ALERT
    language    hi | sat | ...
    payload     {title, text, ...}
    path        [teacher, student-a, student-b]
}
```

Relay rules, enforced in both transports and covered by tests:

* a node relays only if `ttl > 0` and it has not seen the id;
* every relay costs 1 TTL and adds 1 hop;
* duplicates are suppressed and surface as `duplicate` events;
* TTL exhaustion surfaces as `ttl_expired` events.

Transport abstraction (`backend/mesh/transport.py`):

| implementation        | what it is                                                       |
|-----------------------|------------------------------------------------------------------|
| `LocalMeshSimulation` | in-process deterministic flood over the classroom topology       |
| `BleakMeshTransport`  | real BLE via bleak (guarded import; needs an actual BT adapter)  |

The simulation is the default and the UI labels it
**DEMO / SIMULATION MODE — no radio hardware involved.** Nobody ever
claims a simulated hop was a radio hop. The manager, message format,
TTL/duplicate rules and events are identical for both transports, so the
simulation can be swapped for real BLE without touching the API layer.

## Engine abstractions

`backend/engines/base.py` defines the three contracts; concrete engines
implement them:

```
ASREngine           TranslationEngine          TTSEngine
  VoskEngine          LexiconEngine               EspeakEngine
  WhisperEngine       NllbEngine (CT2)            (bhashini provider
                      (bhashini provider            when configured)
                       when configured)
```

Selection is by availability, at runtime, per call:

* `asr.best_for(lang)` - first available engine that supports the language
* `translation` - composite `ClassroomTranslationEngine`: lexicon first,
  NLLB second, nothing third
* `tts.best_for(lang)` - espeak-ng; refuses with a clear error if the
  binary or the `sat` voice is missing

The optional Bhashini cloud provider implements the same shapes and is
**invisible and disabled** unless credentials exist in the environment —
and is force-disabled in offline mode, which is enforced by test.

## Offline-first

```
 INTERNET AVAILABLE (once)
      |
      |  scripts/download_models.py
      |    - Noto fonts (Ol Chiki, Devanagari)
      |    - NLLB-200-distilled-600M (CTranslate2 int8)
      |    - faster-whisper small
      |    - Vosk small Hindi
      v
 LOCAL MODEL STORE  (models/)
      |
      v
 OFFLINE MODE  - everything below runs with sockets dead:
      ASR      translation      TTS
      lessons  worksheets  flashcards
      mesh simulation / BLE
```

`scripts/offline_demo.py` monkeypatches `socket.connect` to raise, then
runs the whole feature set — if any component had tried the network, the
demo would crash rather than pass.

## API surface and the 25 req/min budget

A global sliding-window limiter (`backend/ratelimit.py`) caps **all**
`/api/*` requests combined at 25 per rolling 60 seconds (configurable via
`MATR_RATE_LIMIT`). Static files are deliberately uncapped. The same
primitive throttles any outbound provider call, so the app can never
hammer an external API either. The frontend is built for the budget: no
polling, one request per voice utterance, catalog responses cached in the
session, mesh events arrive over a WebSocket (outside `/api/*`).

```
GET  /api/status                     engine/mesh/limit snapshot
GET  /api/languages                  language registry incl. planned ones
POST /api/voice/translate            audio -> transcript+translation+speech
POST /api/voice/translate-text      text mode (same chain, speak optional)
POST /api/voice/tts                  replay TTS
GET  /api/materials/catalog          grades/subjects/topics/outcomes
POST /api/materials/lesson           bilingual lesson JSON
POST /api/materials/worksheet        PDF (also saved under generated/)
POST /api/materials/flashcards       SVG cards JSON
POST /api/materials/flashcards/pdf   PDF (also saved under generated/)
GET  /api/mesh/status|nodes|inbox|events
POST /api/mesh/send | /api/mesh/reset
WS   /ws/mesh                        live relay events
```

## Frontend

Vanilla ES modules served statically by the same FastAPI process — no
build step, no framework, no CDN (fonts ship locally). Hash router with
four pages (dashboard, voice, materials, mesh). The browser records and
encodes WAV client-side, so the backend needs no audio toolchain.

## Honest limitations (by design, visible in the UI)

| limitation                          | how the system behaves                          |
|-------------------------------------|-------------------------------------------------|
| no offline Santali ASR exists        | reverse voice direction errors explicitly       |
| no offline Santali TTS exists at all | Ol Chiki → Devanagari transliteration read by the espeak-ng `hi` voice, labelled in the UI; if espeak-ng is missing, explicit "unavailable" |
| Ho / Mundari not implemented         | selectable but marked "Planned / Future Language"|
| WSL2 demo box has no BT adapter      | simulation is default, clearly banner-labelled   |
| machine translation quality varies   | review warning on every machine-generated line   |
