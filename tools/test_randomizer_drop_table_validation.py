#!/usr/bin/env python3
"""Fail-closed model/contract for the 35x3 Table-O item payload."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mods/universal-item-randomizer/src/universal_item_randomizer.c"
ENTRIES = 35
COLUMNS = 3
EQUIP_MAX = 277
CONSUMABLE_MAX = 40


def valid_word(raw: int) -> bool:
    item_id = raw & 0x7FFF
    if item_id == 0:
        return True
    if raw & 0x8000:
        return item_id <= EQUIP_MAX
    return item_id <= CONSUMABLE_MAX


def table_valid(words: list[int]) -> bool:
    assert len(words) == ENTRIES * COLUMNS
    return all(valid_word(raw) for raw in words)


def main() -> int:
    text = SOURCE.read_text()
    readable = text.split("static int drop_table_readable", 1)[1]
    readable = readable.split("static void reset_drop_shadow", 1)[0]
    rewrite = text.split("static void rewrite_drop_table", 1)[1]
    rewrite = rewrite.split("static void reset_pickup_shadow", 1)[0]

    assert "static int source_item_word_valid" in text
    assert "entry < DROP_ENTRY_MAX" in readable
    assert "column < 3u" in readable
    assert "source_item_word_valid(raw)" in readable
    assert "wr16(" not in readable, "validation must not mutate Table O"
    assert "drop_table_present() && drop_table_readable()" in rewrite

    vanilla = [0] * (ENTRIES * COLUMNS)
    vanilla[0] = 1
    vanilla[1] = 40
    vanilla[2] = 0x8000 | 1
    vanilla[-1] = 0x8000 | EQUIP_MAX
    assert table_valid(vanilla)

    # Invalid consumable in the final word: whole source must be rejected before
    # any earlier valid word can be considered safe to rewrite.
    bad_consumable = list(vanilla)
    bad_consumable[-1] = CONSUMABLE_MAX + 1
    assert not table_valid(bad_consumable)

    bad_equipment = list(vanilla)
    bad_equipment[-1] = 0x8000 | (EQUIP_MAX + 1)
    assert not table_valid(bad_equipment)

    # Boundaries remain valid.
    assert valid_word(CONSUMABLE_MAX)
    assert valid_word(0x8000 | EQUIP_MAX)
    assert valid_word(0)

    print("universal randomizer Table-O validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
