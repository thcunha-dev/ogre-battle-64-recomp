#!/usr/bin/env python3
"""Static acquisition-source contract for Universal Item Randomizer.

Rev-A analysis proved four ordinary gameplay calls to func_ovlN_801DC740 in the
Bank-N mission module. Each consumes a transient source that the frame hook maps
*before* popup/reward text and final delivery, so the central replacement must
recognize those callers as already mapped rather than applying the permutation a
second time.

Direct setup/tutorial grants are a separate opt-in class. Every unclassified
direct caller is deliberately fail-closed and stays vanilla until its source and
save semantics are understood.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "mods/universal-item-randomizer/src/universal_item_randomizer.c").read_text()
MANIFEST = (ROOT / "mods/universal-item-randomizer/mod.toml").read_text()

# jal addresses and return addresses proven from the Rev-A cart.
CALLERS = {
    "map_object_a": (0x801ADEA8, 0x801ADEB0, "DROP_TABLE"),
    "map_object_b": (0x801AE188, 0x801AE190, "DROP_TABLE"),
    "ground_table_p": (0x801BB934, 0x801BB93C, "PICKUP_IDS"),
    "battle_reward": (0x801E53DC, 0x801E53E4, "REWARD_QUEUE"),
}


def require(token: str) -> None:
    assert token in SRC, f"missing universal acquisition coverage token: {token}"


def main() -> int:
    # Ordinary pickup/reward sources are transformed before the game consumes
    # them, keeping displayed and delivered ids identical.
    for token in (
        "rewrite_drop_table();",
        "rewrite_pickup_list();",
        "rewrite_reward_queue();",
        "#define DROP_TABLE",
        "#define PICKUP_IDS",
        "#define REWARD_QUEUE",
    ):
        require(token)

    # These exact caller return addresses must remain classified as already
    # mapped. A second application of a Sattolo cycle would deterministically
    # produce a different item and desync UI/source semantics.
    for token in (
        "caller_ra == RA_MAP_OBJECT_A",
        "caller_ra == RA_MAP_OBJECT_B",
        "caller_ra == RA_GROUND_PICKUP",
        "caller_ra == RA_BATTLE_REWARD",
    ):
        require(token)

    for name, (jal, ra, source) in CALLERS.items():
        assert jal + 8 == ra, name
        print(f"{name}: jal={jal:#010x} ra={ra:#010x} source={source}")

    # Starting/setup grants are explicit opt-in behavior, not part of ordinary
    # pickup coverage. The range classification and manifest switch must both
    # exist, and the direct-grant classifier must still end fail-closed.
    for token in (
        "#define RA_SETUP_R_LO",
        "#define RA_SETUP_R_HI",
        "caller_is_setup_grant(caller_ra)",
        "s_starting_items_enabled",
    ):
        require(token)
    assert 'id = "starting_items"' in MANIFEST
    assert 'default = false' in MANIFEST.split('id = "starting_items"', 1)[1].split("[[manifest.config_options]]", 1)[0]

    classifier = SRC.split("static int should_randomize_direct_grant", 1)[1]
    classifier = classifier.split("RECOMP_PATCH", 1)[0]
    assert classifier.rstrip().endswith("return 0;\n}"), "unknown direct callers are not fail-closed"

    print("universal normal acquisition coverage: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
