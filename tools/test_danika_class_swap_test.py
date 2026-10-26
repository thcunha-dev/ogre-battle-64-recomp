#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mods/playable-knight-of-danika-class-swap-test/src/danika_class_swap_test.c"
text = SRC.read_text(encoding="utf-8")

required = [
    "#define CHAR_TABLE        0x80193BE0u",
    "#define CHAR_STRIDE       0x38u",
    "#define CHAR_CLASS        0x12u",
    "#define CHAR_COUNT        100u",
    "#define DRAGOON_CLASS_ID  0x14u",
    "#define DANIKA_CLASS_ID   0x71u",
    'RECOMP_HOOK("func_80072944")',
    "if (class_id == DRAGOON_CLASS_ID)",
    "wr8(class_addr, (unsigned char)DANIKA_CLASS_ID);",
    "if (s_attempted)",
    "s_attempted = 1u;",
]

for token in required:
    assert token in text, f"missing safety token: {token}"

# The isolated smoke-test must not inspect the live battle/enemy participant
# graph at all. Ownership proof is deliberately irrelevant here because the
# write target is the already-proven persistent player roster.
for forbidden in [
    "0x801CE8DC",  # live battle ptr
    "PART_OFF",
    "PART_VALID",
    "PART_STRIDE",
    "RECOMP_PATCH(",
    "RECOMP_FORCE_PATCH(",
]:
    assert forbidden not in text, f"forbidden test path token present: {forbidden}"

# Exactly one explicit gameplay write call is allowed, and it must be the
# guarded roster class-byte write shown above. The helper itself contains the
# underlying volatile assignment; no other raw volatile write may exist.
assert text.count("wr8(") == 2, "expected helper definition plus exactly one call"
assert text.count("*(volatile unsigned char*)address = value;") == 1
assert not re.search(r"\*\s*\(volatile\s+(?:unsigned\s+)?(?:short|int)\s*\*\).*?=", text)

# No global class table mutation: class 0x71 is assigned only into one roster
# record's +0x12 byte after an exact 0x14 guard.
guard = text.index("if (class_id == DRAGOON_CLASS_ID)")
write = text.index("wr8(class_addr, (unsigned char)DANIKA_CLASS_ID);")
assert guard < write
assert "CHAR_TABLE + i * CHAR_STRIDE + CHAR_CLASS" in text

print("Danika allied class-swap test safety contract: OK")
