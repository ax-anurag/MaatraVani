# MaatraVani
# MAATRAVANI  **"Breaking language and connectivity barriers in education."**  A functional proof of concept for primary-school classrooms in underserved and tribal regions: a Hindi-speaking teacher can teach Santali-speaking children — speak to them, generate mother-tongue learning material, and relay school information between devices .
# MAATRAVANI

**"Breaking language and connectivity barriers in education."**

A functional proof of concept for primary-school classrooms in underserved
and tribal regions: a Hindi-speaking teacher can teach Santali-speaking
children — speak to them, generate mother-tongue learning material, and
relay school information between devices — with **no internet at runtime**.


## Modules

| module | what it does |
|--------|---------------|
| Voice Translator | Hindi speech to Hindi text to Santali (Ol Chiki) to Santali audio, fully local; text mode both directions |
| Study Materials | bilingual FLN/NIPUN-aligned lessons, printable worksheets, visual flashcards — generated locally |
| Offline Mesh | lesson/homework/notice relay between classroom devices with TTL, hop counts and duplicate suppression |

## Requirements

* Linux (developed and tested on WSL2, Ubuntu); any modern distro works
* Python **3.11** (a `.venv` is created for you — the system Python does
  not need to match; 3.11 specifically because some pins ship no wheels
  for newer Pythons)
* `espeak-ng` for speech output. Upstream espeak-ng has **no Santali
  voice** — Santali is spoken through the labelled Ol Chiki → Devanagari
  transliteration (`backend/engines/tts/sat_translit.py`) read by the
  Hindi voice. With sudo: `sudo apt-get install -y espeak-ng`; without:
  `scripts/install_espeak_nosudo.sh` (run by `setup_all.sh`) unpacks the
  distro debs into `~/.local/espeak-root`.
* ~1.2 GB disk for the models after setup (the one-time download is
  larger — the fp32 translation weights are ~2.5 GB before conversion —
  and a few GB RAM free; runs on modest hardware)

## Installation

```bash
# Everything below in one shot (also runs the test suite and offline demo):
bash scripts/setup_all.sh

# --- or step by step ---

# 1. Python environment (uv bootstraps a 3.11 venv, no sudo needed)
./scripts/bootstrap.sh          # or see below for the manual steps

# 2. Santali (and Hindi) speech — the only system package
sudo apt-get install -y espeak-ng
#    (no sudo on the machine? scripts/install_espeak_nosudo.sh unpacks the
#     distro debs into ~/.local/espeak-root and scripts/run_dev.sh wires
#     up PATH / LD_LIBRARY_PATH / ESPEAK_DATA_PATH automatically)

# 3. One-time model + font download (internet needed HERE ONLY)
.venv/bin/python scripts/download_models.py

# 4. Content files (lexicon/outcomes/demo sentences) — already emitted;
#    re-run only if you edit content/seed.py
.venv/bin/python scripts/emit_content.py
```

