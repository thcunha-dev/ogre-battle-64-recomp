#!/usr/bin/env python3
"""Static save-safety contract for Universal Item Randomizer."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mods/universal-item-randomizer/src"


def body(text: str, signature: str, next_marker: str | None = None) -> str:
    assert signature in text, f"missing {signature}"
    tail = text.split(signature, 1)[1]
    if next_marker and next_marker in tail:
        tail = tail.split(next_marker, 1)[0]
    return tail


def strip_c_comments(text: str) -> str:
    """Remove // and /* */ comments for code-only persistence assertions."""
    out: list[str] = []
    i = 0
    block = False
    while i < len(text):
        if block:
            end = text.find("*/", i)
            if end < 0:
                break
            i = end + 2
            block = False
            continue
        if text.startswith("/*", i):
            block = True
            i += 2
            continue
        if text.startswith("//", i):
            end = text.find("\n", i)
            if end < 0:
                break
            out.append("\n")
            i = end + 1
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def main() -> int:
    central = (SRC / "universal_item_randomizer.c").read_text()
    mapper = (SRC / "randomizer_map.c").read_text()
    shop = (SRC / "shop_stock.c").read_text()
    post = (SRC / "post_battle_add.c").read_text()
    repair = (SRC / "use_repair.c").read_text()
    all_text = "\n".join((central, mapper, shop, post, repair))

    for forbidden in (
        "func_800749C0",
        "RECOMP_HOOK(\"func_800749C0\")",
        "RECOMP_PATCH\nvoid func_800749C0",
    ):
        assert forbidden not in all_text, f"save/load path referenced: {forbidden}"

    assert "recomp_get_config_u32" in mapper
    for forbidden in ("wr8(", "wr16(", "wr32(", "MEM_W", "MEM_H", "MEM_B"):
        assert forbidden not in mapper, f"mapper writes game memory via {forbidden}"

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

    direct = body(central, "static int should_randomize_direct_grant", "RECOMP_PATCH")
    assert "caller_is_starting_grant" in direct
    assert "s_starting_items_enabled" in direct
    assert direct.rstrip().endswith("return 0;\n}"), "unknown direct grant is not fail-closed"
    assert "#define RA_TUTORIAL_SETUP_R      0x80215BF4u" in central
    assert "#define RA_STARTING_R_LO         0x80217070u" in central
    assert "#define RA_STARTING_R_HI         0x8021724Cu" in central
    assert "#define RA_BANK_R_UNKNOWN        0x80216D98u" in central
    assert "caller_ra == RA_TUTORIAL_SETUP_R" in central
    assert "caller_is_unclassified_bank_r" in central
    assert "unclassified Bank-R grant left vanilla" in central
    assert "RA_BANK_R_UNKNOWN_A" not in central and "RA_BANK_R_UNKNOWN_B" not in central
    assert "RA_SETUP_R_LO" not in central and "RA_SETUP_R_HI" not in central
    assert 'recomp_get_config_u32("shops")' not in central

    assert 'recomp_get_config_u32("shops")' in shop
    assert "SHOP_STOCK_PTR" in shop
    for forbidden in ("0x80196B20u", "0x80193AE0u", "grant_vanilla"):
        assert forbidden not in shop, f"shop path touches owned inventory: {forbidden}"

    assert "RECOMP_PATCH\nvoid func_80172820" in post
    assert "uir_map_equipment_id(original_id)" in post
    assert "universal_item_randomizer_force_use_repair();" in post

    assert "#define LIST_USE                 2u" in repair
    assert "void universal_item_randomizer_force_use_repair(void)" in repair
    assert "full_repair_and_snapshot();" in repair
    assert "wr8(record + LIST_USE" in repair

    # Comments explicitly document that seed/save state is *not* touched. Run
    # persistence assertions on code only so those safety comments cannot become
    # false positives while still rejecting real seed/config/persistence access.
    repair_code = strip_c_comments(repair)
    for forbidden in (
        "wr16(",
        "wr32(",
        "LIST_COUNT",
        "uir_map_",
        "recomp_get_config_u32",
        '"seed"',
        "s_seed",
        "save_seed",
        "saved_seed",
    ):
        assert forbidden not in repair_code, f"transient repair can affect saved state: {forbidden}"

    lowered = strip_c_comments(all_text).lower()
    for forbidden in ("save_seed", "saved_seed", "serialize_randomizer", "randomizer_save", "save_metadata"):
        assert forbidden not in lowered, f"randomizer persistence introduced: {forbidden}"

    print("universal randomizer save-safety contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
