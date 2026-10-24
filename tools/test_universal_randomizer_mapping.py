#!/usr/bin/env python3
"""Host-side invariants for the Universal Item Randomizer mapping.

The numeric test mirrors the tiny integer mixer/xorshift/Sattolo code used by
randomizer_map.c. Source-contract checks ensure every acquisition path consumes
that one mapper instead of silently growing a second implementation.
"""

from __future__ import annotations

from pathlib import Path

MASK = 0xFFFFFFFF
EQUIP_SALT = 0x45515549
CONSUMABLE_SALT = 0x434F4E53
KEY_SALT = 0x4B455953
COUNT_MAX = 99


def u32(x: int) -> int:
    return x & MASK


def mix32(x: int) -> int:
    x = u32(x ^ (x >> 16))
    x = u32(x * 0x7FEB352D)
    x = u32(x ^ (x >> 15))
    x = u32(x * 0x846CA68B)
    x = u32(x ^ (x >> 16))
    return x


def rng_next(state: int) -> int:
    x = state
    x = u32(x ^ (x << 13))
    x = u32(x ^ (x >> 17))
    x = u32(x ^ (x << 5))
    return x


def cycle(seed: int, sources: list[int], salt: int) -> dict[int, int]:
    targets = list(sources)
    if len(targets) > 1:
        state = mix32(u32(seed ^ salt ^ u32(len(targets) * 0x9E3779B9)))
        if state == 0:
            state = 0xA341316C
        for i in range(len(targets) - 1, 0, -1):
            state = rng_next(state)
            j = state % i
            targets[i], targets[j] = targets[j], targets[i]
    return dict(zip(sources, targets, strict=True))


def saturated_count(current: int, amount: int) -> int:
    return min(current + amount, COUNT_MAX)


def assert_cycle_properties(seed: int, size: int, salt: int) -> None:
    src = list(range(1, size + 1))
    a = cycle(seed, src, salt)
    b = cycle(seed, src, salt)
    assert a == b, (seed, size, "same seed was not deterministic")
    assert set(a) == set(src)
    assert set(a.values()) == set(src), (seed, size, "mapping was not bijective")
    if size > 1:
        assert all(k != v for k, v in a.items()), (seed, size, "fixed point")


