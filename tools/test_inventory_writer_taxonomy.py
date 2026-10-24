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

ACQUISITION_WRITERS = {
    "main_grant": "func_ovlN_801DC740",
    "post_battle_add": "func_80172820",
}

NON_ACQUISITION_WRITERS = {
    "class_change_base": "func_80172C64",
    "class_change_bank_m": "func_ovlM_801A4110",
    "used_count_rebuild": "func_8016B774",
    "save_restore": "func_8016CEC4",
    "debug_cheat": "func_ovlS_801C214C",
    "class_default_equipment": "func_ovlN_801DD430",
}

# Two Bank-R main-grant callers are coupled to a unit's consumable loadout. Both
# pass a1=1 and write/maintain the unit+0x0D slot references before granting the
# matching consumable. Central-only mapping would split roster references from
# the owned-list slot, so both are fail-closed/vanilla.
COUPLED_LOADOUT_TOKENS = (
    "RA_TUTORIAL_SETUP_R",
    "RA_UNIT_LOADOUT_R",
    "caller_is_coupled_unit_grant",
    "coupled Bank-R unit/setup grant left vanilla",
)


def target_marker(symbol: str, kind: str) -> str:
    if kind == "patch":
        return f"RECOMP_PATCH\nvoid {symbol}"
    return f'RECOMP_HOOK("{symbol}")'


def main() -> int:
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

    for category, symbol in NON_ACQUISITION_WRITERS.items():
        assert target_marker(symbol, "patch") not in MOD_TEXT, f"non-acquisition patched: {category} {symbol}"
        assert target_marker(symbol, "hook") not in MOD_TEXT, f"non-acquisition hooked: {category} {symbol}"

    for forbidden in (
        'RECOMP_HOOK("func_800749C0")',
        "RECOMP_PATCH\nvoid func_800749C0",
        'RECOMP_HOOK("func_8016CEC4")',
        "RECOMP_PATCH\nvoid func_8016CEC4",
    ):
        assert forbidden not in MOD_TEXT, f"save/load path became acquisition signal: {forbidden}"

    for token in COUPLED_LOADOUT_TOKENS:
        assert token in central, f"coupled unit/setup classification lost: {token}"

    coupled = central.split("static int caller_is_coupled_unit_grant", 1)[1]
    coupled = coupled.split("static int should_randomize_direct_grant", 1)[0]
    assert "caller_ra == RA_TUTORIAL_SETUP_R" in coupled
    assert "caller_ra == RA_UNIT_LOADOUT_R" in coupled

    starting = central.split("static int caller_is_starting_grant", 1)[1]
    starting = starting.split("static int caller_is_coupled_unit_grant", 1)[0]
    assert "RA_TUTORIAL_SETUP_R" not in starting
    assert "RA_UNIT_LOADOUT_R" not in starting

    classifier = central.split("static int should_randomize_direct_grant", 1)[1].split("RECOMP_PATCH", 1)[0]
    assert "if (caller_is_coupled_unit_grant(caller_ra)) return 0;" in classifier
    assert classifier.index("caller_is_coupled_unit_grant") < classifier.index("caller_is_starting_grant")
    assert classifier.rstrip().endswith("return 0;\n}"), "future direct callers are not fail-closed"

    manifest = (ROOT / "mods/universal-item-randomizer/mod.toml").read_text()
    for unsafe_option in ("class_equipment", "class_defaults", "starting_equipment"):
        assert f'id = "{unsafe_option}"' not in manifest, f"unsafe class equipment option exposed: {unsafe_option}"

    print("inventory writer taxonomy: PASS")
    print("  acquisition: func_ovlN_801DC740, func_80172820")
    print("  protected: class change, save/rebuild, debug, class defaults, coupled Bank-R unit/setup grants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
