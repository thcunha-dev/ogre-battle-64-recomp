#!/usr/bin/env python3
"""Host test for analyze_danika_bankc_dump.py."""
from analyze_danika_bankc_dump import analyze_functions, parse, summarize

# Synthetic big-endian MIPS covering two known predicate entries:
#   func_801C8B88: lbu t0,+F6(a0); sltiu v0,t0,0x64; jr ra; nop
#   func_801C8BA4: lhu v0,+20(a0); andi v0,v0,1; jr ra; nop
SAMPLE = """
DANIKA_BANKC name=exp_filters addr=801C8B80 off=0000 bytes=0000000000000000908800F62D020064
DANIKA_BANKC name=exp_filters addr=801C8B80 off=0010 bytes=03E00008000000000000000000000000
DANIKA_BANKC name=exp_filters addr=801C8B80 off=0020 bytes=00000000948200203042000103E00008
DANIKA_BANKC name=exp_filters addr=801C8B80 off=0030 bytes=00000000
"""
windows = parse(SAMPLE)
assert set(windows) == {"exp_filters"}
rows = analyze_functions(windows)
assert [row.name for row in rows] == ["func_801C8B88", "func_801C8BA4"]
assert rows[0].accesses[0][2:] == (0xF6, "PART_CHARIDX")
assert rows[0].saw_return
assert any("compare" in text for _, text in rows[0].return_forms)
assert rows[1].accesses[0][2:] == (0x20, "PART_FIELD_20")
assert rows[1].saw_return
assert any("bit-test" in text for _, text in rows[1].return_forms)

report = summarize(windows)
assert "chosen=big" in report
assert ">>> PART_CHARIDX" in report
assert "0x801C8B88 func_801C8B88" in report
assert "0x801C8BA4 func_801C8BA4" in report
assert "0x801C9008 func_801C9008(index)->participant" in report
assert "Per-function participant dataflow" in report
assert "ownership_review_interest=high" in report
assert "lbu +0xF6($a0/alias) PART_CHARIDX" in report
assert "lhu +0x20($a0/alias) PART_FIELD_20" in report
assert "side/team" in report
assert "Do not promote" in report
print("Danika bank-C dump analyzer: PASS")
