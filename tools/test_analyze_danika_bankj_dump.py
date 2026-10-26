#!/usr/bin/env python3
"""Host test for analyze_danika_bankj_dump.py."""
from analyze_danika_bankj_dump import decode, parse, plausibility, summarize

# Big-endian MIPS sample proving a complete bounded 0x38 roster lookup:
#   lbu   t0,0xF6(a0)       ; participant character index
#   sltiu t1,t0,0x64        ; index < 100
#   sll   t2,t0,3           ; 8*i
#   subu  t3,t2,t0          ; 7*i
#   sll   t4,t3,3           ; 56*i == 0x38*i
#   addu  t5,a1,t4          ; roster base + record offset
#   lbu   v0,0x12(t5)       ; roster class
SAMPLE = """
noise
DANIKA_BANKJ name=part_to_record addr=801D8E90 off=0000 bytes=908800F62D090064000850C001485823
DANIKA_BANKJ name=part_to_record addr=801D8E90 off=0010 bytes=000B60C000AC682191A2001200000000
"""
windows = parse(SAMPLE)
assert set(windows) == {"part_to_record"}
base, data = windows["part_to_record"]
assert base == 0x801D8E90
assert len(data) == 0x20
assert plausibility(data, "big") > plausibility(data, "little")
assert decode(0x908800F6, 0x801D8E90) == "lbu $t0, 246($a0)"
assert decode(0x2D090064, 0x801D8E94) == "sltiu $t1, $t0, 0x0064"
assert decode(0x000B60C0, 0x801D8EA0) == "sll $t4, $t3, 3"

report = summarize(windows)
assert "chosen=big" in report
assert ">>> PART_CHARIDX" in report
assert ">>> CHAR_COUNT_100" in report
assert ">>> ROSTER_CLASS" in report
assert "HIT 0x801D8E90 PART_CHARIDX" in report
assert "[coeff=56]" in report
assert "ROSTER_BRIDGE_CHAIN=STRONG" in report
assert "strong_participant_to_roster_chains=1" in report
assert "participant_charidx_to_persistent_roster=SUPPORTED" in report
assert "ownership_side=UNKNOWN" in report
assert "does NOT alone" in report

# A superficially similar scale (8*i + 4*i = 12*i) must not be accepted as
# the 0x38 roster stride. This guards the exact-coefficient safety contract.
FALSE_SCALE = """
DANIKA_BANKJ name=x addr=801D0000 off=0000 bytes=908800F62D090064000850C000085900
DANIKA_BANKJ name=x addr=801D0000 off=0010 bytes=014B6021918200120000000000000000
"""
false_report = summarize(parse(FALSE_SCALE))
assert "ROSTER_BRIDGE_CHAIN=STRONG" not in false_report
assert "strong_participant_to_roster_chains=0" in false_report
assert "ownership_side=UNKNOWN" in false_report

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
