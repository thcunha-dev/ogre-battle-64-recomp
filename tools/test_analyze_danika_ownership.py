#!/usr/bin/env python3
"""Host tests for analyze_danika_ownership.py."""

from analyze_danika_ownership import (
    DANIKA_CLASS_ID,
    DRAGOON_CLASS_ID,
    PARTICIPANT_SIZE,
    bit_discriminators,
    byte_discriminators,
    disjoint_roster_evidence,
    override_eligible,
    parse_participants,
    parse_raw_payloads,
    report,
)


def raw_lines(index: int, side_byte: int) -> str:
    payload = bytearray(PARTICIPANT_SIZE)
    payload[0x40] = side_byte
    payload[0x31] = 0x10 + index  # known level: excluded candidate
    payload[0x32] = 0x20 + index  # known EXP: excluded candidate
    payload[0xF6] = index         # known roster index: excluded candidate
    lines = []
    for off in range(0, PARTICIPANT_SIZE, 16):
        chunk = bytes(payload[off:off + 16])
        lines.append(
            f"DANIKA_PART_RAW i={index:02X} off={off:02X} bytes={chunk.hex().upper()}"
        )
    return "\n".join(lines)


SAMPLE = """
DANIKA_PART_SNAPSHOT i=00 roster=00 rclass=14 lvl=10 exp=20 head=00000000 tail=11111111
DANIKA_PART_SNAPSHOT i=01 roster=01 rclass=10 lvl=12 exp=30 head=00000000 tail=22222222
DANIKA_PART_SNAPSHOT i=02 roster=08 rclass=71 lvl=20 exp=40 head=00000000 tail=33333333
DANIKA_PART_SNAPSHOT i=03 roster=09 rclass=11 lvl=22 exp=50 head=00000000 tail=44444444
""" + "\n".join((
    raw_lines(0, 0x80),
    raw_lines(1, 0x81),
    raw_lines(2, 0x00),
    raw_lines(3, 0x01),
)) + "\n"

rows = parse_participants(SAMPLE)
payloads = parse_raw_payloads(SAMPLE)
assert len(rows) == 4
assert len(payloads) == 4
assert all(len(payload) == PARTICIPANT_SIZE for payload in payloads.values())
assert rows[0].class_id == DRAGOON_CLASS_ID
assert rows[2].class_id == DANIKA_CLASS_ID
assert payloads[0][0x40] == 0x80
assert payloads[3][0x40] == 0x01

clean, ally_range, enemy_range = disjoint_roster_evidence(rows[:2], rows[2:])
assert clean
assert ally_range == (0x00, 0x01)
assert enemy_range == (0x08, 0x09)

bytes_found = byte_discriminators(payloads, {0, 1}, {2, 3})
bits_found = bit_discriminators(payloads, {0, 1}, {2, 3})
assert any(off == 0x40 for off, _, _ in bytes_found)
assert (0x40, 0x80, 1, 0) in bits_found
assert all(off not in {0x31, 0x32, 0xF6} for off, _, _ in bytes_found)
assert all(off not in {0x31, 0x32, 0xF6} for off, _, _, _ in bits_found)

text = report(rows, {0x00, 0x01}, {0x02, 0x03}, payloads)
assert "complete_raw_payloads=4" in text
assert "labeled_allies=2 roster_range=0x00..0x01" in text
assert "labeled_enemies=2 roster_range=0x08..0x09" in text
assert "roster_ranges_cleanly_separable=yes" in text
assert "EVIDENCE: this capture has clean, disjoint contiguous roster ranges." in text
assert "BYTE_CANDIDATE off=0x40" in text
assert "BIT_CANDIDATE off=0x40 mask=0x80 ally=1 enemy=0" in text
assert "EVIDENCE: raw participant side-discriminator candidates were found." in text
assert "i=0x02 ownership=ENEMY" in text
assert "danika_override_eligible=no" in text

# A known allied 0x71 is the one and only class/side combination eligible.
assert override_eligible(DANIKA_CLASS_ID, "ALLY")
assert not override_eligible(DANIKA_CLASS_ID, "ENEMY")
assert not override_eligible(DANIKA_CLASS_ID, "UNKNOWN")
assert not override_eligible(DRAGOON_CLASS_ID, "ALLY")

# Overlapping or sparse roster ranges must not be promoted.
overlap = [rows[0], rows[2]]
clean, _, _ = disjoint_roster_evidence(overlap, [rows[1], rows[2]])
assert not clean

sparse_allies = [rows[0], rows[2]]
clean, ally_range, _ = disjoint_roster_evidence(sparse_allies, rows[1:2])
assert not clean
assert ally_range is None

# Raw evidence is also fail closed when any labeled participant is missing.
incomplete_payloads = dict(payloads)
del incomplete_payloads[3]
assert byte_discriminators(incomplete_payloads, {0, 1}, {2, 3}) == []
assert bit_discriminators(incomplete_payloads, {0, 1}, {2, 3}) == []
incomplete_text = report(rows, {0, 1}, {2, 3}, incomplete_payloads)
assert "missing_raw_payloads=0x03" in incomplete_text
assert "Raw comparison incomplete" in incomplete_text

# Partial raw chunks must never be reconstructed as a complete participant.
partial_log = (
    "DANIKA_PART_RAW i=00 off=00 bytes=" + ("00" * 16) + "\n"
    "DANIKA_PART_RAW i=00 off=10 bytes=" + ("00" * 16) + "\n"
)
assert parse_raw_payloads(partial_log) == {}

conflict_text = report(rows, {0x00, 0x01}, {0x01, 0x02}, payloads)
assert "label_conflicts=0x01" in conflict_text
assert "FAIL: conflicting side labels exist." in conflict_text

missing_text = report(rows, {0x00, 0x7F}, {0x02, 0x03}, payloads)
assert "missing_labeled_indices=0x7F" in missing_text
assert "FAIL: one or more labeled participants were absent" in missing_text

print("Danika ownership analyzer host tests: PASS")
