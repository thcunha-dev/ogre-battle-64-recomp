#!/usr/bin/env bash
# Build the Universal Item Randomizer with main + streamed-bank reference symbols.
set -euo pipefail

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

n64recomp=tools/N64Recomp/build/N64Recomp
modtool=tools/N64Recomp/build/RecompModTool
main_elf=build/ogrebattle64.elf
out_root=build/mod-syms
main_dump="$out_root/main"
merged=mods/reference/dump.toml

bank_units=(
  A B C D E F G H I J K L M N O P Q R S T U V W X Y Z
  AA AB AC AD AE AF AG AH
)

fail() {
    echo "build-universal-randomizer.sh: $*" >&2
    exit 1
}

[ -x "$n64recomp" ] || fail "$n64recomp is missing; build N64Recomp first"
[ -x "$modtool" ] || fail "$modtool is missing; build RecompModTool first"
[ -f "$main_elf" ] || fail "$main_elf is missing; link/regenerate the game first"

rm -rf "$out_root"
mkdir -p "$main_dump" mods/reference

echo "==> dumping main ELF symbols"
(
    cd "$main_dump"
    "$root/$n64recomp" "$root/config/config.toml" --dump-context >/dev/null
)
[ -f "$main_dump/dump.toml" ] || fail "main dump.toml was not produced"
[ -f "$main_dump/data_dump.toml" ] || fail "main data_dump.toml was not produced"

inputs=("$main_dump/dump.toml")

for unit in "${bank_units[@]}"; do
    elf="build/bank${unit}.elf"
    cfg="config/banks/config-bank${unit}.toml"
    dir="$out_root/bank${unit}"

    [ -f "$elf" ] || fail "$elf is missing; run 'make bank-recomp' first"
    [ -f "$cfg" ] || fail "$cfg is missing"

    mkdir -p "$dir"
    echo "==> dumping Bank${unit} symbols"
    (
        cd "$dir"
        "$root/$n64recomp" "$root/$cfg" --dump-context >/dev/null
    )
    [ -f "$dir/dump.toml" ] || fail "Bank${unit} dump.toml was not produced"
    inputs+=("$dir/dump.toml")
done

python3 tools/merge_mod_syms.py "$merged" "${inputs[@]}"
cp "$main_dump/data_dump.toml" mods/reference/data_dump.toml

# Guard the one symbol this project exists to expose. A build that omits Bank N
# must fail here instead of producing a randomizer that silently falls back to
# the old RAM-watching behaviour.
grep -q 'name = "func_ovlN_801DC740"' "$merged" || \
    fail "merged symbols do not contain func_ovlN_801DC740"

echo "==> building universal-item-randomizer.nrm"
tools/build-example-mods.sh mods/universal-item-randomizer

echo "==> build/mods/universal-item-randomizer.nrm"
