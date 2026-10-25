#!/usr/bin/env python3
"""Model fixed-slot acquisition semantics at inventory capacity boundaries."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COUNT_MAX = 99
EQUIP_ID_MAX = 277
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


def add_equipment_amount(records: list[list[int]], item_id: int, amount: int) -> None:
    if item_id == 0 or item_id > EQUIP_ID_MAX or amount == 0:
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
    add_equipment_amount(records, 9999, 12)
    assert records == before, "invalid post-battle id changed a full inventory"

    records[100][1] = 95
    item_id = records[100][0]
    add_equipment_amount(records, item_id, 250)
    assert records[100][1] == 99


def test_first_empty_slot_and_zero_noop() -> None:
    records = full_records(10)
    records[3] = [0, 0]
    records[7] = [0, 0]
    add_equipment_amount(records, 77, 150)
    assert records[3] == [77, 99]
    assert records[7] == [0, 0]

    snapshot = [r[:] for r in records]
    add_equipment_amount(records, 0, 4)
    add_equipment_amount(records, 78, 0)
    add_equipment_amount(records, EQUIP_ID_MAX + 1, 1)
    add_equipment_amount(records, 0xFFFF, 1)
    assert records == snapshot


def test_source_contract() -> None:
    text = (ROOT / "mods/universal-item-randomizer/src/post_battle_add.c").read_text()
    assert "#define EQUIP_ID_MAX             277u" in text
    assert "original_id > EQUIP_ID_MAX" in text
    assert "id > EQUIP_ID_MAX" in text


def main() -> int:
    test_main_grant_full_inventory()
    test_post_battle_full_inventory()
    test_first_empty_slot_and_zero_noop()
    test_source_contract()
    print("universal randomizer inventory-capacity model: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
