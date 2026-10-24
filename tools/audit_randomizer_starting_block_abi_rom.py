#!/usr/bin/env python3
"""Audit the only STARTING ITEMS opt-in block against Ogre Battle 64 Rev-A.

The safe block is Bank-R ROM 0x1974F8..0x1976D4: forty literal calls to the
central grant. Every call sets a1=0 in its delay slot, and the surrounding
straight-line block contains no store instruction, so unlike the two coupled
unit/setup paths it does not first write a matching unit-loadout reference.

Usage:
    python3 tools/audit_randomizer_starting_block_abi_rom.py /path/to/rev1.z64
"""

from __future__ import annotations

from hashlib import sha1
from pathlib import Path
import sys

ROM_SHA1 = "d26b14bee422a09581ce438d45ba9fec9783fbb8"
TARGET = 0x801DC740
JAL_WORD = 0x0C000000 | ((TARGET >> 2) & 0x03FFFFFF)
A1_ZERO_WORD = 0x00002821
BLOCK_SCAN_LO = 0x1974D0
BLOCK_CALL_LO = 0x1974F8
BLOCK_CALL_HI = 0x1976D4
BLOCK_SCAN_HI = 0x1976DC  # next call after the literal grant sequence
BANK_R_DELTA = 0x8007FB70
RA_LO = BLOCK_CALL_LO + BANK_R_DELTA + 8
RA_HI_EXCLUSIVE = BLOCK_CALL_HI + BANK_R_DELTA + 8

SAFE_CALL_OFFSETS = (
    0x1974F8, 0x197504, 0x197510, 0x19751C, 0x197528, 0x197534,
    0x197540, 0x19754C, 0x197560, 0x19756C, 0x197578, 0x197584,
    0x197590, 0x19759C, 0x1975A8, 0x1975B4, 0x1975C0, 0x1975CC,
    0x1975D8, 0x1975E4, 0x1975F0, 0x1975FC, 0x197608, 0x197614,
    0x197620, 0x19762C, 0x197638, 0x197644, 0x197650, 0x19765C,
    0x197668, 0x197674, 0x197680, 0x19768C, 0x197698, 0x1976A4,
    0x1976B0, 0x1976BC, 0x1976C8, 0x1976D4,
)


def is_store(word: int) -> bool:
    op = (word >> 26) & 0x3F
    return 40 <= op <= 47 or 56 <= op <= 63


def audit_rom(path: Path) -> None:
    rom = path.read_bytes()
    digest = sha1(rom).hexdigest()
    if digest != ROM_SHA1:
        raise SystemExit(f"wrong ROM SHA-1: {digest}; expected {ROM_SHA1}")

    found: list[int] = []
    for offset in range(BLOCK_SCAN_LO, BLOCK_SCAN_HI, 4):
        word = int.from_bytes(rom[offset:offset + 4], "big")
        if is_store(word):
            raise SystemExit(f"store appeared in safe starting block at ROM 0x{offset:X}: 0x{word:08X}")
        if word == JAL_WORD:
            found.append(offset)

    if tuple(found) != SAFE_CALL_OFFSETS:
        raise SystemExit(f"safe starting call set changed: {tuple(hex(x) for x in found)}")

    for offset in SAFE_CALL_OFFSETS:
        delay = int.from_bytes(rom[offset + 4:offset + 8], "big")
        if delay != A1_ZERO_WORD:
            raise SystemExit(f"safe starting call at ROM 0x{offset:X} no longer passes a1=0")

    print("safe starting block ROM audit: PASS (40 grants, a1=0, no stores)")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: audit_randomizer_starting_block_abi_rom.py <Rev-A .z64>")
    audit_rom(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
