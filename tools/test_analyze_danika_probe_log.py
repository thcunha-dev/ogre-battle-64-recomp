#!/usr/bin/env python3
"""Host test for analyze_danika_probe_log.py."""
from analyze_danika_probe_log import (
    candidate_discriminators,
    parse,
    parse_location,
    summarize,
)

SAMPLE = """
noise
DANIKA_SNAPSHOT g=03 slot=00 sel=0012 class=0014 id=14 f04=0001 f06=0002 f08=0003 f0A=0004 flags=0002 f0E=0005 f10=0006
DANIKA_SNAPSHOT g=03 slot=01 sel=0044 class=0071 id=71 f04=0011 f06=0012 f08=0013 f0A=0014 flags=0003 f0E=0015 f10=0016
DANIKA_PROBE g=03 slot=01 sel=0044 class=0071 id=71 f04=0011 f06=0012 f08=0013 f0A=0014 flags=0002 f0E=0015 f10=0016
DANIKA_SNAPSHOT g=04 slot=02 sel=0033 class=009C id=9C f04=0021 f06=0022 f08=0023 f0A=0024 flags=0001 f0E=0025 f10=0026
"""

rows = parse(SAMPLE)
assert len(rows) == 4
assert rows[0]["id"] == 0x14
assert rows[1]["sel"] == 0x44
assert rows[2]["flags"] == 0x0002
assert parse_location("03:0A") == (0x03, 0x0A)

report = summarize(rows)
assert "records=4 snapshots=3 changes=1" in report
assert "0x14 Dragoon" in report
assert "selectors=0x0012" in report
assert "0x71 Knight of Danika" in report
assert "0x9C Hidden Dragoon" in report
assert "flags: 0x0002,0x0003" in report
assert "Unlabeled records never imply allied/enemy ownership." in report

# Cross-class labels are useful for donor/enemy selector capture, but must NOT
# be promoted into an ownership field discriminator.
labeled = summarize(rows, {(0x03, 0x00)}, {(0x03, 0x01)})
assert "known_allied_dragoon_selectors=0x0012" in labeled
assert "known_enemy_danika_selectors=0x0044" in labeled
assert "No same-class ally/enemy field discriminator" in labeled
assert "CANDIDATE" not in labeled

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

empty = summarize(parse("nothing useful here"))
assert "records=0" in empty
assert "No DANIKA_SNAPSHOT/DANIKA_PROBE records found." in empty

print("Danika probe log analyzer: PASS")
