#!/usr/bin/env python3
"""Host test for analyze_danika_bankah_dump.py."""
from analyze_danika_bankah_dump import parse, summarize

BASE = 0x801D0860
SIZE = 0xE80
blob = bytearray(SIZE)


def put(addr: int, words: list[int]) -> None:
    off = addr - BASE
    for word in words:
        blob[off:off + 4] = word.to_bytes(4, "big")
        off += 4


# setup function: form absolute pointer 0x801D16D0 and read first setup byte.
put(0x801D0AAC, [
    0x3C08801D,  # lui t0,0x801d
    0x250816D0,  # addiu t0,t0,0x16d0
    0x91090000,  # lbu t1,0(t0)
    0x03E00008,  # jr ra
    0x00000000,
])

# participant allocator: form absolute pointer 0x801F0CD0, load slot, store tag.
put(0x801D1508, [
    0x3C08801F,  # lui t0,0x801f
    0x25080CD0,  # addiu t0,t0,0x0cd0
    0x8D090000,  # lw t1,0(t0)
    0xA1090004,  # sb t1,4(t0)
    0x03E00008,  # jr ra
    0x00000000,
])

lines = []
for off in range(0, SIZE, 16):
    raw = blob[off:off + 16]
    lines.append(f"DANIKA_BANKAH addr={BASE:08X} off={off:04X} bytes={raw.hex().upper()}")

parsed = parse("\n".join(lines))
assert parsed is not None
report = summarize(parsed)
assert "chosen=big" in report
assert "func_801D0AAC_setup" in report
assert "func_801D1508_participant_alloc" in report
assert "@0x801D16D0 >>> SETUP_TABLE_16B" in report
assert "@0x801F0CD0 >>> UNIT_SLOT_TABLE_NEAR_801F0CD0" in report
assert "STORE sb" in report
assert "do not name a" in report
print("Danika bank-AH setup analyzer: PASS")
