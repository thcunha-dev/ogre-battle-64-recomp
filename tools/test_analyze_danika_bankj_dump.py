#!/usr/bin/env python3
"""Host test for analyze_danika_bankj_dump.py."""
from analyze_danika_bankj_dump import decode, parse, plausibility, summarize

# Big-endian MIPS sample:
#   lbu   t0,0xF6(a0)
#   sltiu t1,t0,0x64
#   bne   t1,zero,+1
#   nop
#   lbu   v0,0x12(a1)
SAMPLE = """
noise
DANIKA_BANKJ name=part_to_record addr=801D8E90 off=0000 bytes=908800F62D0900641520000100000000
DANIKA_BANKJ name=part_to_record addr=801D8E90 off=0010 bytes=90A20012000000000000000000000000
"""
windows = parse(SAMPLE)
assert set(windows) == {"part_to_record"}
base, data = windows["part_to_record"]
assert base == 0x801D8E90
assert len(data) == 0x20
assert plausibility(data, "big") > plausibility(data, "little")
assert decode(0x908800F6, 0x801D8E90) == "lbu $t0, 246($a0)"
assert decode(0x2D090064, 0x801D8E94) == "sltiu $t1, $t0, 0x0064"

report = summarize(windows)
assert "chosen=big" in report
assert ">>> PART_CHARIDX" in report
assert ">>> CHAR_COUNT_100" in report
assert ">>> ROSTER_CLASS" in report
assert "HIT 0x801D8E90 PART_CHARIDX" in report
assert "identity/roster bridge" in report
assert "allied/enemy proof" in report

empty = summarize(parse("nothing"))
assert "No DANIKA_BANKJ records found." in empty

# Gaps are rejected rather than silently filling unknown bytes with zero.
GAPPED = """
DANIKA_BANKJ name=x addr=801D0000 off=0000 bytes=00000000
DANIKA_BANKJ name=x addr=801D0000 off=0008 bytes=00000000
"""
try:
    parse(GAPPED)
except ValueError as exc:
    assert "incomplete dump" in str(exc)
else:
    raise AssertionError("gapped dump must fail")

print("Danika bank-J dump analyzer: PASS")
