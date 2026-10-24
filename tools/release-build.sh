#!/usr/bin/env bash
# Build a distributable package for this machine's platform (or DIST_OS).
#
# This is the one path CI and a developer both use, so the release artifacts are
# exactly what `make dist` produces locally.
#
#   tools/release-build.sh                    # host platform
#   DIST_OS=linux tools/release-build.sh      # explicit (CI passes this)
#   DIST_STATIC_SDL=0 tools/release-build.sh  # bundle the shared SDL2 instead
#
# Output: dist/ogre-battle-64-recomp/ plus dist/ogre-battle-64-recomp-<os>.tar.gz
# and/or .zip.
#
# It refuses to run when the generated game code or the example mods are
# missing, because on a fresh clone they always are: RecompiledFuncs/,
# Bank*Funcs/, RspFuncs/ and app/src/bank_funcs.inc are gitignored and are
# produced by a recompilation that needs a ROM, and build/mods/*.nrm is
# `make example-mods` output. See docs/guides/app-build.md.
set -euo pipefail

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

# --- what platform are we packaging? ----------------------------------------
if [ -z "${DIST_OS:-}" ]; then
    case "$(uname -s)" in
        Darwin) DIST_OS=macos ;;
        Linux)  DIST_OS=linux ;;
        MINGW*|MSYS*|CYGWIN*|Windows_NT) DIST_OS=windows ;;
        *) echo "release-build.sh: unknown platform $(uname -s); set DIST_OS" >&2; exit 2 ;;
    esac
fi
export DIST_OS

# --- the generated game code must be present --------------------------------
missing=""
[ -d RecompiledFuncs ] || missing="$missing RecompiledFuncs/"
[ -f app/src/bank_funcs.inc ] || missing="$missing app/src/bank_funcs.inc"
[ -d RspFuncs ] || missing="$missing RspFuncs/"
if [ -n "$missing" ]; then
    cat >&2 <<EOF
release-build.sh: the recompiled game code is missing:$missing

It is not in the repository (it is generated from the ROM and gitignored), so
this script cannot build without it. On a machine that has your ROM:

    tools/venv/bin/splat split config/config.yaml   # once, if asm/ assets/ are absent
    make && make recomp && make bank-recomp

Then run this script again. See docs/guides/app-build.md.
EOF
    exit 1
fi

