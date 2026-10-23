#!/usr/bin/env python3
"""Static acquisition-source contract for Universal Item Randomizer.

Rev-A whole-game analysis found every call to func_ovlN_801DC740. Four ordinary
Bank-N gameplay calls consume transient sources that are mapped before UI/final
delivery. Bank R contributes two still-unclassified calls plus the proven
straight-line starting-consumable block. This test makes that caller inventory a
contract: every audited caller must be explicitly accounted for, and unknowns
must remain fail-closed.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "mods/universal-item-randomizer/src/universal_item_randomizer.c").read_text()
MANIFEST = (ROOT / "mods/universal-item-randomizer/mod.toml").read_text()

# Exact Bank-N jal addresses and return addresses proven from the Rev-A cart.
SOURCE_CALLERS = {
    "map_object_a": (0x801ADEA8, 0x801ADEB0, "RA_MAP_OBJECT_A", "DROP_TABLE"),
    "map_object_b": (0x801AE188, 0x801AE190, "RA_MAP_OBJECT_B", "DROP_TABLE"),
    "ground_pickup": (0x801BB934, 0x801BB93C, "RA_GROUND_PICKUP", "PICKUP_IDS"),
    "battle_reward": (0x801E53DC, 0x801E53E4, "RA_BATTLE_REWARD", "REWARD_QUEUE"),
}

# The two non-literal Bank-R calls found by the same whole-game scan. Their game
# meaning is not yet proven, so they are named/observable but never randomized.
UNKNOWN_BANK_R = {
    "bank_r_unknown_a": (0x80215BEC, 0x80215BF4, "RA_BANK_R_UNKNOWN_A"),
    "bank_r_unknown_b": (0x80216D90, 0x80216D98, "RA_BANK_R_UNKNOWN_B"),
}

# Proven literal starting-consumable jal block. The last documented jal lies at
# or below 0x80217244, hence return addresses are inside [0x80217070,0x8021724c).
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

    # Known display-sensitive routes must be transformed at their source and the
    # central grant must recognize their exact return addresses as already mapped.
    for name, (jal, ra, macro, source) in SOURCE_CALLERS.items():
        assert jal + 8 == ra, name
        require(f"#define {macro}")
        require(f"caller_ra == {macro}")
        print(f"{name}: jal={jal:#010x} ra={ra:#010x} source={source}")

    # Starting items are the only direct Bank-R class currently eligible for
    # mapping, and only inside the disassembly-proven literal block.
    assert STARTING_RA_LO == 0x80217070
    assert STARTING_RA_HI_EXCLUSIVE == 0x8021724C
    for token in (
        "#define RA_STARTING_R_LO         0x80217070u",
        "#define RA_STARTING_R_HI         0x8021724Cu",
        "caller_is_starting_grant(caller_ra)",
        "s_starting_items_enabled",
    ):
        require(token)
    assert 'id = "starting_items"' in MANIFEST
    starting_cfg = MANIFEST.split('id = "starting_items"', 1)[1].split("[[manifest.config_options]]", 1)[0]
    assert "default = false" in starting_cfg

    # The remaining Bank-R callers are explicitly represented and observable,
    # but are not accepted by should_randomize_direct_grant().
    for name, (jal, ra, macro) in UNKNOWN_BANK_R.items():
        assert jal + 8 == ra, name
        require(f"#define {macro}")
        require(f"caller_ra == {macro}")
        print(f"{name}: jal={jal:#010x} ra={ra:#010x} classification=vanilla")
    require("caller_is_unclassified_bank_r")
    require("unclassified Bank-R grant left vanilla")

    classifier = SRC.split("static int should_randomize_direct_grant", 1)[1]
    classifier = classifier.split("RECOMP_PATCH", 1)[0]
    assert "caller_is_unclassified_bank_r" not in classifier, "unknown Bank-R caller became randomizable"
    assert classifier.rstrip().endswith("return 0;\n}"), "unknown direct callers are not fail-closed"

    # Do not regress to the old broad Bank-R module range, which accidentally
    # included both unknown calls under STARTING ITEMS.
    for stale in ("RA_SETUP_R_LO", "RA_SETUP_R_HI", "0x80215000u", "0x80217300u"):
        assert stale not in SRC, f"broad Bank-R classification returned: {stale}"

    print("universal whole-game main-grant caller coverage: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
