#!/usr/bin/env python3
"""Static safety contract for the Knight of Danika runtime battle probe."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mods/playable-knight-of-danika/src/danika_battle_probe.c"
BANKJ = ROOT / "mods/playable-knight-of-danika/src/danika_bankj_probe.c"
BANKC = ROOT / "mods/playable-knight-of-danika/src/danika_bankc_probe.c"
BANKAH = ROOT / "mods/playable-knight-of-danika/src/danika_bankah_probe.c"
JOIN = ROOT / "mods/playable-knight-of-danika/src/danika_join_probe.c"
DOC = ROOT / "mods/playable-knight-of-danika/BATTLE-PROBE.md"
TOML = ROOT / "mods/playable-knight-of-danika/mod.toml"

text = SRC.read_text(encoding="utf-8")
bankj = BANKJ.read_text(encoding="utf-8")
bankc = BANKC.read_text(encoding="utf-8")
bankah = BANKAH.read_text(encoding="utf-8")
join = JOIN.read_text(encoding="utf-8")
doc = DOC.read_text(encoding="utf-8")
toml = TOML.read_text(encoding="utf-8")
plain_doc = doc.replace("**", "")

assert 'RECOMP_HOOK("func_80072944")' in text
assert len(re.findall(r"RECOMP_HOOK\s*\(", text)) == 1
assert 'RECOMP_HOOK_RETURN("func_8009DA50")' in bankah
assert len(re.findall(r"RECOMP_HOOK_RETURN\s*\(", bankah)) == 1
for source_name, source in (
    ("battle probe", text),
    ("bank-J probe", bankj),
    ("bank-C probe", bankc),
    ("bank-AH probe", bankah),
    ("descriptor/participant join probe", join),
):
    assert not re.search(r"RECOMP_(?:PATCH|FORCE_PATCH)\s*\(", source), source_name
    assert not re.search(r"\bwr(?:8|16|32)\s*\(", source), f"{source_name} must not write RAM"
assert not re.search(r"RECOMP_HOOK(?:_RETURN)?\s*\(", bankj)
assert not re.search(r"RECOMP_HOOK(?:_RETURN)?\s*\(", bankc)
assert not re.search(r"RECOMP_HOOK(?:_RETURN)?\s*\(", join)
assert "danika_bankj_probe_tick();" in text
assert "danika_bankc_probe_tick();" in bankj
assert "danika_join_probe_tick();" in bankj

for token in (
    "0x801BA6D8u", "0x801BA72Du", "0x1Au", "REC_SELECTOR 0x00u",
    "REC_CLASS    0x02u", "REC_FLAGS    0x0Cu", "INVALID_SELECTOR 0xFFFFu",
):
    assert token in text, f"missing battle probe contract token: {token}"

for token in (
    "LIVE_BATTLE_PTR 0x801CE8DCu", "CHAR_TABLE      0x80193BE0u",
    "CHAR_STRIDE     0x38u", "CHAR_CLASS      0x12u", "CHAR_COUNT      100u",
    "PART_STRIDE     0xF8u", "PART_OFF        0x1C4u", "PART_VALID      0x20Cu",
    "PART_LEVEL      0x31u", "PART_EXP        0x32u", "PART_CHARIDX    0xF6u",
    "PART_MAX        20u",
):
    assert token in text, f"missing live participant contract token: {token}"

for token in (
    "DESC_BASE_PTR   0x801BA690u", "DESC_COUNT      0x801BA694u",
    "DESC_STRIDE     0xF8u", "DESC_CLASS      0x4Cu", "DESC_SELECTOR   0x50u",
    "LIVE_BATTLE_PTR 0x801CE8DCu", "PART_STRIDE     0xF8u", "PART_OFF        0x1C4u",
    "PART_VALID      0x20Cu", "PART_CHARIDX    0xF6u", "PART_MAX        20u",
    "CHAR_TABLE      0x80193BE0u", "CHAR_STRIDE     0x38u", "CHAR_CLASS      0x12u",
    '"DANIKA_JOIN i="', '" classmatch="',
):
    assert token in join, f"missing descriptor/participant join token: {token}"
assert "dclass == rclass" in join
assert "count > PART_MAX" in join

for token in (
    "LIVE_BATTLE_PTR 0x801CE8DCu", "BANKJ_SYNC_RECORD_TO_PART 0x801D8DC4u",
    "BANKJ_SYNC_RECORD_TO_PART_SIZE 0xCCu", "BANKJ_SYNC_PART_TO_RECORD 0x801D8E90u",
    "BANKJ_SYNC_PART_TO_RECORD_SIZE 0x180u", "BANKJ_DUMP_CHUNK 16u",
    '"DANIKA_BANKJ name="',
):
    assert token in bankj, f"missing bank-J probe contract token: {token}"
assert "s_dumped_for_base == base" in bankj
assert "window_has_signal" in bankj
assert "log_window(\"record_to_part\"" in bankj
assert "log_window(\"part_to_record\"" in bankj

for token in (
    "LIVE_BATTLE_PTR 0x801CE8DCu", "BANKC_FILTER_BLOCK      0x801C8B80u",
    "BANKC_FILTER_BLOCK_SIZE 0x500u", "BANKC_DUMP_CHUNK        16u",
    '"DANIKA_BANKC name=exp_filters addr="',
):
    assert token in bankc, f"missing bank-C probe contract token: {token}"
for address in ("func_801C9008", "func_801C8BA4", "func_801C8E50", "func_801C8EBC", "func_801C8B88", "func_801C8C5C"):
    assert address in bankc, f"missing documented EXP-filter symbol: {address}"
assert "s_dumped_for_base == base" in bankc
assert "window_has_signal" in bankc

for token in (
    "BANKAH_ROM_START 0x0023A370u", "BANKAH_RAM_START 0x801D0860u",
    "BANKAH_SIZE      0x00000E80u", "BANKAH_CODE_SIZE 0x00000E70u",
    "BANKAH_DUMP_CHUNK 16u", '"DANIKA_BANKAH addr="',
    '"DANIKA_BANKAH_CAPTURE rom=0023A370 ram=801D0860 size=00000E80"',
):
    assert token in bankah, f"missing bank-AH probe contract token: {token}"
assert "rom != BANKAH_ROM_START || ram != BANKAH_RAM_START" in bankah
assert "size != BANKAH_SIZE" in bankah
assert "s_dumped != 0u" in bankah
assert "window_has_signal(BANKAH_RAM_START, BANKAH_CODE_SIZE)" in bankah

assert text.count("valid_range(") >= 8
assert "if (!valid_range(table, 2u))" in text
assert "if (!valid_range(offset_addr, 2u))" in text
assert "if (!valid_range(group_base, BATTLE_RECORD_STRIDE))" in text
assert "if (!valid_range(record, BATTLE_RECORD_STRIDE))" in text
assert "if (!valid_range(valid_addr, 4u) || !valid_range(part, PART_STRIDE))" in text
assert "if (roster < CHAR_COUNT)" in text
assert "if (valid_range(class_addr, 1u))" in text
assert "if (!valid_range(address, size))" in bankj
assert "if (!valid_range(address, size))" in bankc
assert "if (!valid_range(BANKAH_RAM_START, BANKAH_SIZE)" in bankah
assert "!valid_range(desc_base, count * DESC_STRIDE)" in join
assert "!valid_range(part_base, PART_OFF + PART_MAX * PART_STRIDE)" in join

assert "BATTLE_RECORD_MAX       24u" in text
assert "PART_MAX        20u" in text
assert "if (!s_seen[slot] || s_signature[slot] != signature)" in text
assert "if (!s_part_seen[index] || s_part_signature[index] != signature)" in text
assert "DANIKA_SNAPSHOT" in text and "DANIKA_PROBE" in text
assert "DANIKA_PART_SNAPSHOT" in text and '"DANIKA_PART"' in text
assert "DANIKA_JOIN" in join

assert 'id = "ogre_danika_battle_probe"' in toml
assert 'display_name = "Knight of Danika - Battle Probe"' in toml
assert "enabled_by_default = false" in toml
assert 'additional_files = [ "BATTLE-PROBE.md" ]' in toml

assert "class `0x71`" in doc
assert "must remain `0x71`" in doc
assert "enemy Danika" in doc
assert "read-only" in plain_doc.lower()
assert "same class" in plain_doc.lower()
assert "mistaken for an ally/enemy flag" in plain_doc
assert "must be reproduced before" in plain_doc
assert "final ownership gate" in plain_doc

print("Danika battle probe safety: PASS")
print("hooks=frame+exact-DMA-return; writes=none; patch=none; visual+participant+join+bankAH+bankC+bankJ snapshots=bounded")
