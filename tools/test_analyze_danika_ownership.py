#!/usr/bin/env python3
"""Host tests for analyze_danika_ownership.py."""

from analyze_danika_ownership import (
    DANIKA_CLASS_ID,
    DRAGOON_CLASS_ID,
    disjoint_roster_evidence,
    override_eligible,
    parse_participants,
    report,
)

SAMPLE = """
DANIKA_PART_SNAPSHOT i=00 roster=00 rclass=14 lvl=10 exp=0020 head=00000000 tail=11111111
DANIKA_PART_SNAPSHOT i=01 roster=01 rclass=10 lvl=12 exp=0030 head=00000000 tail=22222222
DANIKA_PART_SNAPSHOT i=02 roster=08 rclass=71 lvl=20 exp=0040 head=00000000 tail=33333333
DANIKA_PART_SNAPSHOT i=03 roster=09 rclass=11 lvl=22 exp=0050 head=00000000 tail=44444444
"""

rows = parse_participants(SAMPLE)
assert len(rows) == 4
assert rows[0].class_id == DRAGOON_CLASS_ID
assert rows[2].class_id == DANIKA_CLASS_ID

clean, ally_range, enemy_range = disjoint_roster_evidence(rows[:2], rows[2:])
assert clean
assert ally_range == (0x00, 0x01)
assert enemy_range == (0x08, 0x09)

text = report(rows, {0x00, 0x01}, {0x02, 0x03})
assert "labeled_allies=2 roster_range=0x00..0x01" in text
assert "labeled_enemies=2 roster_range=0x08..0x09" in text
assert "roster_ranges_cleanly_separable=yes" in text
assert "EVIDENCE: this capture has clean, disjoint contiguous roster ranges." in text
assert "i=0x02 ownership=ENEMY" in text
assert "danika_override_eligible=no" in text

# A known allied 0x71 is the one and only class/side combination eligible.
assert override_eligible(DANIKA_CLASS_ID, "ALLY")
assert not override_eligible(DANIKA_CLASS_ID, "ENEMY")
assert not override_eligible(DANIKA_CLASS_ID, "UNKNOWN")
assert not override_eligible(DRAGOON_CLASS_ID, "ALLY")

# Overlapping or sparse ranges must not be promoted.
overlap = [rows[0], rows[2]]
clean, _, _ = disjoint_roster_evidence(overlap, [rows[1], rows[2]])
assert not clean

sparse_allies = [rows[0], rows[2]]
clean, ally_range, _ = disjoint_roster_evidence(sparse_allies, rows[1:2])
assert not clean
assert ally_range is None

conflict_text = report(rows, {0x00, 0x01}, {0x01, 0x02})
assert "label_conflicts=0x01" in conflict_text
assert "FAIL: conflicting side labels exist." in conflict_text

missing_text = report(rows, {0x00, 0x7F}, {0x02, 0x03})
assert "missing_labeled_indices=0x7F" in missing_text
assert "FAIL: one or more labeled participants were absent" in missing_text

print("Danika ownership analyzer host tests: PASS")
