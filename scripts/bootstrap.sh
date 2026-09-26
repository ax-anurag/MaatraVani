#!/usr/bin/env bash
# Bootstrap the Python environment without sudo.
#
# The dev box's system Python has no ensurepip/pip and is too new for some
# of our pins, so we install uv (a single static binary, no root needed),
# create a 3.11 venv with it, and install requirements.
#
# Why exactly 3.11: faster-whisper resolves tokenizers 0.13.3, which ships
# prebuilt wheels only up to cp311. On 3.12+ it tries a Rust source build
# instead (which this box has no compiler for). Every other pin has wheels
# for 3.11 too, so 3.11 is the intersection that installs clean.
set -euo pipefail
cd "$(dirname "$0")/.."

UV="$HOME/.local/bin/uv"

if [ ! -x "$UV" ]; then
    echo "==> installing uv to ~/.local/bin (no sudo, from the GitHub release tarball)"
    mkdir -p "$HOME/.local/bin" /tmp/uv-extract
    wget -q "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz" \
        -O /tmp/uv.tar.gz
    tar -xzf /tmp/uv.tar.gz -C /tmp/uv-extract
    cp /tmp/uv-extract/uv-x86_64-unknown-linux-gnu/uv "$UV"
    rm -rf /tmp/uv.tar.gz /tmp/uv-extract
fi
"$UV" --version

# The venv must be exactly 3.11: faster-whisper's tokenizers 0.13.3 has no
# wheels for newer Pythons and would try a Rust source build instead. So
# we check the version, not just existence - a leftover 3.14 venv is
# exactly the trap we hit once.
VENV_OK=0
if [ -x ".venv/bin/python" ]; then
    ".venv/bin/python" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)" \
        && VENV_OK=1
fi
if [ "$VENV_OK" -ne 1 ]; then
    echo "==> creating .venv (Python 3.11)"
    rm -rf .venv
    "$UV" venv --python 3.11 .venv
fi

echo "==> installing requirements"
"$UV" pip install -r requirements.txt --python .venv/bin/python

echo "==> next steps:"
echo "    sudo apt-get install -y espeak-ng   # Santali TTS (system package)"
echo "    .venv/bin/python scripts/download_models.py   # one-time, online"
echo "    ./scripts/run_dev.sh"
