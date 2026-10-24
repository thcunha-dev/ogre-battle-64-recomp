#!/usr/bin/env python3
"""Model the native central-grant a1 -> consumable +0x02 semantics."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mods/universal-item-randomizer/src/universal_item_randomizer.c"
COUNT_MAX = 99


def existing(count: int, use: int, used_flag: int) -> tuple[int, int]:
    next_count = count + 1 if count < COUNT_MAX else COUNT_MAX
    if used_flag & 0xFF:
        next_use = (use + 1) & 0xFF
        if next_use > next_count:
            next_use = next_count
    else:
        next_use = use
    return next_count, next_use


def new_slot(stale_use: int, used_flag: int) -> tuple[int, int]:
    return 1, 1 if (used_flag & 0xFF) else stale_use


def main() -> int:
    text = SOURCE.read_text()

    # Rev-A disassembly contract: a1 low byte is meaningful only for the
    # consumable branch. Equipment must deliberately pass zero to the helper.
    assert "#define LIST_USE                 2u" in text
    assert "void func_ovlN_801DC740(unsigned int item_word, unsigned int used_flag)" in text
    assert "grant_vanilla(EQUIP_LIST, EQUIP_SLOTS, id, 0u);" in text
    assert "grant_vanilla(CONSUMABLE_LIST, CONSUMABLE_SLOTS, id, used_flag & 0xFFu);" in text
    assert "if (used_flag != 0u)" in text
    assert "if (use > next_count) use = next_count;" in text

    # Existing consumable stack: count always grows/caps; use grows only when
    # a1 low byte is non-zero and may never exceed the resulting count.
    assert existing(5, 2, 0) == (6, 2)
    assert existing(5, 2, 1) == (6, 3)
    assert existing(98, 98, 1) == (99, 99)
    assert existing(99, 99, 1) == (99, 99)
    assert existing(99, 120, 1) == (99, 99)
    assert existing(99, 255, 1) == (99, 0)  # native byte increment wrap, then clamp if needed

    # New slot: native grant writes count=1; a1!=0 also initializes use=1.
    # With a1==0 the native routine leaves stale +0x02 untouched, which the
    # frame repair later rebuilds from the roster.
    assert new_slot(7, 0) == (1, 7)
    assert new_slot(7, 1) == (1, 1)
    assert new_slot(7, 0x100) == (1, 7)  # only low byte matters
    assert new_slot(7, 0x101) == (1, 1)

    print("central grant used-flag model: PASS (consumable a1 semantics locked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
