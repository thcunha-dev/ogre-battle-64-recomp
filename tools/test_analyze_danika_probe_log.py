#!/usr/bin/env python3
"""Host test for analyze_danika_probe_log.py."""
from analyze_danika_probe_log import parse, summarize

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

report = summarize(rows)
assert "records=4 snapshots=3 changes=1" in report
assert "0x14 Dragoon" in report
assert "selectors=0x0012" in report
assert "0x71 Knight of Danika" in report
assert "0x9C Hidden Dragoon" in report
assert "flags: 0x0002,0x0003" in report
assert "does NOT infer allied/enemy ownership" in report

empty = summarize(parse("nothing useful here"))
assert "records=0" in empty
assert "No DANIKA_SNAPSHOT/DANIKA_PROBE records found." in empty

print("Danika probe log analyzer: PASS")
