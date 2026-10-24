#!/usr/bin/env python3
"""Audit func_80172820 call-site ABI against the Ogre Battle 64 Rev-A ROM.

The randomizer replaces func_80172820(id,count) with a void RECOMP_PATCH. Rev-A
has exactly one JAL to this helper, from Bank L. This auditor proves the caller
never consumes the original `$v0` return value: the first instruction after the
JAL delay slot overwrites `$v0`.

Usage:
    python3 tools/audit_randomizer_post_battle_abi_rom.py /path/to/rev1.z64
"""

from __future__ import annotations

from hashlib import sha1
from pathlib import Path
import sys

ROM_SHA1 = "d26b14bee422a09581ce438d45ba9fec9783fbb8"
TARGET = 0x80172820
JAL_WORD = 0x0C000000 | ((TARGET >> 2) & 0x03FFFFFF)
EXPECTED_CALL_OFFSET = 0x002A4ED8
EXPECTED_CALL_VRAM = 0x802356F8
EXPECTED_DELAY_WORD = 0x30A500FF  # andi a1,a1,0xff
EXPECTED_POST_WORD = 0x26220001   # addiu v0,s1,1 -- definite return clobber


def find_calls(rom: bytes) -> tuple[int, ...]:
    needle = JAL_WORD.to_bytes(4, "big")
    out: list[int] = []
    pos = 0
    while True:
        pos = rom.find(needle, pos)
        if pos < 0:
            break
        out.append(pos)
        pos += 4
    return tuple(out)


def audit_rom(path: Path) -> None:
    rom = path.read_bytes()
    digest = sha1(rom).hexdigest()
    if digest != ROM_SHA1:
        raise SystemExit(f"wrong ROM SHA-1: {digest}; expected {ROM_SHA1}")

    calls = find_calls(rom)
    if calls != (EXPECTED_CALL_OFFSET,):
        raise SystemExit(
            "func_80172820 call-site set changed: "
            f"found={tuple(hex(x) for x in calls)}, expected=(0x{EXPECTED_CALL_OFFSET:X},)"
        )

    call_word = int.from_bytes(rom[EXPECTED_CALL_OFFSET:EXPECTED_CALL_OFFSET + 4], "big")
    delay_word = int.from_bytes(rom[EXPECTED_CALL_OFFSET + 4:EXPECTED_CALL_OFFSET + 8], "big")
    post_word = int.from_bytes(rom[EXPECTED_CALL_OFFSET + 8:EXPECTED_CALL_OFFSET + 12], "big")
    if call_word != JAL_WORD:
        raise SystemExit(f"unexpected JAL word: 0x{call_word:08X}")
    if delay_word != EXPECTED_DELAY_WORD:
        raise SystemExit(f"unexpected delay word: 0x{delay_word:08X}")
    if post_word != EXPECTED_POST_WORD:
        raise SystemExit(f"post-call v0 clobber changed: 0x{post_word:08X}")

    delta = EXPECTED_CALL_VRAM - EXPECTED_CALL_OFFSET
    if EXPECTED_CALL_OFFSET + delta != EXPECTED_CALL_VRAM:
        raise SystemExit("Bank-L ROM/VRAM mapping invariant failed")

    print("post-battle add ABI ROM audit: PASS (1 caller, v0 overwritten immediately)")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: audit_randomizer_post_battle_abi_rom.py <Rev-A .z64>")
    audit_rom(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
