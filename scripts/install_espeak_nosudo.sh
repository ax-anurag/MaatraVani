#!/usr/bin/env bash
# Install espeak-ng WITHOUT root, by downloading the distro's own .deb
# packages and extracting them into $HOME/.local/espeak-root.
#
# Why this exists: the demo box has no sudo access, but the app's speech
# output is espeak-ng all the way down - the Hindi voice for demo audio and
# Hindi TTS, and Santali via our transliteration fallback read through that
# same voice (there is no offline Santali TTS anywhere; see
# backend/engines/tts/sat_translit.py). apt-get download and dpkg-deb -x are
# plain userland tools, so the packages can be unpacked into a home prefix
# instead of /usr.
# scripts/run_dev.sh picks the prefix up automatically and exports
# PATH / LD_LIBRARY_PATH / ESPEAK_DATA_PATH for it.
#
# A system package installed with sudo (the normal route, see README)
# makes this script unnecessary - it is the no-root fallback only.
set -euo pipefail

ROOT="$HOME/.local/espeak-root"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "==> downloading espeak-ng debs (no install, just download)"
cd "$WORK"
# The binary's full link chain, discovered the hard way on the demo box:
# espeak-ng needs libespeak-ng1 (which needs libsonic0 and libpcaudio0),
# and even when only writing WAV files the loader insists on the whole
# audio shim - libasound2, plus libpulse0 (libpulse-simple.so.0 lives
# there; it in turn wants libdbus-1-3 and libglib2.0-0). Package names
# shifted after the 64-bit time_t transition (*t64), so each candidate
# list takes whichever spelling this distro uses.
apt-get download espeak-ng espeak-ng-data libespeak-ng1 libsonic0 libpcaudio0
for candidates in "libasound2t64 libasound2" "libpulse0t64 libpulse0" \
                  "libglib2.0-0t64 libglib2.0-0" "libpcre2-8-0" "libffi8" \
                  "libsndfile1" "libvorbis0a" "libvorbisenc2" "libogg0" \
                  "libopus0" "libmp3lame0" "libasyncns0" \
                  "libmpg123-0t64 libmpg123-0" \
                  "libflac14t64 libflac14 libflac12t64 libflac12"; do
    got=0
    for name in $candidates; do
        if apt-get download "$name" 2>/dev/null; then got=1; break; fi
    done
    [[ $got -eq 1 ]] || echo "  [warn] none of '$candidates' in the archive - relying on the system copy" >&2
done

echo "==> extracting into $ROOT"
mkdir -p "$ROOT"
for deb in *.deb; do
    dpkg-deb -x "$deb" "$ROOT"
done

BIN="$ROOT/usr/bin/espeak-ng"
if [[ ! -x "$BIN" ]]; then
    echo "extraction failed - no espeak-ng binary at $BIN" >&2
    exit 1
fi

LIBDIR="$ROOT/usr/lib/x86_64-linux-gnu"
# libpulsecommon-17.0.so ships inside a pulseaudio/ subdirectory of the
# libdir, and the dynamic loader does not search LD_LIBRARY_PATH
# subdirectories - without naming it explicitly every espeak-ng run dies
# with "libpulsecommon-17.0.so: cannot open shared object file".
export LD_LIBRARY_PATH="$LIBDIR:$LIBDIR/pulseaudio${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ESPEAK_DATA_PATH="$LIBDIR/espeak-ng-data"

# Close the loop before declaring victory: every library in the prefix
# (and the binary itself) must resolve. This check is what caught each
# missing link in the chain during development, and it keeps the script
# honest on distros that name or ship things differently. Note the
# pulseaudio/ glob - a lib hiding in a subdir is still a NEEDED entry
# that must resolve.
echo "==> library self-check"
MISSING="$( { ldd "$BIN"; for f in "$LIBDIR"/lib*.so* "$LIBDIR"/pulseaudio/lib*.so*; do ldd "$f"; done; } 2>/dev/null \
             | grep "not found" | sort -u || true)"
if [[ -n "$MISSING" ]]; then
    echo "  these libraries are still missing:" >&2
    echo "$MISSING" >&2
    exit 1
fi

# Santali needs no voice files here: the app reads Santali through the
# labelled Ol Chiki -> Devanagari transliteration
# (backend/engines/tts/sat_translit.py) on the Hindi voice installed above.

echo "==> voice check"
"$BIN" --voices | awk 'NR==1 || $2 ~ /^hi$/'
if ! "$BIN" --voices | awk '{print $2}' | grep -qx "hi"; then
    echo "Hindi voice 'hi' missing after install - Santali audio (transliteration) rides on it" >&2
    exit 1
fi
# and actually speak, so a silent-voice regression cannot slip through
TMPWAV="$(mktemp --suffix=.wav)"
"$BIN" -v hi -s 140 -w "$TMPWAV" "नमस्ते बच्चों"
[[ $(stat -c%s "$TMPWAV") -gt 200 ]] || { echo "Hindi voice produced silent audio" >&2; rm -f "$TMPWAV"; exit 1; }
if "$BIN" --voices | awk '{print $2}' | grep -qx "sat"; then
    "$BIN" -v sat -s 140 -w "$TMPWAV" "ᱥᱟᱱᱛᱟᱲᱤ"
    [[ $(stat -c%s "$TMPWAV") -gt 200 ]] || { echo "sat voice produced silent audio" >&2; rm -f "$TMPWAV"; exit 1; }
fi
rm -f "$TMPWAV"

cat <<EOF

done. espeak-ng lives in $ROOT (no root was used).
scripts/run_dev.sh exports it for the app automatically.
EOF
