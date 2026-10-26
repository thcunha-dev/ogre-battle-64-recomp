#!/usr/bin/env python3
"""Host test for analyze_danika_probe_log.py."""
from analyze_danika_probe_log import (
    candidate_discriminators,
    parse,
    parse_location,
    parse_participants,
    summarize,
    unique_class_bridges,
)

SAMPLE = """
noise
DANIKA_PART_SNAPSHOT i=00 roster=01 rclass=14 lvl=12 exp=34 head=00112233445566778899AABBCCDDEEFF tail=1020304050600170
DANIKA_PART_SNAPSHOT i=01 roster=FF rclass=FF lvl=10 exp=00 head=FFEEDDCCBBAA99887766554433221100 tail=010203040506FF08
DANIKA_SNAPSHOT g=03 slot=00 sel=0012 class=0014 id=14 f04=0001 f06=0002 f08=0003 f0A=0004 flags=0002 f0E=0005 f10=0006
DANIKA_SNAPSHOT g=03 slot=01 sel=0044 class=0071 id=71 f04=0011 f06=0012 f08=0013 f0A=0014 flags=0003 f0E=0015 f10=0016
DANIKA_PROBE g=03 slot=01 sel=0044 class=0071 id=71 f04=0011 f06=0012 f08=0013 f0A=0014 flags=0002 f0E=0015 f10=0016
DANIKA_SNAPSHOT g=04 slot=02 sel=0033 class=009C id=9C f04=0021 f06=0022 f08=0023 f0A=0024 flags=0001 f0E=0025 f10=0026
"""

rows = parse(SAMPLE)
parts = parse_participants(SAMPLE)
assert len(rows) == 4
assert len(parts) == 2
assert rows[0]["id"] == 0x14
assert rows[1]["sel"] == 0x44
assert rows[2]["flags"] == 0x0002
assert parts[0]["i"] == 0
assert parts[0]["roster"] == 1
assert parts[0]["rclass"] == 0x14
assert parts[0]["tail"] == "1020304050600170"
assert parse_location("03:0A") == (0x03, 0x0A)

bridges = unique_class_bridges(rows, parts)
assert bridges == [(0x14, 0, 1, (0x03, 0x00), 0x0012)]

report = summarize(rows, participants=parts)
assert "records=4 snapshots=3 changes=1" in report
assert "participants=2 snapshots=2 changes=0" in report
assert "0x14 Dragoon" in report
assert "selectors=0x0012" in report
assert "0x71 Knight of Danika" in report
assert "0x9C Hidden Dragoon" in report
assert "flags: 0x0002,0x0003" in report
assert "participant=0x00 roster=0x01 rclass=0x14 Dragoon roster_backed=yes" in report
assert "participant=0x01 roster=0xFF rclass=0xFF unresolved roster_backed=no" in report
assert "BRIDGE_CANDIDATE class=0x14 Dragoon" in report
assert "visual=g03/s00 selector=0x0012" in report
assert "candidate_roster_backed_dragoon_selectors=0x0012" in report
assert "identity correlation only" in report
assert "Unlabeled visual records never imply allied/enemy ownership." in report

# Cross-class labels are useful for donor/enemy selector capture, but must NOT
# be promoted into an ownership field discriminator.  A BRIDGE_CANDIDATE is a
# separate identity correlation and is allowed here.
labeled = summarize(rows, {(0x03, 0x00)}, {(0x03, 0x01)}, parts)
assert "known_allied_dragoon_selectors=0x0012" in labeled
assert "known_enemy_danika_selectors=0x0044" in labeled
assert "No same-class ally/enemy field discriminator" in labeled
assert "\nCANDIDATE class=0x" not in labeled

# Same-class observations on both labeled sides may produce candidate fields,
# but they are still reported only as correlations requiring reproduction.
SAME_CLASS = """
DANIKA_SNAPSHOT g=05 slot=00 sel=0012 class=0014 id=14 f04=0001 f06=0002 f08=0003 f0A=0004 flags=0002 f0E=0005 f10=0006
DANIKA_SNAPSHOT g=05 slot=01 sel=0012 class=0014 id=14 f04=0001 f06=0002 f08=0003 f0A=0004 flags=0003 f0E=0005 f10=0006
"""
same = parse(SAME_CLASS)
candidates = candidate_discriminators([same[0]], [same[1]])
assert candidates == [(0x14, "flags", {0x0002}, {0x0003})]
same_report = summarize(same, {(0x05, 0x00)}, {(0x05, 0x01)})
assert "CANDIDATE class=0x14 Dragoon field=flags ally=0x0002 enemy=0x0003" in same_report
assert "not yet a global ownership proof" in same_report

# A class is not bridged when more than one visual location exists: that would
# be ambiguous and must remain manual evidence.
AMBIG = SAMPLE + "\nDANIKA_SNAPSHOT g=03 slot=05 sel=0013 class=0014 id=14 f04=0001 f06=0002 f08=0003 f0A=0004 flags=0002 f0E=0005 f10=0006\n"
assert unique_class_bridges(parse(AMBIG), parse_participants(AMBIG)) == []
ambig_report = summarize(parse(AMBIG), participants=parse_participants(AMBIG))
assert "No unambiguous 1:1 roster-class -> visual-record bridge" in ambig_report

empty = summarize(parse("nothing useful here"), participants=parse_participants("nothing useful here"))
assert "records=0" in empty
assert "participants=0" in empty
assert "No DANIKA_SNAPSHOT/DANIKA_PROBE or DANIKA_PART records found." in empty

print("Danika probe log analyzer: PASS")
