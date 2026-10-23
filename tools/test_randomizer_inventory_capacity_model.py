#!/usr/bin/env python3
"""Model fixed-slot acquisition semantics at inventory capacity boundaries."""

from __future__ import annotations

COUNT_MAX = 99
EQUIP_SLOTS = 278
CONSUMABLE_SLOTS = 40


def add_one(records: list[list[int]], item_id: int) -> None:
    empty = None
    for i, rec in enumerate(records):
        slot_id, count = rec
        if slot_id == item_id:
            if count < COUNT_MAX:
                rec[1] = count + 1
            return
        if slot_id == 0 and empty is None:
            empty = i
    if empty is not None:
        records[empty] = [item_id, 1]


def add_amount(records: list[list[int]], item_id: int, amount: int) -> None:
    if item_id == 0 or amount == 0:
        return
    empty = None
    for i, rec in enumerate(records):
        slot_id, count = rec
        if slot_id == item_id:
            rec[1] = min(COUNT_MAX, count + amount)
            return
        if slot_id == 0 and empty is None:
            empty = i
    if empty is not None:
        records[empty] = [item_id, min(COUNT_MAX, amount)]


def full_records(slots: int, start_id: int = 1) -> list[list[int]]:
    return [[start_id + i, 1] for i in range(slots)]


def test_main_grant_full_inventory() -> None:
    records = full_records(CONSUMABLE_SLOTS)
    before = [r[:] for r in records]
    add_one(records, 999)
    assert records == before, "full central inventory overwrote an occupied slot"

    # Existing stack still increments even when there is no empty slot.
    records[17][1] = 98
    add_one(records, records[17][0])
    assert records[17][1] == 99
    add_one(records, records[17][0])
    assert records[17][1] == 99


def test_post_battle_full_inventory() -> None:
    records = full_records(EQUIP_SLOTS)
    before = [r[:] for r in records]
    add_amount(records, 9999, 12)
    assert records == before, "full post-battle inventory overwrote an occupied slot"

    records[100][1] = 95
    item_id = records[100][0]
    add_amount(records, item_id, 250)
    assert records[100][1] == 99


def test_first_empty_slot_and_zero_noop() -> None:
    records = full_records(10)
    records[3] = [0, 0]
    records[7] = [0, 0]
    add_amount(records, 777, 150)
    assert records[3] == [777, 99]
    assert records[7] == [0, 0]

    snapshot = [r[:] for r in records]
    add_amount(records, 0, 4)
    add_amount(records, 778, 0)
    assert records == snapshot


def main() -> int:
    test_main_grant_full_inventory()
    test_post_battle_full_inventory()
    test_first_empty_slot_and_zero_noop()
    print("universal randomizer inventory-capacity model: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
