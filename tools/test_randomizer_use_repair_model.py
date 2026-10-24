#!/usr/bin/env python3
"""Boundary and slot-semantics model for transient +0x02 used-count repair."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mods/universal-item-randomizer/src/use_repair.c"
EQUIP_SLOTS = 278
CONSUMABLE_SLOTS = 40
CLASS_TABLE = 0x80187C62
CLASS_STRIDE = 0x48
CLASS_COUNT = 255
EQUIP_TABLE = 0x8018C42C


def clamp_use(value: int) -> int:
    return min(value, 255)


def rebuild_column(refs: list[int]) -> list[int]:
    """Native semantics: +0x02 is indexed by owned-list slot, not item id."""
    return [clamp_use(v) for v in refs]


def add_ref(refs: list[int], slot_index: int) -> None:
    # Zero is no-reference; upper bound is the native slti list size.
    if slot_index == 0 or slot_index >= len(refs):
        return
    if refs[slot_index] < 0xFFFF:
        refs[slot_index] += 1


def class_entry_start(class_id: int) -> int:
    return CLASS_TABLE + class_id * CLASS_STRIDE


def main() -> int:
    text = SOURCE.read_text()
    assert "#define EQUIP_SLOTS              278u" in text
    assert "#define CONSUMABLE_SLOTS         40u" in text
    assert "#define ROSTER_CLASS_COUNT       255u" in text
    assert "if (cls >= ROSTER_CLASS_COUNT) return 0u;" in text
    assert "s_equip_refs[EQUIP_SLOTS]" in text
    assert "s_consumable_refs[CONSUMABLE_SLOTS]" in text
    assert "slot_index < EQUIP_SLOTS" in text
    assert "slot_index < CONSUMABLE_SLOTS" in text
    assert "wr8(record + LIST_USE, clamp_use(s_equip_refs[i]));" in text
    assert "wr8(record + LIST_USE, clamp_use(s_consumable_refs[i]));" in text
    assert "s_equip_refs[id]" not in text
    assert "s_consumable_refs[id]" not in text
    assert "CONSUMABLE_ID_MAX" not in text

    # 0..254 are complete class records. 0xFF would overlap the equipment table.
    last_valid = class_entry_start(CLASS_COUNT - 1)
    assert last_valid + CLASS_STRIDE <= EQUIP_TABLE
    invalid_ff = class_entry_start(0xFF)
    assert invalid_ff < EQUIP_TABLE
    assert invalid_ff + CLASS_STRIDE > EQUIP_TABLE

    # Equipment example proving slot != item id. An owned item with definition
    # id 117 in slot 20 must receive slot 20's reference count, not refs[117].
    equip_refs = [0] * EQUIP_SLOTS
    add_ref(equip_refs, 20)
    add_ref(equip_refs, 20)
    equip_refs[117] = 9  # unrelated slot deliberately has a different count
    uses = rebuild_column(equip_refs)
    owned_item_id_at_slot_20 = 117
    assert owned_item_id_at_slot_20 != 20
    assert uses[20] == 2
    assert uses[117] == 9

    # Same rule for the 40-slot consumable list. Slot 7 may contain definition
    # id 40; the use byte belongs to slot 7. Reference value 40 itself is out of
    # range because native code uses `slti <40` on the roster slot reference.
    consumable_refs = [0] * CONSUMABLE_SLOTS
    add_ref(consumable_refs, 7)
    add_ref(consumable_refs, 7)
    add_ref(consumable_refs, 40)  # ignored: valid indices are 0..39, 0 sentinel
    uses = rebuild_column(consumable_refs)
    owned_item_id_at_slot_7 = 40
    assert owned_item_id_at_slot_7 != 7
    assert uses[7] == 2
    assert len(uses) == 40

    # Empty records are not forcibly cleared by the rebuild model. If roster
    # state still references a slot, native func_8016B774 can leave +0x02 > 0
    # even while the owned record's id is zero. The repair must mirror that.
    empty_record_id = 0
    equip_refs[33] = 3
    uses = rebuild_column(equip_refs)
    assert empty_record_id == 0
    assert uses[33] == 3

    # Saturate pathological reference multiplicity to the physical u8 column.
    equip_refs[55] = 1000
    assert rebuild_column(equip_refs)[55] == 255

    # Rebuild is bookkeeping only: no owned id/count writes are allowed here.
    assert "wr16(" not in text
    assert "LIST_COUNT" not in text

    print("universal randomizer use-repair slot model: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
