#!/usr/bin/env bash
# Build Ogre Battle 64's D3D9 port without putting ROM-derived files on GitHub.
# Usage: dx9/build-offline.sh /path/to/owned/ogre64-rev-a.z64
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROM="${1:-}"
if [ -z "$ROM" ] || [ ! -f "$ROM" ]; then
    echo "usage: $0 /path/to/Ogre-Battle-64-USA-Rev-A.z64" >&2
    exit 2
fi

cd "$ROOT"
source tools/dx9-offline-env.sh

# The Makefile deliberately calls tools/venv/bin/splat, so keep the offline
# Python environment at that exact path. The wheelhouse was produced with the
# same Python major/minor as the container-side build (3.13).
if [ ! -x tools/venv/bin/splat ]; then
    rm -rf tools/venv
    python3 -m venv tools/venv
    tools/venv/bin/python -m pip install --no-index \
        --find-links "$ROOT/tools/offline-wheelhouse" 'splat64[mips]'
fi

mkdir -p assets
cp -f "$ROM" assets/ogre64.z64

# The project documents this order as load-bearing: split/link, banks, main
# recomp (with bank dispatch), then RSP njpeg/audio microcode.
make regenerate

test -d RecompiledFuncs
test -n "$(find RecompiledFuncs -type f -print -quit)"
test -f app/src/bank_funcs.inc
test -n "$(find . -maxdepth 1 -type d -name 'Bank*Funcs' -print -quit)"
test -n "$(find RspFuncs -type f -print -quit)"

BUILD="$ROOT/build-dx9-offline"
cmake -S app -B "$BUILD" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$ROOT/dx9/llvm-mingw-x86_64.cmake" \
    -DCMAKE_BUILD_TYPE=Release \
    -DOGRE_USE_RT64=OFF \
    -DOGRE_USE_DX9=ON \
    -DOGRE_STATIC_SDL2=ON
cmake --build "$BUILD" --target ogrebattle64 -j 2

test -f "$BUILD/ogrebattle64.exe"

# Shader Model 3 bytecode is intentionally precompiled on a Windows SDK runner.
# If the toolchain kit/user placed it under tools/, make the runnable pair now.
if [ -f tools/dx9_rdp_ps.cso ]; then
    cp -f tools/dx9_rdp_ps.cso "$BUILD/dx9_rdp_ps.cso"
fi

mkdir -p "$ROOT/dist-dx9"
cp -f "$BUILD/ogrebattle64.exe" "$ROOT/dist-dx9/OgreBattle64-DX9.exe"
if [ -f "$BUILD/dx9_rdp_ps.cso" ]; then
    cp -f "$BUILD/dx9_rdp_ps.cso" "$ROOT/dist-dx9/dx9_rdp_ps.cso"
fi

echo "DX9 build complete: $ROOT/dist-dx9/OgreBattle64-DX9.exe"
