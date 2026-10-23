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

    # Key items are identity-mapped unless the explicit key_items option is on.
    # Only the audited quest/key classes 3..4 may enter the key pool. Unknown
    # classes must remain identity even when KEY ITEMS is enabled.
    assert 'recomp_get_config_u32("key_items")' in mapper
    assert "#define CONSUMABLE_KEY_MIN       3u" in mapper
    assert "#define CONSUMABLE_KEY_MAX       4u" in mapper
    assert "cls >= CONSUMABLE_KEY_MIN && cls <= CONSUMABLE_KEY_MAX" in mapper
    assert "if (s_key_items_enabled)" in mapper
    assert "build_cycle_map(s_consumable_map, key_pool" in mapper
    assert "Unknown classes are intentionally omitted" in mapper

    # The consumable table has ids 0..40 even though the owned inventory has 40
    # records. Reference counters are indexed by item id, so id 40 requires a
    # 41-element table and inclusive bounds. A 40-element array silently loses
    # the use count of the final valid consumable id.
    assert "#define CONSUMABLE_ID_MAX        40u" in use_repair
    assert "s_consumable_refs[CONSUMABLE_ID_MAX + 1u]" in use_repair
    assert "i <= CONSUMABLE_ID_MAX" in use_repair
    assert "id <= CONSUMABLE_ID_MAX" in use_repair
    assert "s_consumable_refs[CONSUMABLE_SLOTS]" not in use_repair
    assert "id < CONSUMABLE_SLOTS" not in use_repair

    # The post-battle route must clamp in wide arithmetic before narrowing to
    # u8. The old '& 0xFF' path could wrap a large award below 99.
    post_battle = consumers["post_battle"]
    assert "static unsigned char saturated_count" in post_battle
    assert "total > COUNT_MAX ? COUNT_MAX : total" in post_battle
    assert "saturated_count(count, amount)" in post_battle
    assert "saturated_count(0u, amount)" in post_battle
    assert "(count + amount) & 0xFFu" not in post_battle
    assert "amount & 0xFFu" not in post_battle

    # Shops have a dedicated Bank-AB source path. The Bank-N replacement must
    # never use shops=ON as permission to randomize an unclassified caller.
    central = consumers["central"]
    assert 'recomp_get_config_u32("shops")' not in central
    direct = central.split("static int should_randomize_direct_grant", 1)[1]
    direct = direct.split("RECOMP_PATCH", 1)[0]
    assert "return 0;" in direct, "unknown direct grants are not fail-closed"


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
