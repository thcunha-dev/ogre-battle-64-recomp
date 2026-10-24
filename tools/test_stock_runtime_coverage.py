#!/usr/bin/env python3
"""Static acquisition-source contract for Universal Item Randomizer.

Rev-A whole-game analysis accounts for every call to func_ovlN_801DC740. Four
Bank-N gameplay calls consume transient UI sources. Bank R has one safe literal
starting-item range and two coupled unit/setup calls that also write unit-loadout
references; those coupled calls must stay vanilla until reference and inventory
can be mapped atomically.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "mods/universal-item-randomizer/src/universal_item_randomizer.c").read_text()
MANIFEST = (ROOT / "mods/universal-item-randomizer/mod.toml").read_text()

SOURCE_CALLERS = {
    "map_object_a": (0x801ADEA8, 0x801ADEB0, "RA_MAP_OBJECT_A", "DROP_TABLE"),
    "map_object_b": (0x801AE188, 0x801AE190, "RA_MAP_OBJECT_B", "DROP_TABLE"),
    "ground_pickup": (0x801BB934, 0x801BB93C, "RA_GROUND_PICKUP", "PICKUP_IDS"),
    "battle_reward": (0x801E53DC, 0x801E53E4, "RA_BATTLE_REWARD", "REWARD_QUEUE"),
}

COUPLED_SETUP = (0x80215BEC, 0x80215BF4, "RA_TUTORIAL_SETUP_R")
UNIT_LOADOUT = (0x80216D90, 0x80216D98, "RA_UNIT_LOADOUT_R")
STARTING_JAL_LO = 0x80217068
STARTING_JAL_HI = 0x80217244
STARTING_RA_LO = STARTING_JAL_LO + 8
STARTING_RA_HI_EXCLUSIVE = STARTING_JAL_HI + 8


def require(token: str) -> None:
    assert token in SRC, f"missing universal acquisition coverage token: {token}"


def main() -> int:
    for token in (
        "rewrite_drop_table();",
        "rewrite_pickup_list();",
        "rewrite_reward_queue();",
        "#define DROP_TABLE",
        "#define PICKUP_IDS",
        "#define REWARD_QUEUE",
    ):
        require(token)

    for name, (jal, ra, macro, source) in SOURCE_CALLERS.items():
        assert jal + 8 == ra, name
        require(f"#define {macro}")
        require(f"caller_ra == {macro}")
        print(f"{name}: jal={jal:#010x} ra={ra:#010x} source={source}")

    assert STARTING_RA_LO == 0x80217070
    assert STARTING_RA_HI_EXCLUSIVE == 0x8021724C
    for token in (
        "#define RA_STARTING_R_LO         0x80217070u",
        "#define RA_STARTING_R_HI         0x8021724Cu",
        "return caller_ra >= RA_STARTING_R_LO && caller_ra < RA_STARTING_R_HI;",
        "caller_is_starting_grant(caller_ra)",
        "s_starting_items_enabled",
    ):
        require(token)
    assert 'id = "starting_items"' in MANIFEST
    starting_cfg = MANIFEST.split('id = "starting_items"', 1)[1].split("[[manifest.config_options]]", 1)[0]
    assert "default = false" in starting_cfg

    # Both Rev-A a1=1 callers write/maintain a unit's ten-byte consumable
    # loadout at unit+0x0D and then grant the corresponding consumable. Mapping
    # only the global inventory id would break the native slot-reference link.
    for jal, ra, macro in (COUPLED_SETUP, UNIT_LOADOUT):
        assert jal + 8 == ra
        require(f"#define {macro}")
        require(f"caller_ra == {macro}")

    require("caller_is_coupled_unit_grant")
    require("coupled Bank-R unit/setup grant left vanilla")

    classifier = SRC.split("static int should_randomize_direct_grant", 1)[1]
    classifier = classifier.split("RECOMP_PATCH", 1)[0]
    assert "if (caller_is_coupled_unit_grant(caller_ra)) return 0;" in classifier
    assert classifier.index("caller_is_coupled_unit_grant") < classifier.index("caller_is_starting_grant")
    assert classifier.rstrip().endswith("return 0;\n}"), "unknown/future direct callers are not fail-closed"

    starting = SRC.split("static int caller_is_starting_grant", 1)[1]
    starting = starting.split("static int caller_is_coupled_unit_grant", 1)[0]
    assert "RA_TUTORIAL_SETUP_R" not in starting
    assert "RA_UNIT_LOADOUT_R" not in starting

    for stale in (
        "RA_SETUP_R_LO", "RA_SETUP_R_HI", "RA_BANK_R_UNKNOWN", "RA_BANK_R_UNKNOWN_A",
        "RA_BANK_R_UNKNOWN_B", "caller_is_unclassified_bank_r", "0x80215000u", "0x80217300u",
        "caller_is_coupled_unit_loadout",
    ):
        assert stale not in SRC, f"stale/broad Bank-R classification returned: {stale}"

    print("universal whole-game main-grant caller coverage: PASS (coupled setup fail-closed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
