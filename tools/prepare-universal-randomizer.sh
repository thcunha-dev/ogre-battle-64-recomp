#!/usr/bin/env bash
# Prepare the local runtime/generated bank registry for the Universal Item Randomizer.
set -euo pipefail

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

runtime=tools/N64ModernRuntime
patch="$root/patches/n64modernruntime-randomizer.patch"

[ -d "$runtime/.git" ] || {
    echo "prepare-universal-randomizer.sh: $runtime is missing." >&2
    echo "  Prepare the normal OB64 third-party tree first, then rerun this script." >&2
    exit 1
}

if ( cd "$runtime" && git apply --reverse --check "$patch" ) >/dev/null 2>&1; then
    echo "==> randomizer runtime patch already applied"
elif ( cd "$runtime" && git apply --check "$patch" ) >/dev/null 2>&1; then
    echo "==> applying randomizer runtime patch"
    ( cd "$runtime" && git apply "$patch" )
else
    echo "prepare-universal-randomizer.sh: runtime tree is neither pristine-for nor already carrying $patch" >&2
    echo "  Check tools/N64ModernRuntime against the project's pinned/OB64-patched runtime." >&2
    exit 1
fi

# bank_funcs.inc is generated from Bank*Funcs and is what registers every bank
# record with the replacement lookup. Regenerate it even when the bank C files
# are unchanged so an older generated include cannot silently omit the registrar.
python3 tools/gen_bank_funcs.py

echo "==> Universal Randomizer runtime support prepared"
echo "    Rebuild the app so the runtime patch and regenerated bank_funcs.inc are linked."
