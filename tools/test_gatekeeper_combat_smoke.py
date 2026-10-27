#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mods/gatekeeper-combat-smoke/src/gatekeeper_combat_smoke.c"
text = SRC.read_text(encoding="utf-8")

required = [
    "#define CHAR_TABLE          0x80193BE0u",
    "#define CHAR_STRIDE         0x38u",
    "#define CHAR_CLASS          0x12u",
    "#define CHAR_COUNT          100u",
    "#define FIGHTER_CLASS_ID    0x02u",
    "#define GATEKEEPER_CLASS_ID 0x71u",
    "#define TARGET_FIGHTER_ORD  2u",
    'RECOMP_HOOK("func_80072944")',
    "if (class_id != FIGHTER_CLASS_ID)",
    "fighter_ordinal++;",
    "if (fighter_ordinal != TARGET_FIGHTER_ORD)",
    "wr8(class_addr, (unsigned char)GATEKEEPER_CLASS_ID);",
    "s_done = 1u;",
    "GATEKEEPER_SMOKE fighter2 02->71",
    "GATEKEEPER_SMOKE waiting_for_second_fighter",
]

for token in required:
    assert token in text, f"missing smoke-test safety token: {token}"

for forbidden in [
    "0x801CE8DC",  # live battle graph
    "PART_OFF",
    "PART_VALID",
    "PART_STRIDE",
    "RECOMP_PATCH(",
    "RECOMP_FORCE_PATCH(",
    "0x80187C34",  # class table must not be globally mutated in this smoke test
]:
    assert forbidden not in text, f"forbidden smoke-test token present: {forbidden}"

# Helper definition + exactly one gameplay call.
assert text.count("wr8(") == 2, "expected helper plus one class-byte write"
assert text.count("*(volatile unsigned char*)address = value;") == 1
assert not re.search(r"\*\s*\(volatile\s+(?:unsigned\s+)?(?:short|int)\s*\*\).*?=", text)

# Ensure targeting really is second Fighter, not fixed roster slot 1.
assert "fighter_ordinal = 0u" in text
inc = text.index("fighter_ordinal++;")
ord_guard = text.index("if (fighter_ordinal != TARGET_FIGHTER_ORD)", inc)
write = text.index("wr8(class_addr, (unsigned char)GATEKEEPER_CLASS_ID);", ord_guard)
assert inc < ord_guard < write
assert "CHAR_TABLE + i * CHAR_STRIDE + CHAR_CLASS" in text

# Missing target remains read-only and retryable.
wait = text.index("if (!s_logged_waiting)")
assert "s_done = 1u;" not in text[wait:]

print("Gatekeeper combat smoke safety contract: OK")
