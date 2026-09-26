#!/usr/bin/env bash
# Start the MaatraVani dev server.
#
#   ./scripts/run_dev.sh             # normal mode (online fallback allowed if configured)
#   ./scripts/run_dev.sh --offline   # hard offline mode: no network egress, ever
#
# One API, one port, one process: the frontend is served by the same uvicorn.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "${1:-}" == "--offline" ]]; then
  export MATR_OFFLINE=1
  echo "[run_dev] OFFLINE MODE - all network egress disabled"
fi

HOST="${MATR_HOST:-127.0.0.1}"
PORT="${MATR_PORT:-8000}"

# espeak-ng extracted into the home dir (scripts/install_espeak_nosudo.sh)
# needs its library and voice data on the environment - a system package
# registers those itself and this block simply does nothing.
if [[ -x "$HOME/.local/espeak-root/usr/bin/espeak-ng" ]]; then
  export PATH="$HOME/.local/espeak-root/usr/bin:$PATH"
  # pulseaudio/ subdir holds libpulsecommon-17.0.so - the loader does not
  # search LD_LIBRARY_PATH subdirectories, so it must be named explicitly
  export LD_LIBRARY_PATH="$HOME/.local/espeak-root/usr/lib/x86_64-linux-gnu:$HOME/.local/espeak-root/usr/lib/x86_64-linux-gnu/pulseaudio${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  export ESPEAK_DATA_PATH="$HOME/.local/espeak-root/usr/lib/x86_64-linux-gnu/espeak-ng-data"
fi

if [[ -x .venv/bin/uvicorn ]]; then
  exec .venv/bin/uvicorn backend.main:app --host "$HOST" --port "$PORT"
else
  echo "[run_dev] no .venv found - create it first (see README.md: Installation)"
  exit 1
fi
