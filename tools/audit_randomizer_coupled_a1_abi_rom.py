#!/usr/bin/env python3
"""Audit the central-grant a1 calling convention against Ogre Battle 64 Rev-A.

All 46 calls to func_ovlN_801DC740 set a1 in the JAL delay slot. Exactly two
set a1=1; both are coupled Bank-R unit/setup paths that also write unit-loadout
references and therefore must remain vanilla. Every other caller sets a1=0.

Usage:
    python3 tools/audit_randomizer_coupled_a1_abi_rom.py /path/to/rev1.z64
"""

from __future__ import annotations

from hashlib import sha1
from pathlib import Path
import sys

ROM_SHA1 = "d26b14bee422a09581ce438d45ba9fec9783fbb8"
TARGET = 0x801DC740
JAL_WORD = 0x0C000000 | ((TARGET >> 2) & 0x03FFFFFF)
A1_ZERO_WORD = 0x00002821  # addu a1,zero,zero
A1_ONE_WORD = 0x24050001   # addiu a1,zero,1
COUPLED_A1_ONE_OFFSETS = (0x19607C, 0x197220)
COUPLED_A1_ONE_RAS = (0x80215BF4, 0x80216D98)

EXPECTED_CALL_OFFSETS = (
    0x1025E8, 0x1028C8, 0x110074, 0x139B1C,
    0x19607C, 0x197220,
    0x1974F8, 0x197504, 0x197510, 0x19751C, 0x197528, 0x197534,
    0x197540, 0x19754C, 0x197560, 0x19756C, 0x197578, 0x197584,
    0x197590, 0x19759C, 0x1975A8, 0x1975B4, 0x1975C0, 0x1975CC,
    0x1975D8, 0x1975E4, 0x1975F0, 0x1975FC, 0x197608, 0x197614,
    0x197620, 0x19762C, 0x197638, 0x197644, 0x197650, 0x19765C,
    0x197668, 0x197674, 0x197680, 0x19768C, 0x197698, 0x1976A4,
    0x1976B0, 0x1976BC, 0x1976C8, 0x1976D4,
)

BANK_N_DELTA = 0x801AD5C0 - 0x00101D00
BANK_R_DELTA = 0x8007FB70


def call_offsets(rom: bytes) -> tuple[int, ...]:
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


def return_address(offset: int) -> int:
    delta = BANK_N_DELTA if offset < 0x190000 else BANK_R_DELTA
    return offset + delta + 8


def audit_rom(path: Path) -> None:
    rom = path.read_bytes()
    digest = sha1(rom).hexdigest()
    if digest != ROM_SHA1:
        raise SystemExit(f"wrong ROM SHA-1: {digest}; expected {ROM_SHA1}")

    found = call_offsets(rom)
    if found != EXPECTED_CALL_OFFSETS:
        raise SystemExit("central grant call-site set changed")

    one_offsets: list[int] = []
    one_ras: list[int] = []
    for offset in found:
        delay = int.from_bytes(rom[offset + 4:offset + 8], "big")
        if delay == A1_ONE_WORD:
            one_offsets.append(offset)
            one_ras.append(return_address(offset))
        elif delay != A1_ZERO_WORD:
            raise SystemExit(
                f"unexpected a1 delay instruction at ROM 0x{offset:X}: 0x{delay:08X}"
            )

    if tuple(one_offsets) != COUPLED_A1_ONE_OFFSETS:
        raise SystemExit(f"a1=1 caller set changed: {tuple(hex(x) for x in one_offsets)}")
    if tuple(one_ras) != COUPLED_A1_ONE_RAS:
        raise SystemExit(f"a1=1 return-address set changed: {tuple(hex(x) for x in one_ras)}")

    print("coupled a1 ROM audit: PASS (2 a1=1 callers, both classified coupled)")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: audit_randomizer_coupled_a1_abi_rom.py <Rev-A .z64>")
    audit_rom(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
