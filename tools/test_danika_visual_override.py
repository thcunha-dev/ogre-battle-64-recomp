#!/usr/bin/env python3
"""Lock the playable-Danika visual selector override truth table."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HDR=ROOT/'mods/playable-knight-of-danika/danika_visual_override.h'
text=HDR.read_text(encoding='utf-8')

for phrase in [
    'battle_record+0x00 -> descriptor+0x50 -> func_801AD13C arg0',
    'dragoon_player_visual_selector == 0u',
    'danika_should_use_player_override(renderer_class_id, side)',
    'return original_visual_selector;',
    'return dragoon_player_visual_selector;',
]:
    assert phrase in text, phrase

UNKNOWN=0; ALLIED=1; ENEMY=2

def gate(cid,side):
    return cid==0x71 and side==ALLIED

def select(cid,side,original,donor):
    if not gate(cid,side):
        return original
    if donor==0:
        return original
    return donor

# Unresolved donor is always vanilla, even for allied Danika.
assert select(0x71,ALLIED,0x1234,0)==0x1234
# The only allowed substitution is allied class 0x71 with a resolved donor.
assert select(0x71,ALLIED,0x1234,0x0042)==0x0042
# Enemy and unknown Danika never change.
assert select(0x71,ENEMY,0x1234,0x0042)==0x1234
assert select(0x71,UNKNOWN,0x1234,0x0042)==0x1234
# Actual Dragoon and every unrelated class are untouched.
for cid in [0x00,0x01,0x14,0x70,0x72,0x9C,0xFF]:
    for side in [UNKNOWN,ALLIED,ENEMY]:
        assert select(cid,side,0x1234,0x0042)==0x1234

print('Danika visual override contract: PASS (0x71 + allied + resolved donor only)')
