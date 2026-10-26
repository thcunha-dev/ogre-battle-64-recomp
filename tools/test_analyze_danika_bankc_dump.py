#!/usr/bin/env python3
"""Host test for analyze_danika_bankc_dump.py."""
from analyze_danika_bankc_dump import parse, summarize

SAMPLE = """
DANIKA_BANKC name=exp_filters addr=801C8B80 off=0000 bytes=908800F62D0900641520000100000000
DANIKA_BANKC name=exp_filters addr=801C8B80 off=0010 bytes=90A20012000000000000000000000000
"""
windows = parse(SAMPLE)
assert set(windows) == {"exp_filters"}
report = summarize(windows)
assert "chosen=big" in report
assert ">>> PART_CHARIDX" in report
assert "0x801C8B88 func_801C8B88" in report
assert "0x801C8BA4 func_801C8BA4" in report
assert "0x801C9008 func_801C9008(index)->participant" in report
assert "side/team" in report
assert "Do not promote" in report
print("Danika bank-C dump analyzer: PASS")
