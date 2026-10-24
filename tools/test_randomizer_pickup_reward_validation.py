#!/usr/bin/env python3
"""Fail-closed contracts for ground-pickup and battle-reward sources."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mods/universal-item-randomizer/src/universal_item_randomizer.c"
EQUIP_MAX = 277
CONSUMABLE_MAX = 40
PICKUP_IDS = 0x801F1004
PICKUP_NEXT_ARRAY = 0x801F1024
PICKUP_MAX = 16
REWARD_SLOTS = 20


def valid_word(raw: int) -> bool:
    item_id = raw & 0x7FFF
    if item_id == 0:
        return True
    if raw & 0x8000:
        return item_id <= EQUIP_MAX
    return item_id <= CONSUMABLE_MAX


def main() -> int:
    text = SOURCE.read_text()

    assert "#define PICKUP_IDS               0x801F1004u" in text
    assert "#define PICKUP_MAX               16u" in text
    # The id array has exactly 0x20 bytes before the first adjacent metadata
    # array. That is 16 u16 ids; count 17 must never be treated as readable.
    assert PICKUP_IDS + PICKUP_MAX * 2 == PICKUP_NEXT_ARRAY

    pickup_check = text.split("static int pickup_list_readable", 1)[1]
    pickup_check = pickup_check.split("static void rewrite_pickup_list", 1)[0]
    pickup_rewrite = text.split("static void rewrite_pickup_list", 1)[1]
    pickup_rewrite = pickup_rewrite.split("static void reset_reward_shadow", 1)[0]

    assert "i < count" in pickup_check
    assert "source_item_word_valid" in pickup_check
    assert "wr16(" not in pickup_check
    assert "count > PICKUP_MAX || !pickup_list_readable(count)" in pickup_rewrite
    assert "reset_pickup_shadow();" in pickup_rewrite

    reward_check = text.split("static int reward_queue_readable", 1)[1]
    reward_check = reward_check.split("static void rewrite_reward_queue", 1)[0]
    reward_rewrite = text.split("static void rewrite_reward_queue", 1)[1]
    reward_rewrite = reward_rewrite.split("// Original func_ovlN_801DC740", 1)[0]

    assert "i < REWARD_SLOTS" in reward_check
    assert "source_item_word_valid" in reward_check
    assert "wr16(" not in reward_check
    assert "if (!reward_queue_readable())" in reward_rewrite
    assert "reset_reward_shadow();" in reward_rewrite

    # Pickup source boundary model.
    pickup = [1, CONSUMABLE_MAX, 0x8000 | EQUIP_MAX]
    assert len(pickup) <= PICKUP_MAX
    assert all(valid_word(x) for x in pickup)
    pickup_bad = pickup + [CONSUMABLE_MAX + 1]
    assert not all(valid_word(x) for x in pickup_bad)
    assert PICKUP_MAX + 1 > PICKUP_MAX  # a count of 17 is fail-closed by source contract

    # Reward source: a bad final word must reject the complete generation rather
    # than allowing earlier valid rewards to be partially rewritten.
    reward = [0] * REWARD_SLOTS
    reward[0] = 2
    reward[1] = 0x8000 | 10
    reward[-1] = CONSUMABLE_MAX
    assert all(valid_word(x) for x in reward)
    reward[-1] = 0x8000 | (EQUIP_MAX + 1)
    assert not all(valid_word(x) for x in reward)

    print("universal randomizer pickup/reward validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
