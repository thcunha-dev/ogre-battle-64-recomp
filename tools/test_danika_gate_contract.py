#!/usr/bin/env python3
"""Lock the fail-closed playable-Danika gate contract.

This is intentionally a source-contract test rather than a gameplay claim.
Identity is proven at renderer descriptor+0x4F.  Allied-side detection is not
proven yet, so UNKNOWN and ENEMY must never activate the Dragoon donor path.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
HDR=ROOT/'mods/playable-knight-of-danika/danika_gate.h'

text=HDR.read_text(encoding='utf-8')

assert '#define DANIKA_CLASS_ID 0x71u' in text
assert '#define DRAGOON_CLASS_ID 0x14u' in text
assert 'DANIKA_SIDE_UNKNOWN = 0' in text
assert 'DANIKA_SIDE_ALLIED = 1' in text
assert 'DANIKA_SIDE_ENEMY = 2' in text
assert 'renderer_class_id == DANIKA_CLASS_ID' in text
assert 'side == DANIKA_SIDE_ALLIED' in text

# Model the C truth table explicitly.
def gate(class_id:int, side:int)->bool:
    return class_id == 0x71 and side == 1

def donor(class_id:int, side:int)->int:
    return 0x14 if gate(class_id,side) else class_id

# Danika only overrides when side is independently proven allied.
assert gate(0x71,0) is False
assert gate(0x71,1) is True
assert gate(0x71,2) is False
assert donor(0x71,0)==0x71
assert donor(0x71,1)==0x14
assert donor(0x71,2)==0x71

# Never redirect unrelated classes, including actual Dragoon.
for cid in [0x00,0x01,0x14,0x70,0x72,0x9C,0xFF]:
    for side in [0,1,2]:
        assert gate(cid,side) is False
        assert donor(cid,side)==cid

# Guardrail language must stay in the executable contract.
for phrase in ['fail-closed','Camera/layout/interpolation flags are forbidden']:
    assert phrase in text

print('Danika gate contract: PASS (identity=0x71, allied-only override, unknown/enemy vanilla)')
