#!/usr/bin/env python3
"""Boundary model for the transient +0x02 used-count repair."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mods/universal-item-randomizer/src/use_repair.c"
EQUIP_MAX = 277
CONSUMABLE_MAX = 40
CLASS_TABLE = 0x80187C62
CLASS_STRIDE = 0x48
CLASS_COUNT = 255
EQUIP_TABLE = 0x8018C42C


def clamp_use(value: int) -> int:
    return min(value, 255)


def repaired_use(item_id: int, refs: list[int], max_id: int) -> int:
    if item_id == 0 or item_id > max_id:
        return 0
    return clamp_use(refs[item_id])


def class_entry_start(class_id: int) -> int:
    return CLASS_TABLE + class_id * CLASS_STRIDE


def main() -> int:
    text = SOURCE.read_text()
    assert "#define EQUIP_SLOTS              278u" in text
    assert "#define CONSUMABLE_ID_MAX        40u" in text
    assert "#define ROSTER_CLASS_COUNT       255u" in text
    assert "if (cls >= ROSTER_CLASS_COUNT) return 0u;" in text
    assert "s_consumable_refs[CONSUMABLE_ID_MAX + 1u]" in text
    assert "value > 255u ? 255u : value" in text
    assert "id != 0u && id < EQUIP_SLOTS" in text
    assert "id != 0u && id <= CONSUMABLE_ID_MAX" in text

    # 0..254 are the complete class records that fit before the equipment table.
    last_valid = class_entry_start(CLASS_COUNT - 1)
    assert last_valid + CLASS_STRIDE <= EQUIP_TABLE
    # 0xFF would begin before the equipment table but its 0x48-byte record would
    # overlap it, so the C implementation must reject that one byte value.
    invalid_ff = class_entry_start(0xFF)
    assert invalid_ff < EQUIP_TABLE
    assert invalid_ff + CLASS_STRIDE > EQUIP_TABLE

    equip_refs = [0] * (EQUIP_MAX + 1)
    consumable_refs = [0] * (CONSUMABLE_MAX + 1)

    equip_refs[1] = 1
    equip_refs[EQUIP_MAX] = 300
    consumable_refs[1] = 2
    consumable_refs[CONSUMABLE_MAX] = 999

    assert repaired_use(0, equip_refs, EQUIP_MAX) == 0
    assert repaired_use(1, equip_refs, EQUIP_MAX) == 1
    assert repaired_use(EQUIP_MAX, equip_refs, EQUIP_MAX) == 255
    assert repaired_use(EQUIP_MAX + 1, equip_refs, EQUIP_MAX) == 0

    assert repaired_use(0, consumable_refs, CONSUMABLE_MAX) == 0
    assert repaired_use(1, consumable_refs, CONSUMABLE_MAX) == 2
    assert repaired_use(CONSUMABLE_MAX, consumable_refs, CONSUMABLE_MAX) == 255
    assert repaired_use(CONSUMABLE_MAX + 1, consumable_refs, CONSUMABLE_MAX) == 0

    # Rebuild is bookkeeping only: source contract must keep all owned id/count
    # writes out of this module.
    assert "wr16(" not in text
    assert "LIST_COUNT" not in text

    print("universal randomizer use-repair boundary model: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
