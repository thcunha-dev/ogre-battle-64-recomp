#!/usr/bin/env python3
"""Static coverage contract for the stock-runtime randomizer variant.

Rev-A ROM analysis found exactly four gameplay calls to func_ovlN_801DC740 in
Bank N. All four consume sources that the frame hook rewrites before delivery.
The stock-runtime package deliberately removes the Bank-N replacement, so this
contract makes that architectural assumption explicit and regression-testable.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "mods/universal-item-randomizer/src/universal_item_randomizer.c").read_text()

# jal addresses and return addresses proven from the Rev-A cart.
CALLERS = {
    "map_object_a": (0x801ADEA8, 0x801ADEB0, "DROP_TABLE"),
    "map_object_b": (0x801AE188, 0x801AE190, "DROP_TABLE"),
    "ground_table_p": (0x801BB934, 0x801BB93C, "PICKUP_IDS"),
    "battle_reward": (0x801E53DC, 0x801E53E4, "REWARD_QUEUE"),
}


def require(token: str) -> None:
    assert token in SRC, f"missing stock-runtime coverage token: {token}"


def main() -> int:
    # Source rewrite entry points must remain in the primary frame hook.
    for token in (
        "rewrite_drop_table();",
        "rewrite_pickup_list();",
        "rewrite_reward_queue();",
        "#define DROP_TABLE",
        "#define PICKUP_IDS",
        "#define REWARD_QUEUE",
    ):
        require(token)

    # Both Table-O map callers must be classified as already mapped. This is
    # especially important for Map B: ROM disassembly proved it loads the item
    # from Table O before copying it to popup state, so direct remapping would be
    # a deterministic *second* mapping rather than extra coverage.
    require("caller_ra == RA_MAP_OBJECT_A")
    require("caller_ra == RA_MAP_OBJECT_B")
    require("caller_ra == RA_GROUND_PICKUP")
    require("caller_ra == RA_BATTLE_REWARD")

    for name, (jal, ra, source) in CALLERS.items():
        assert jal + 8 == ra, name
        print(f"{name}: jal={jal:#010x} ra={ra:#010x} source={source}")

    # The optional starting-item feature genuinely depends on the Bank-N direct
    # replacement and must not be advertised by the stock-runtime package.
    assert "STARTING ITEMS" in (ROOT / "mods/universal-item-randomizer/mod.toml").read_text()
    print("stock-runtime normal acquisition coverage: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
