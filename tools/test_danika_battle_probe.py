#!/usr/bin/env python3
"""Static safety contract for the Knight of Danika runtime battle probe."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mods/playable-knight-of-danika/src/danika_battle_probe.c"
DOC = ROOT / "mods/playable-knight-of-danika/BATTLE-PROBE.md"
TOML = ROOT / "mods/playable-knight-of-danika/mod.toml"

text = SRC.read_text(encoding="utf-8")
doc = DOC.read_text(encoding="utf-8")
toml = TOML.read_text(encoding="utf-8")

# Stable hook only; no function replacement and no save/asset mutation surface.
assert 'RECOMP_HOOK("func_80072944")' in text
assert "RECOMP_PATCH" not in text
assert "RECOMP_FORCE_PATCH" not in text
assert not re.search(r"\bwr(?:8|16|32)\s*\(", text), "probe must not define/call RAM writers"
assert "volatile const unsigned char*" in text
assert "volatile const unsigned short*" in text
assert "volatile const unsigned int*" in text

# Lock the proven battle-record path and the fields needed for live correlation.
for token in (
    "0x801BA6D8u",  # D_801BA6D8 battle record table pointer
    "0x801BA72Du",  # current multi-mode resource group
    "0x1Au",        # record stride
    "REC_SELECTOR 0x00u",
    "REC_CLASS    0x02u",
    "REC_FLAGS    0x0Cu",
    "INVALID_SELECTOR 0xFFFFu",
):
    assert token in text, f"missing battle probe contract token: {token}"

# Unknown/invalid memory state must fail closed before dereferencing derived data.
assert text.count("valid_range(") >= 5
assert "if (!valid_range(table, 2u))" in text
assert "if (!valid_range(offset_addr, 2u))" in text
assert "if (!valid_range(group_base, BATTLE_RECORD_STRIDE))" in text
assert "if (!valid_range(record, BATTLE_RECORD_STRIDE))" in text

# Diagnostics are bounded/change-driven rather than unbounded per-frame spam.
assert "BATTLE_RECORD_MAX       24u" in text
assert "s_signature" in text and "s_seen" in text
assert "if (!s_seen[slot] || s_signature[slot] != signature)" in text
assert "DANIKA_PROBE" in text

# Packaging must be visibly diagnostic and disabled by default.
assert 'id = "ogre_danika_battle_probe"' in toml
assert 'display_name = "Knight of Danika - Battle Probe"' in toml
assert "enabled_by_default = false" in toml
assert 'additional_files = [ "BATTLE-PROBE.md" ]' in toml

# Documentation must preserve the two hard safety constraints.
assert "class `0x71`" in doc
assert "must remain `0x71`" in doc
assert "enemy Danika" in doc
assert "read-only" in doc.lower()

print("Danika battle probe safety: PASS")
print("hook=func_80072944; writes=none; patch=none; bounded_change_logs=yes")
