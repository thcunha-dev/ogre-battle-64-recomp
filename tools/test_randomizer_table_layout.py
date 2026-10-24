#!/usr/bin/env python3
"""RAM table-layout boundary contract for Universal Item Randomizer."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPPER = (ROOT / "mods/universal-item-randomizer/src/randomizer_map.c").read_text()
REPAIR = (ROOT / "mods/universal-item-randomizer/src/use_repair.c").read_text()

CLASS_TABLE = 0x80187C62
CLASS_STRIDE = 0x48
CLASS_COUNT = 255
EQUIP_TABLE = 0x8018C42C
EQUIP_STRIDE = 0x20
EQUIP_MAX = 277
CONSUMABLE_TABLE = 0x8018E6EC
CONSUMABLE_STRIDE = 0x0C
CONSUMABLE_MAX = 40


def main() -> int:
    # Source constants must remain aligned with the audited Rev-A layout.
    for token in (
        "#define EQUIP_TABLE              0x8018C42Cu",
        "#define EQUIP_TABLE_STRIDE       0x20u",
        "#define EQUIP_ID_MAX             277u",
        "#define CONSUMABLE_TABLE         0x8018E6ECu",
        "#define CONSUMABLE_TABLE_STRIDE  0x0Cu",
        "#define CONSUMABLE_ID_MAX        40u",
    ):
        assert token in MAPPER, f"mapper layout drift: {token}"

    for token in (
        "#define ROSTER_CLASS_TABLE       0x80187C62u",
        "#define ROSTER_CLASS_STRIDE      0x48u",
        "#define ROSTER_CLASS_COUNT       255u",
    ):
        assert token in REPAIR, f"class layout drift: {token}"

    # Class ids 0..254 occupy complete records. The next hypothetical class
    # record would begin only 0x12 bytes before the equipment table and would
    # overlap it, so 0xFF must remain invalid.
    class_valid_end = CLASS_TABLE + CLASS_COUNT * CLASS_STRIDE
    assert class_valid_end == 0x8018C41A
    assert class_valid_end < EQUIP_TABLE
    assert EQUIP_TABLE - class_valid_end == 0x12
    assert class_valid_end + CLASS_STRIDE > EQUIP_TABLE

    # Equipment records are indexed 0..277. The byte immediately after record
    # 277 is exactly the consumable-table base. Therefore 278 cannot be admitted
    # as an equipment id without reading the next table as an equipment record.
    equip_end = EQUIP_TABLE + (EQUIP_MAX + 1) * EQUIP_STRIDE
    assert equip_end == CONSUMABLE_TABLE
    assert EQUIP_TABLE + EQUIP_MAX * EQUIP_STRIDE == 0x8018E6CC

    # Highest supported consumable id must still be a complete 0x0C record from
    # the audited base. This does not guess the next table; it locks the current
    # final-record address and prevents accidental off-by-one expansion.
    consumable_40 = CONSUMABLE_TABLE + CONSUMABLE_MAX * CONSUMABLE_STRIDE
    assert consumable_40 == 0x8018E8CC
    assert consumable_40 + CONSUMABLE_STRIDE == 0x8018E8D8

    print("universal randomizer Rev-A RAM table layout: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