def assert_shared_mapper_contract(repo: Path) -> None:
    src = repo / "mods/universal-item-randomizer/src"
    mapper = (src / "randomizer_map.c").read_text()
    header = (repo / "mods/universal-item-randomizer/include/randomizer_map.h").read_text()
    use_repair = (src / "use_repair.c").read_text()
    consumers = {
        "central": (src / "universal_item_randomizer.c").read_text(),
        "post_battle": (src / "post_battle_add.c").read_text(),
        "shop": (src / "shop_stock.c").read_text(),
    }

    for token in (
        "0x45515549u",
        "0x434F4E53u",
        "0x4B455953u",
        "0x7FEB352Du",
        "0x846CA68Bu",
        "0x9E3779B9u",
        "0xA341316Cu",
    ):
        assert token in mapper, f"shared mapper missing {token}"
        for name, text in consumers.items():
            assert token not in text, f"{name}: duplicated mapper constant {token}"

    for symbol in (
        "uir_map_init",
        "uir_map_equipment_id",
        "uir_map_consumable_id",
        "uir_map_item_word",
    ):
        assert symbol in header, f"mapper header missing {symbol}"
        assert symbol in mapper, f"mapper source missing {symbol}"

    assert '#include "randomizer_map.h"' in consumers["central"]
    assert "uir_map_item_word" in consumers["central"]
    assert '#include "randomizer_map.h"' in consumers["shop"]
    assert "uir_map_item_word" in consumers["shop"]
    assert '#include "randomizer_map.h"' in consumers["post_battle"]
    assert "uir_map_equipment_id" in consumers["post_battle"]

    assert 'recomp_get_config_u32("key_items")' in mapper
    assert "#define CONSUMABLE_KEY_MIN       3u" in mapper
    assert "#define CONSUMABLE_KEY_MAX       4u" in mapper
    assert "cls >= CONSUMABLE_KEY_MIN && cls <= CONSUMABLE_KEY_MAX" in mapper
    assert "if (s_key_items_enabled)" in mapper
    assert "build_cycle_map(s_consumable_map, key_pool" in mapper
    assert "Unknown classes are intentionally omitted" in mapper

    # Native func_8016B774 rebuilds +0x02 by owned-list SLOT, not item id.
    # Keep that semantics locked here because an ID-indexed repair can silently
    # diverge whenever compact inventory slot != definition id.
    assert "#define CONSUMABLE_SLOTS         40u" in use_repair
    assert "#define EQUIP_SLOTS              278u" in use_repair
    assert "s_equip_refs[EQUIP_SLOTS]" in use_repair
    assert "s_consumable_refs[CONSUMABLE_SLOTS]" in use_repair
    assert "slot_index < EQUIP_SLOTS" in use_repair
    assert "slot_index < CONSUMABLE_SLOTS" in use_repair
    assert "s_equip_refs[i]" in use_repair
    assert "s_consumable_refs[i]" in use_repair
    assert "s_equip_refs[id]" not in use_repair
    assert "s_consumable_refs[id]" not in use_repair
    assert "CONSUMABLE_ID_MAX" not in use_repair

    central = consumers["central"]
    assert "#define MAP_INDEX                0x8018F4A1u" in central

    # Both map-owned source shadows must use MAP_INDEX as a generation boundary.
    assert "s_drop_map_index" in central
    assert "s_drop_map_known" in central
    assert "static void reset_drop_shadow" in central
    assert "map_index != s_drop_map_index" in central
    assert "reset_drop_shadow();" in central

    assert "s_pickup_map_index" in central
    assert "s_pickup_map_known" in central
    assert "static void reset_pickup_shadow" in central
    assert "map_index = rd8(MAP_INDEX);" in central
    assert "map_index != s_pickup_map_index" in central
    assert "reset_pickup_shadow();" in central

    # STARTING ITEMS covers only the two audited safe setup sources. The third
    # Bank-R caller is fully classified as a coupled per-unit consumable loadout:
    # the loader writes id 28 into unit+0x0D before grant(28,1), so central-only
    # mapping would split the unit reference from owned inventory.
    assert "#define RA_TUTORIAL_SETUP_R      0x80215BF4u" in central
    assert "#define RA_UNIT_LOADOUT_R        0x80216D98u" in central
    assert "#define RA_STARTING_R_LO         0x80217070u" in central
    assert "#define RA_STARTING_R_HI         0x8021724Cu" in central
    assert "caller_ra == RA_TUTORIAL_SETUP_R" in central
    assert "caller_is_starting_grant" in central
    assert "caller_is_coupled_unit_loadout" in central
    assert "caller_ra == RA_UNIT_LOADOUT_R" in central
    assert "coupled Bank-R unit loadout left vanilla" in central
    for stale in (
        "RA_BANK_R_UNKNOWN",
        "RA_BANK_R_UNKNOWN_A",
        "RA_BANK_R_UNKNOWN_B",
        "caller_is_unclassified_bank_r",
        "RA_SETUP_R_LO",
        "RA_SETUP_R_HI",
    ):
        assert stale not in central, f"stale Bank-R classification remains: {stale}"

    direct = central.split("static int should_randomize_direct_grant", 1)[1]
    direct = direct.split("RECOMP_PATCH", 1)[0]
    assert "caller_is_coupled_unit_loadout" not in direct
    assert "return 0;" in direct, "future direct grants are not fail-closed"

    post_battle = consumers["post_battle"]
    assert "static unsigned char saturated_count" in post_battle
    assert "total > COUNT_MAX ? COUNT_MAX : total" in post_battle
    assert "saturated_count(count, amount)" in post_battle
    assert "saturated_count(0u, amount)" in post_battle
    assert "(count + amount) & 0xFFu" not in post_battle
    assert "amount & 0xFFu" not in post_battle

    assert "void universal_item_randomizer_force_use_repair(void)" in use_repair
    assert "full_repair_and_snapshot();" in use_repair
    assert "universal_item_randomizer_force_use_repair();" in post_battle
    for stale_duplicate in (
        "rebuild_equipment_use",
        "ROSTER_CHARS",
        "ROSTER_CLASS_TABLE",
        "class_equipment_id",
    ):
        assert stale_duplicate not in post_battle, f"post-battle duplicated use repair: {stale_duplicate}"

    assert 'recomp_get_config_u32("shops")' not in central


def main() -> int:
    for seed in (1, 2, 123456, 654321, 0xFFFFFFFF, 0xA5A5A5A5):
        for size in (1, 2, 3, 7, 15, 40, 64, 128, 277):
            assert_cycle_properties(seed, size, EQUIP_SALT)
        for size in (1, 2, 7, 15, 40):
            assert_cycle_properties(seed, size, CONSUMABLE_SALT)
            assert_cycle_properties(seed, size, KEY_SALT)

    for current, amount, expected in (
        (0, 1, 1),
        (98, 1, 99),
        (99, 1, 99),
        (99, 200, 99),
        (0, 100, 99),
        (10, 0xFFFF, 99),
    ):
        assert saturated_count(current, amount) == expected

    assert_shared_mapper_contract(Path(__file__).resolve().parents[1])
    print("universal randomizer mapping invariants: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