Manual venv steps, if you prefer no helper script:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # or download the tarball
uv venv --python 3.11 .venv
uv pip install -r requirements.txt --python .venv/bin/python
```

## Running

```bash
./scripts/run_dev.sh            # serves frontend + API on http://localhost:8000
./scripts/run_dev.sh --offline  # same, but MATR_OFFLINE=1: cloud fallback is off
```

Open http://localhost:8000 in a browser. The status pill shows what you
are on: `ONLINE`, `OFFLINE - LOCAL MODELS ACTIVE`, or `BACKEND UNREACHABLE`.

**Microphone note:** 
device, but the *browser* on the Windows side does — recording works fine
against the WSL-served page. For automated tests without a mic, see
`scripts/make_demo_audio.py` (synthesized Hindi WAVs; recognition quality
on synthetic speech is a lower bound, not a benchmark).

## Offline operation — what works with the cable pulled

Everything below was verified by `scripts/offline_demo.py`, which
monkeypatches sockets so that *any* network attempt crashes the run:

* Hindi speech recognition (Vosk / faster-whisper)
* Hindi to Santali translation (verified lexicon then NLLB, both local)
* Santali text display in Ol Chiki
* Santali speech synthesis (espeak-ng)
* lesson / worksheet / flashcard generation (local fonts, local PDF)
* mesh message relay (simulation; native BLE needs a real adapter)
* the full measured-latency reporting

The **only** optional online feature is the Bhashini/ULCA fallback: hidden
without credentials, force-disabled in offline mode, throttled by the
same 25-req/min budget. See `.env.example`.

## Supported languages

| language | status |
|----------|--------|
| Hindi (`hi`) | implemented (ASR, translation source, TTS) |
| Santali (`sat`) | **primary target**: translation + Ol Chiki + TTS. Voice *input* is not available offline (no model exists) — reverse direction uses text mode, or Bhashini if configured |
| Ho (`hoc`) | Planned / Future Language — selectable in the UI, honestly refused by the engines |
| Mundari (`muq`) | Planned / Future Language — same |

## Performance

Latency is **measured, per stage, on every request** and shown in the UI.
Target: < 3 s voice-to-voice. Observed numbers on the dev machine are in
[DEMO.md](DEMO.md) — regenerated by re-running
`scripts/offline_demo.py`; nothing in this repo hard-codes them.

## Testing

```bash
.venv/bin/python -m pytest tests/ -v
```

The suite covers all CLAUDE.md acceptance categories: translation both
ways, ASR, Santali TTS, full pipeline + latency, offline operation
(sockets dead), lesson/worksheet/flashcard generation, mesh relay,
duplicate rejection, TTL expiry, rate-limit enforcement, the HTTP API
contract the frontend calls, and script integrity (no fake or corrupted
Ol Chiki anywhere in the repo). Tests that need a missing model/binary
**skip with the exact reason** — a skip never means "works".

## Project layout

```
backend/
  api/            HTTP + WebSocket routes
  engines/        ASR / translation / TTS abstractions + local engines
    providers/    optional Bhashini cloud fallback
  curriculum/     lesson generator, worksheet + flashcard renderers
  mesh/           message format, simulation, BLE transport, manager
  services/       pipeline orchestration with per-stage latency
  main.py         app assembly + rate-limit middleware
frontend/         vanilla ES modules, no build step, local fonts
content/          seed.py -> vocabulary/lessons/demo JSON (the single source of truth)
scripts/          download_models, make_demo_audio, offline_demo, ...
tests/            pytest suite (12 acceptance categories)
```


## Limitations (stated, not hidden)

* **No offline Santali ASR exists today.** Reverse voice direction errors
  explicitly instead of pretending.
* **Santali TTS is transliteration, not a native voice.** No offline
  Santali TTS exists anywhere — upstream espeak-ng has no `sat` voice.
  The app maps the Ol Chiki text letter-by-letter to Devanagari and reads
  it with the espeak-ng Hindi voice: the real Santali words with Hindi
  phonology, labelled "hi (Santali transliteration)" in the UI. If
  espeak-ng is missing the app says "Santali TTS unavailable" rather than
  playing other-language audio. A production build should integrate a
  neural Santali TTS as soon as one exists.
* **NLLB did not produce usable Santali here.** NLLB-200's only Santali
  code is `sat_Beng` (Bengali script — there is no Ol Chiki variant), and
  the distilled-600M build we converted emitted unrelated languages for
  `sat_Beng` targets on this hardware. So demo sentences are served by the
  **verified lexicon**: exact matches return the verified translation;
  other sentences get a word-by-word gloss built only from verified
  words (unknown words stay visible in Hindi, the line is labelled
  "word gloss (partial)" and carries the review warning). NLLB still
  answers for hi↔hi-adjacent use and its output is never hidden — when
  it misses the target script the gloss takes over.
* **NLLB translation quality varies**; every machine-generated line ships
  with "Please review before classroom use", and the verified lexicon
  takes precedence where it has entries.
* **NLLB weights are CC-BY-NC-4.0** — fine for this educational PoC, a
  licensing constraint for commercial deployment (swap point:
  `TranslationEngine`).
* **Native BLE is best-effort**: the demo machine has no Bluetooth
  adapter, so the mesh defaults to the clearly-labelled simulation; the
  `MeshTransport` interface keeps a real radio swap local.
* The FLN outcome catalog is a **representative, reworded subset** for
  the PoC, not an official NIPUN Bharat document.
