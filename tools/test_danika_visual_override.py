#!/usr/bin/env python3
"""Lock source-level invariants for the playable-Danika visual resolver.

Behavior is executed by tools/test_danika_visual_override.c.  This companion
check locks the proof comments and fail-closed structure so future refactors do
not silently broaden the override surface.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HDR = ROOT / 'mods/playable-knight-of-danika/danika_visual_override.h'
text = HDR.read_text(encoding='utf-8')

for phrase in [
    'battle_record+0x00 -> descriptor+0x50 -> func_801AD13C arg0',
    'battle_record+0x02 -> descriptor+0x4C -> class word / class id',
    '#define DANIKA_INVALID_VISUAL_SELECTOR 0xFFFFu',
    'uint8_t renderer_class_id',
    'DanikaSide side',
    'danika_should_use_player_override(renderer_class_id, side)',
    '!danika_visual_selector_is_valid(dragoon_player_visual_selector)',
    'return original_visual_selector;',
    'return dragoon_player_visual_selector;',
    'playable Danika remains class 0x71',
    'fail closed',
]:
    assert phrase in text, phrase

# The resolver is selector-only: it must not expose a class mutation primitive.
assert 'DRAGOON_CLASS_ID' not in text
assert 'renderer_class_id =' not in text

print('Danika visual override source contract: PASS')
