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
plain_doc = doc.replace("**", "")

# Stable hook only; no function replacement and no save/asset mutation surface.
assert 'RECOMP_HOOK("func_80072944")' in text
assert "RECOMP_PATCH" not in text
assert "RECOMP_FORCE_PATCH" not in text
assert not re.search(r"\bwr(?:8|16|32)\s*\(", text), "probe must not define/call RAM writers"
assert "volatile const unsigned char*" in text
assert "volatile const unsigned short*" in text
assert "volatile const unsigned int*" in text

# Lock the proven battle-record path and the fields needed for visual correlation.
for token in (
    "0x801BA6D8u",
    "0x801BA72Du",
    "0x1Au",
    "REC_SELECTOR 0x00u",
    "REC_CLASS    0x02u",
    "REC_FLAGS    0x0Cu",
    "INVALID_SELECTOR 0xFFFFu",
):
    assert token in text, f"missing battle probe contract token: {token}"

# Lock the independently verified live participant / persistent-roster bridge.
for token in (
    "LIVE_BATTLE_PTR 0x801CE8DCu",
    "CHAR_TABLE      0x80193BE0u",
    "CHAR_STRIDE     0x38u",
    "CHAR_CLASS      0x12u",
    "CHAR_COUNT      100u",
    "PART_STRIDE     0xF8u",
    "PART_OFF        0x1C4u",
    "PART_VALID      0x20Cu",
    "PART_LEVEL      0x31u",
    "PART_EXP        0x32u",
    "PART_CHARIDX    0xF6u",
    "PART_MAX        20u",
):
    assert token in text, f"missing live participant contract token: {token}"

# Unknown/invalid memory state must fail closed before dereferencing derived data.
assert text.count("valid_range(") >= 8
assert "if (!valid_range(table, 2u))" in text
assert "if (!valid_range(offset_addr, 2u))" in text
assert "if (!valid_range(group_base, BATTLE_RECORD_STRIDE))" in text
assert "if (!valid_range(record, BATTLE_RECORD_STRIDE))" in text
assert "if (!valid_range(valid_addr, 4u) || !valid_range(part, PART_STRIDE))" in text
assert "if (roster < CHAR_COUNT)" in text
assert "if (valid_range(class_addr, 1u))" in text

# Diagnostics are bounded/change-driven rather than unbounded per-frame spam.
assert "BATTLE_RECORD_MAX       24u" in text
assert "PART_MAX        20u" in text
assert "s_signature" in text and "s_seen" in text
assert "s_part_signature" in text and "s_part_seen" in text
assert "if (!s_seen[slot] || s_signature[slot] != signature)" in text
assert "if (!s_part_seen[index] || s_part_signature[index] != signature)" in text
assert "plausible_record" in text
assert "selector == 0u || selector == INVALID_SELECTOR" in text
assert "class_id != 0u && class_id != INVALID_CLASS" in text
assert "DANIKA_SNAPSHOT" in text
assert "DANIKA_PROBE" in text
assert "DANIKA_PART_SNAPSHOT" in text
assert '"DANIKA_PART"' in text
assert "new_context ? \"DANIKA_SNAPSHOT\" : \"DANIKA_PROBE\"" in text
assert "new_context ? \"DANIKA_PART_SNAPSHOT\" : \"DANIKA_PART\"" in text

# Packaging must be visibly diagnostic and disabled by default.
assert 'id = "ogre_danika_battle_probe"' in toml
assert 'display_name = "Knight of Danika - Battle Probe"' in toml
assert "enabled_by_default = false" in toml
assert 'additional_files = [ "BATTLE-PROBE.md" ]' in toml

# Documentation must preserve semantic safety constraints, independent of wording/Markdown.
assert "class `0x71`" in doc
assert "must remain `0x71`" in doc
assert "enemy Danika" in doc
assert "read-only" in plain_doc.lower()
assert "same class" in plain_doc.lower()
assert "mistaken for an ally/enemy flag" in plain_doc
assert "must be reproduced before" in plain_doc
assert "final ownership gate" in plain_doc

print("Danika battle probe safety: PASS")
print("hook=func_80072944; writes=none; patch=none; visual+participant snapshots=bounded")
