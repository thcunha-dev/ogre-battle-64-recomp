#!/usr/bin/env python3
"""Fail-closed contracts for the two owned-item grant replacements."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CENTRAL = ROOT / "mods/universal-item-randomizer/src/universal_item_randomizer.c"
POST = ROOT / "mods/universal-item-randomizer/src/post_battle_add.c"
EQUIP_MAX = 277
CONSUMABLE_MAX = 40


def valid_word(raw: int) -> bool:
    item_id = raw & 0x7FFF
    if item_id == 0:
        return True
    if raw & 0x8000:
        return item_id <= EQUIP_MAX
    return item_id <= CONSUMABLE_MAX


def main() -> int:
    central = CENTRAL.read_text()
    body = central.split("void func_ovlN_801DC740", 1)[1]
    body = body.split("RECOMP_HOOK", 1)[0]

    assert "if (!source_item_word_valid(raw)) return;" in body
    assert "if (!source_item_word_valid(delivered)) return;" in body
    assert body.index("if (!source_item_word_valid(raw)) return;") < body.index("grant_vanilla(")
    assert body.index("if (!source_item_word_valid(delivered)) return;") < body.index("grant_vanilla(")

    # Main-grant vanilla bounds.
    assert valid_word(0)
    assert valid_word(CONSUMABLE_MAX)
    assert valid_word(0x8000 | EQUIP_MAX)
    assert not valid_word(CONSUMABLE_MAX + 1)
    assert not valid_word(0x8000 | (EQUIP_MAX + 1))
    assert not valid_word(0xFFFF)

    post = POST.read_text()
    post_body = post.split("void func_80172820", 1)[1]
    assert "original_id > EQUIP_ID_MAX" in post_body
    assert "id > EQUIP_ID_MAX" in post_body
    assert post_body.index("original_id > EQUIP_ID_MAX") < post_body.index("uir_map_equipment_id")
    assert post_body.index("id > EQUIP_ID_MAX") < post_body.index("wr16(")

    print("universal randomizer grant validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
