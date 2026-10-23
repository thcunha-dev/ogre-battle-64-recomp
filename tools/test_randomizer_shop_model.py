#!/usr/bin/env python3
"""Host-side model of the Bank-AB shop source rewrite.

The real mod rewrites the raw zero-terminated item_word source before Bank AB
builds UI/detail/price/purchase caches.  These tests protect the important
properties without emulating the shop code itself:

* equipment bit15/list class is preserved;
* consumables stay consumables and equipment stays equipment;
* the zero terminator is never rewritten;
* the vanilla 1,2,3,4,5,6,8 signature makes each freshly-built stock map once;
* the already-mapped stock no longer matches that signature, preventing a second
  pass from applying map(map(item));
* a newly allocated vanilla stock maps again deterministically.
"""

from __future__ import annotations

from test_universal_randomizer_mapping import CONSUMABLE_SALT, EQUIP_SALT, cycle

EQUIP_FLAG = 0x8000
EQUIP_IDS = list(range(1, 278))
CONSUMABLE_IDS = list(range(1, 41))
SIGNATURE = [1, 2, 3, 4, 5, 6, 8]
SEED = 0x0B640301

EQUIP_MAP = cycle(SEED, EQUIP_IDS, EQUIP_SALT)
CONSUMABLE_MAP = cycle(SEED, CONSUMABLE_IDS, CONSUMABLE_SALT)


def map_item_word(raw: int) -> int:
    if raw == 0:
        return 0
    item_id = raw & 0x7FFF
    if raw & EQUIP_FLAG:
        assert item_id in EQUIP_MAP
        return EQUIP_FLAG | EQUIP_MAP[item_id]
    assert item_id in CONSUMABLE_MAP
    return CONSUMABLE_MAP[item_id]


def has_vanilla_signature(stock: list[int]) -> bool:
    return len(stock) >= len(SIGNATURE) and stock[: len(SIGNATURE)] == SIGNATURE


def validate_stock(stock: list[int]) -> int:
    for i, raw in enumerate(stock):
        if raw == 0:
            return i
        item_id = raw & 0x7FFF
        if raw & EQUIP_FLAG:
            if item_id not in EQUIP_MAP:
                return 0
        elif item_id not in CONSUMABLE_MAP:
            return 0
    return 0


def rewrite_once(stock: list[int]) -> list[int]:
    if not has_vanilla_signature(stock):
        return list(stock)
    count = validate_stock(stock)
    if count < len(SIGNATURE):
        return list(stock)
    out = list(stock)
    for i in range(count):
        out[i] = map_item_word(out[i])
    return out


def test_shop_stock() -> None:
    vanilla = SIGNATURE + [9, 10, EQUIP_FLAG | 1, EQUIP_FLAG | 40, EQUIP_FLAG | 277, 0]
    mapped = rewrite_once(vanilla)

    assert mapped != vanilla
    assert mapped[-1] == 0
    assert all((mapped[i] & EQUIP_FLAG) == 0 for i in range(9))
    assert all((mapped[i] & EQUIP_FLAG) != 0 for i in range(9, 12))
    assert all(1 <= (mapped[i] & 0x7FFF) <= 40 for i in range(9))
    assert all(1 <= (mapped[i] & 0x7FFF) <= 277 for i in range(9, 12))

    # Sattolo has no fixed points for this pool, so the vanilla signature is
    # destroyed after the first pass and the second frame must be stable.
    assert not has_vanilla_signature(mapped)
    assert rewrite_once(mapped) == mapped

    # A fresh shop allocation with the same vanilla source maps identically.
    assert rewrite_once(list(vanilla)) == mapped


def test_invalid_or_unterminated_stock_fails_closed() -> None:
    invalid_consumable = SIGNATURE + [41, 0]
    invalid_equipment = SIGNATURE + [EQUIP_FLAG | 278, 0]
    unterminated = SIGNATURE + [9, 10, 11]

    assert rewrite_once(invalid_consumable) == invalid_consumable
    assert rewrite_once(invalid_equipment) == invalid_equipment
    assert rewrite_once(unterminated) == unterminated


def main() -> int:
    test_shop_stock()
    test_invalid_or_unterminated_stock_fails_closed()
    print("universal randomizer shop-source model: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
