#!/usr/bin/env python3
"""Boundary model for the transient +0x02 used-count repair."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mods/universal-item-randomizer/src/use_repair.c"
EQUIP_MAX = 277
CONSUMABLE_MAX = 40


def clamp_use(value: int) -> int:
    return min(value, 255)


def repaired_use(item_id: int, refs: list[int], max_id: int) -> int:
    if item_id == 0 or item_id > max_id:
        return 0
    return clamp_use(refs[item_id])


def main() -> int:
    text = SOURCE.read_text()
    assert "#define EQUIP_SLOTS              278u" in text
    assert "#define CONSUMABLE_ID_MAX        40u" in text
    assert "s_consumable_refs[CONSUMABLE_ID_MAX + 1u]" in text
    assert "value > 255u ? 255u : value" in text
    assert "id != 0u && id < EQUIP_SLOTS" in text
    assert "id != 0u && id <= CONSUMABLE_ID_MAX" in text

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
