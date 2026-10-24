#!/usr/bin/env bash
set -euo pipefail

elf="${1:-mods/universal-item-randomizer/build/mod.elf}"

if [[ ! -s "$elf" ]]; then
  echo "missing randomizer ELF: $elf" >&2
  exit 1
fi

objdump_bin="${OBJDUMP:-mips-linux-gnu-objdump}"
nm_bin="${NM:-mips-linux-gnu-nm}"
readelf_bin="${READELF:-mips-linux-gnu-readelf}"

sections="$(mktemp)"
symbols="$(mktemp)"
trap 'rm -f "$sections" "$symbols"' EXIT

"$objdump_bin" -h "$elf" | tee "$sections"

# This mod currently contains two RECOMP_PATCH replacements and one frame hook
# on func_80072944. A recomp_hook_return section is optional and is only emitted
# when a hook-return patch is actually used, so it is deliberately not required.
for section in '.recomp_patch' '.recomp_hook.func_80072944'; do
  grep -Fq "$section" "$sections" || {
    echo "missing required ELF section: $section" >&2
    exit 1
  }
done

"$nm_bin" -n "$elf" | tee "$symbols"
for sym in \
  func_ovlN_801DC740 \
  func_80172820 \
  universal_item_randomizer_tick \
  universal_item_randomizer_force_use_repair \
  universal_item_randomizer_log_post_battle \
  uir_map_init \
  uir_map_item_word \
  uir_map_equipment_id \
  uir_map_consumable_id; do
  grep -Eq "[[:space:]]${sym}$" "$symbols" || {
    echo "missing required ELF symbol: $sym" >&2
    exit 1
  }
done

"$readelf_bin" -sW "$elf" | grep -E \
  'func_ovlN_801DC740|func_80172820|universal_item_randomizer_tick' >/dev/null

echo "universal randomizer MIPS ELF contract: PASS"
