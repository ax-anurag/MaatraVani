#!/usr/bin/env bash
# One-shot setup: espeak-ng (no-sudo), models + fonts, demo audio, tests,
# and the offline demonstration - in that order, with everything the app
# needs to run with the network unplugged afterwards.
#
# Every phase is idempotent, and a phase that fails does not stop the
# later ones (a missing espeak should not prevent the model download,
# and so on). Run it from anywhere:
#
#     bash scripts/setup_all.sh
#
# First run needs internet (model download); later runs verify offline
# behaviour without re-downloading anything.

set -uo pipefail   # deliberately no -e, see above
cd "$(dirname "$0")/.."

if [ ! -x ".venv/bin/python" ]; then
    echo "no .venv found - run ./scripts/bootstrap.sh first" >&2
    exit 1
fi

echo "=== PHASE 1: espeak-ng into ~/.local/espeak-root (no sudo) ==="
bash scripts/install_espeak_nosudo.sh || echo "[warn] espeak install failed"

# the home prefix only works with these three exports; run_dev.sh does
# the same wiring for the app itself (libpulsecommon lives in the
# pulseaudio/ subdirectory - the loader does not search subdirs itself)
export PATH="$HOME/.local/espeak-root/usr/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/.local/espeak-root/usr/lib/x86_64-linux-gnu:$HOME/.local/espeak-root/usr/lib/x86_64-linux-gnu/pulseaudio${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ESPEAK_DATA_PATH="$HOME/.local/espeak-root/usr/lib/x86_64-linux-gnu/espeak-ng-data"

echo "=== PHASE 2: one-time model + font download (~1.2 GB) ==="
.venv/bin/python scripts/download_models.py --probe || echo "[warn] model download failed"

echo "=== PHASE 3: demo audio (synthetic Hindi WAVs) ==="
.venv/bin/python scripts/make_demo_audio.py || echo "[warn] demo audio failed"

echo "=== PHASE 4: full test suite ==="
.venv/bin/python -m pytest tests/ -v 2>&1 | tail -80 || echo "[warn] pytest reported failures"

echo "=== PHASE 5: offline demonstration (network blocked in-process) ==="
.venv/bin/python scripts/offline_demo.py || echo "[warn] offline demo reported failures"

echo "=== ALL PHASES ATTEMPTED - server ready via ./scripts/run_dev.sh ==="
