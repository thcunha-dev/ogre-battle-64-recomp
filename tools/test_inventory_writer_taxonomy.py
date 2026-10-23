#!/usr/bin/env python3
"""Static inventory-writer taxonomy contract for Universal Item Randomizer.

Rev-A objdump/ROM audits enumerate the normal owned-item writers. The randomizer
must patch only true acquisition writers, prepare display-sensitive acquisition
sources, and leave transfer/reconstruction/debug/coupled setup writers alone.

This test is intentionally conservative. If a new inventory writer is discovered,
it should fail review until it has an explicit semantic category rather than being
silently treated as an acquisition.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "mods/universal-item-randomizer/src"
MOD_TEXT = "\n".join(path.read_text() for path in sorted(SRC_DIR.glob("*.c")))

# True gameplay acquisition writers covered by replacements/source mapping.
ACQUISITION_WRITERS = {
    "main_grant": "func_ovlN_801DC740",
    "post_battle_add": "func_80172820",
}

# Writers/operations that alter inventory bookkeeping but are not acquisitions.
# They must never become RECOMP_PATCH/HOOK targets in this mod merely because
# they touch the owned lists.
NON_ACQUISITION_WRITERS = {
    # Base class-change transfer/copy. Moves/rebuilds equipment ownership around
    # class changes; randomizing here would rerandomize existing owned state.
    "class_change_base": "func_80172C64",
    # Bank-M scene-local analogue of the same transfer behavior.
    "class_change_bank_m": "func_ovlM_801A4110",
    # Full transient +0x02 roster-reference rebuild. Called after load and other
    # bookkeeping; it is explicitly not an acquisition signal.
    "used_count_rebuild": "func_8016B774",
    # Save-load restore path calls the rebuild and reconstructs native inventory.
    "save_restore": "func_8016CEC4",
    # Bank-S developer/debug path that sets owned counts for existing items.
    "debug_cheat": "func_ovlS_801C214C",
    # Class-derived default equipment setup is source-coupled to roster/class
    # references and remains vanilla until source and inventory can map together.
    "class_default_equipment": "func_ovlN_801DD430",
}

# The remaining Bank-R direct main-grant caller is also coupled setup, but it is
# classified by return address rather than a separate callee function: the ROM
# writes consumable id 28 into unit+0x0D first, then grant(28,1). The central
# replacement must recognize it and preserve the raw id.
COUPLED_LOADOUT_TOKENS = (
    "RA_UNIT_LOADOUT_R",
    "caller_is_coupled_unit_loadout",
    "coupled Bank-R unit loadout left vanilla",
)


def target_marker(symbol: str, kind: str) -> str:
    if kind == "patch":
        return f"RECOMP_PATCH\nvoid {symbol}"
    return f'RECOMP_HOOK("{symbol}")'


def main() -> int:
    # Both proven acquisition writers must be explicit replacements. The main
    # grant is accompanied by source rewrites so UI and delivered id agree.
    for name, symbol in ACQUISITION_WRITERS.items():
        assert target_marker(symbol, "patch") in MOD_TEXT, f"missing acquisition patch: {name} {symbol}"

    central = (SRC_DIR / "universal_item_randomizer.c").read_text()
    for required in (
        "rewrite_drop_table();",
        "rewrite_pickup_list();",
        "rewrite_reward_queue();",
        "caller_source_already_mapped",
    ):
        assert required in central, f"main acquisition source coverage lost: {required}"

    # Never hook/patch transfer, restore, bookkeeping, debug, or class-default
    # writers. Seeing their symbol names in comments/tests is fine; executable
    # target markers are what would change semantics.
    for category, symbol in NON_ACQUISITION_WRITERS.items():
        assert target_marker(symbol, "patch") not in MOD_TEXT, f"non-acquisition patched: {category} {symbol}"
        assert target_marker(symbol, "hook") not in MOD_TEXT, f"non-acquisition hooked: {category} {symbol}"

    # No save-load function may be used as an acquisition detector.
    for forbidden in (
        'RECOMP_HOOK("func_800749C0")',
        "RECOMP_PATCH\nvoid func_800749C0",
        'RECOMP_HOOK("func_8016CEC4")',
        "RECOMP_PATCH\nvoid func_8016CEC4",
    ):
        assert forbidden not in MOD_TEXT, f"save/load path became acquisition signal: {forbidden}"

    # The coupled per-unit consumable loadout is explicitly classified and must
    # not be accepted by the direct randomizing classifier.
    for token in COUPLED_LOADOUT_TOKENS:
        assert token in central, f"coupled unit loadout classification lost: {token}"
    classifier = central.split("static int should_randomize_direct_grant", 1)[1].split("RECOMP_PATCH", 1)[0]
    assert "caller_is_coupled_unit_loadout" not in classifier, "coupled unit loadout became randomizable"
    assert classifier.rstrip().endswith("return 0;\n}"), "future direct callers are not fail-closed"

    # Class-default equipment is intentionally absent from config until an
    # atomic source/reference-safe implementation exists.
    manifest = (ROOT / "mods/universal-item-randomizer/mod.toml").read_text()
    for unsafe_option in ("class_equipment", "class_defaults", "starting_equipment"):
        assert f'id = "{unsafe_option}"' not in manifest, f"unsafe class equipment option exposed: {unsafe_option}"

    print("inventory writer taxonomy: PASS")
    print("  acquisition: func_ovlN_801DC740, func_80172820")
    print("  protected: class change, save/rebuild, debug, class defaults, coupled unit loadout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