# --- the example mods must be present ----------------------------------------
# The package's mods/ directory is filled from build/mods/*.nrm, and the README
# lists them as part of the package. `make dist` requires at least one, so fail
# here rather than at the end of the app build. On a hosted runner they arrive in
# files.tar.gz from tools/data-bundle.sh; on a developer's machine from
# `make example-mods`.
if ! ls build/mods/*.nrm >/dev/null 2>&1; then
    cat >&2 <<EOF
release-build.sh: no example mods in build/mods/.

The package must carry them, so they are a release input:

    make example-mods

A GitHub-hosted runner gets them from files.tar.gz, which tools/data-bundle.sh
writes; regenerate and commit that bundle. See docs/guides/app-build.md ->
"Releases (GitHub Actions)".
EOF
    exit 1
fi

# --- third-party trees ------------------------------------------------------
if [ ! -d tools/N64ModernRuntime ]; then
    echo "release-build.sh: tools/N64ModernRuntime is missing (git submodule / clone step)" >&2
    exit 1
fi
if [ ! -d tools/RT64/src ]; then
    echo "release-build.sh: tools/RT64 is missing (git submodule / clone step)" >&2
    exit 1
fi

# The RT64 SDL compatibility patch is needed on systems with SDL < 2.0.22 and is
# harmless elsewhere. Applying it twice fails, hence the `|| true`.
if [ -f tools/rt64-plume-sdl.patch ] && [ -d tools/RT64/src/contrib/plume ]; then
    git -C tools/RT64/src/contrib/plume apply ../../../../tools/rt64-plume-sdl.patch >/dev/null 2>&1 || true
fi

# --- the patches must describe the trees ------------------------------------
# A GitHub-hosted runner builds these trees by APPLYING the canonical project
# patches, so its trees match them by construction. The universal randomizer has
# one intentionally layered runtime patch that touches two files already present
# in n64modernruntime-ob64.patch. patchcheck.py compares each canonical patch to
# the complete worktree diff and deliberately does not model overlapping layered
# patches, so audit the canonical tree first, then compose the randomizer layer.
randomizer_runtime_patch="$root/patches/n64modernruntime-randomizer.patch"
randomizer_runtime_was_applied=0
if [ -f "$randomizer_runtime_patch" ]; then
    if ( cd tools/N64ModernRuntime && git apply --reverse --check "$randomizer_runtime_patch" ) >/dev/null 2>&1; then
        echo "==> temporarily removing universal-randomizer runtime layer for patch audit"
        ( cd tools/N64ModernRuntime && git apply --reverse "$randomizer_runtime_patch" )
        randomizer_runtime_was_applied=1
    fi
fi

# Always restore the layered patch if this script exits after the audit step.
restore_randomizer_runtime() {
    if [ "$randomizer_runtime_was_applied" = 1 ] && [ -f "$randomizer_runtime_patch" ]; then
        if ! ( cd tools/N64ModernRuntime && git apply --reverse --check "$randomizer_runtime_patch" ) >/dev/null 2>&1; then
            ( cd tools/N64ModernRuntime && git apply "$randomizer_runtime_patch" ) || true
        fi
    fi
}
trap restore_randomizer_runtime EXIT

# A developer builds from trees that carry uncommitted work, and a patch that
# has drifted from them ships old code with a green build: the hosted v0.5.0 and
# v0.5.1 releases carried neither the presented-frame capture fix nor the D3D12
# null-texture guard, because both live in the RT64 trees and the patch files
# were stale (session 116). Fail before packaging instead.
echo "==> checking that the tracked patches describe the vendored trees"
if ! python3 tools/patchcheck.py; then
    cat >&2 <<EOF

release-build.sh: a tracked patch no longer describes the tree it patches, so
the package would ship old code for it. Regenerate, review and commit:

    python3 tools/patchcheck.py --fix

See docs/guides/app-build.md -> "Third-party patches".
EOF
    exit 1
fi

# Compose the universal-randomizer runtime lookup only after the canonical patch
# audit has passed. This is idempotent for hosted and developer trees.
if [ -f "$randomizer_runtime_patch" ]; then
    if ( cd tools/N64ModernRuntime && git apply --reverse --check "$randomizer_runtime_patch" ) >/dev/null 2>&1; then
        echo "==> universal-randomizer runtime layer already applied"
    else
        echo "==> applying universal-randomizer runtime layer"
        ( cd tools/N64ModernRuntime && git apply --check "$randomizer_runtime_patch" )
        ( cd tools/N64ModernRuntime && git apply "$randomizer_runtime_patch" )
    fi
fi
# The desired post-audit state is patched, so the EXIT trap no longer needs to
# restore a layer removed above.
randomizer_runtime_was_applied=0
trap - EXIT

# --- build ------------------------------------------------------------------
echo "==> packaging for $DIST_OS (static SDL2: ${DIST_STATIC_SDL:-1})"
make dist "DIST_OS=$DIST_OS"

# --- archive ----------------------------------------------------------------
# zip for Windows (what a player expects), tar.gz everywhere; make whichever
# tools exist, and fail only if neither worked.
made=0
if command -v tar >/dev/null 2>&1; then
    make dist-tar "DIST_OS=$DIST_OS" >/dev/null && made=1
fi
# `make dist-zip` falls back to `cmake -E tar` when `zip` is missing, and Git
# Bash for Windows ships no zip, so cmake alone is enough to attempt it. Gating
# this on `zip` left the Windows run with only a tar.gz, and the workflow's
# Collect step, which takes the zip on Windows, failed with
# "dist/ogre-battle-64-recomp-windows.zip was not produced".
if command -v zip >/dev/null 2>&1 || command -v cmake >/dev/null 2>&1; then
    make dist-zip "DIST_OS=$DIST_OS" >/dev/null && made=1
fi
if [ "$made" = 0 ]; then
    echo "release-build.sh: no tar, zip or cmake is available to create an archive" >&2
    exit 1
fi

# `make dist-zip`/`dist-tar` each re-run `dist`; the payload is identical, so
# the result is just the folder plus both archives.
echo "==> done:"
ls -lh dist/
