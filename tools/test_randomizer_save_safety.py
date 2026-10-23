#!/usr/bin/env python3
"""Static save-safety contract for Universal Item Randomizer.

This does not replace in-game save/load QA. It prevents the architecture from
regressing back to the failure mode this mod exists to avoid: treating inventory
reconstruction as acquisition, persisting randomizer state in native save data,
or randomizing an unclassified grant just because an unrelated option is on.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mods/universal-item-randomizer/src"


def body(text: str, signature: str, next_marker: str | None = None) -> str:
    assert signature in text, f"missing {signature}"
    tail = text.split(signature, 1)[1]
    if next_marker and next_marker in tail:
        tail = tail.split(next_marker, 1)[0]
    return tail


def main() -> int:
    central = (SRC / "universal_item_randomizer.c").read_text()
    mapper = (SRC / "randomizer_map.c").read_text()
    shop = (SRC / "shop_stock.c").read_text()
    post = (SRC / "post_battle_add.c").read_text()
    repair = (SRC / "use_repair.c").read_text()
    all_text = "\n".join((central, mapper, shop, post, repair))

    # The old randomizer used save/load reconstruction as a signal. This build
    # must not hook, patch or even call that path.
    for forbidden in (
        "func_800749C0",
        "RECOMP_HOOK(\"func_800749C0\")",
        "RECOMP_PATCH\nvoid func_800749C0",
    ):
        assert forbidden not in all_text, f"save/load path referenced: {forbidden}"

    # Randomizer configuration is read only from external mod config. No mapper
    # state is written through a generic RDRAM address or a save serialization
    # API. The mapper itself should be pure except for reading item metadata.
    assert "recomp_get_config_u32" in mapper
    for forbidden in ("wr8(", "wr16(", "wr32(", "MEM_W", "MEM_H", "MEM_B"):
        assert forbidden not in mapper, f"mapper writes game memory via {forbidden}"

    # The frame hook may prepare transient acquisition sources only. It must not
    # walk or transform the owned equipment/consumable lists.
    tick = body(central, "void universal_item_randomizer_tick(void)")
    for required in (
        "randomizer_init();",
        "rewrite_drop_table();",
        "rewrite_pickup_list();",
        "rewrite_reward_queue();",
    ):
        assert required in tick, f"frame hook lost {required}"
    for forbidden in ("EQUIP_LIST", "CONSUMABLE_LIST", "grant_vanilla("):
        assert forbidden not in tick, f"frame hook mutates owned inventory: {forbidden}"

    # The central grant is fail-closed. Starting grants are the only direct
    # caller class deliberately mapped here; known UI/source paths arrive already
    # mapped, and all other callers remain vanilla.
    direct = body(central, "static int should_randomize_direct_grant", "RECOMP_PATCH")
    assert "caller_is_setup_grant" in direct
    assert "s_starting_items_enabled" in direct
    assert direct.rstrip().endswith("return 0;\n}"), "unknown direct grant is not fail-closed"
    assert 'recomp_get_config_u32("shops")' not in central

    # Shop mutation is constrained to the transient Bank-AB source buffer and is
    # opt-in. It must not directly grant or rewrite the owned inventory arrays.
    assert 'recomp_get_config_u32("shops")' in shop
    assert "SHOP_STOCK_PTR" in shop
    for forbidden in ("0x80196B20u", "0x80193AE0u", "grant_vanilla"):
        assert forbidden not in shop, f"shop path touches owned inventory: {forbidden}"

    # Post-battle is an actual acquisition patch, so inventory writes are valid;
    # it must use the shared mapper rather than re-randomizing an existing list.
    assert "RECOMP_PATCH\nvoid func_80172820" in post
    assert "uir_map_equipment_id(original_id)" in post

    # No native-save-looking configuration/state identifiers should appear in
    # the mod. This catches accidental future persistence plumbing by name.
    lowered = all_text.lower()
    for forbidden in ("save_seed", "saved_seed", "serialize_randomizer", "randomizer_save", "save_metadata"):
        assert forbidden not in lowered, f"randomizer persistence introduced: {forbidden}"

    print("universal randomizer save-safety contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
