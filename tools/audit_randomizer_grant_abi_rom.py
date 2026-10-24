#!/usr/bin/env python3
"""Audit func_ovlN_801DC740 call-site ABI against the Rev-A ROM.

The universal randomizer replaces this streamed Bank-N grant with a `void`
RECOMP_PATCH. That is only safe if callers do not consume the original `$v0`
return value. This scanner validates the exact Rev-A ROM, locates every
`jal 0x801DC740`, and symbolically follows each post-return path until `$v0`
is either overwritten/call-clobbered or read.

Usage:
    python3 tools/audit_randomizer_grant_abi_rom.py /path/to/rev1.z64
"""

from __future__ import annotations

from hashlib import sha1
from pathlib import Path
import sys

ROM_SHA1 = "d26b14bee422a09581ce438d45ba9fec9783fbb8"
TARGET = 0x801DC740
JAL_WORD = 0x0C000000 | ((TARGET >> 2) & 0x03FFFFFF)
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

BANK_N_ROM = 0x101D00
BANK_N_VRAM = 0x801AD5C0
BANK_R_DELTA = 0x8007FB70


def section_delta(rom_offset: int) -> int:
    if rom_offset < 0x190000:
        return BANK_N_VRAM - BANK_N_ROM
    return BANK_R_DELTA


def decode_rw(word: int) -> tuple[set[int], set[int], str]:
    """Return (read GPRs, written GPRs, control kind) for needed MIPS-I forms."""
    op = (word >> 26) & 0x3F
    rs = (word >> 21) & 0x1F
    rt = (word >> 16) & 0x1F
    rd = (word >> 11) & 0x1F
    funct = word & 0x3F
    reads: set[int] = set()
    writes: set[int] = set()
    kind = "normal"

    if op == 0:
        if funct in (0, 2, 3):  # sll/srl/sra
            reads.add(rt)
            writes.add(rd)
        elif funct == 8:  # jr
            reads.add(rs)
            kind = "jr"
        elif funct == 9:  # jalr
            reads.add(rs)
            writes.add(rd if rd else 31)
            kind = "jalr"
        elif funct in (16, 18):  # mfhi/mflo
            writes.add(rd)
        elif funct in (17, 19):  # mthi/mtlo
            reads.add(rs)
        else:
            reads.update((rs, rt))
            writes.add(rd)
    elif op == 2:
        kind = "j"
    elif op == 3:
        writes.add(31)
        kind = "jal"
    elif op in (4, 5):
        reads.update((rs, rt))
        kind = "branch"
    elif op in (1, 6, 7):
        reads.add(rs)
        kind = "branch"
    elif op in (8, 9, 10, 11, 12, 13, 14):
        reads.add(rs)
        writes.add(rt)
    elif op == 15:  # lui
        writes.add(rt)
    elif 32 <= op <= 39 or 48 <= op <= 55:  # loads
        reads.add(rs)
        writes.add(rt)
    elif 40 <= op <= 47 or 56 <= op <= 63:  # stores
        reads.update((rs, rt))
    else:
        # Fail conservative for uncommon forms.
        if rs:
            reads.add(rs)
        if rt:
            reads.add(rt)
    return reads, writes, kind


def branch_target(pc: int, word: int) -> int:
    imm = word & 0xFFFF
    if imm & 0x8000:
        imm -= 0x10000
    return pc + 4 + (imm << 2)


def jump_target(pc: int, word: int) -> int:
    return ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)


def call_offsets(rom: bytes) -> tuple[int, ...]:
    needle = JAL_WORD.to_bytes(4, "big")
    found: list[int] = []
    pos = 0
    while True:
        pos = rom.find(needle, pos)
        if pos < 0:
            break
        found.append(pos)
        pos += 4
    return tuple(found)


def v0_safe_after_call(rom: bytes, call_offset: int, max_steps: int = 256) -> tuple[bool, str]:
    """Prove no `$v0` read occurs before a definite ABI clobber on every path."""
    delta = section_delta(call_offset)

    def walk(rom_offset: int, steps: int, seen: frozenset[int]) -> tuple[bool, str]:
        if steps <= 0:
            return False, "analysis step limit reached"
        if rom_offset in seen:
            # A loop that never reads v0 is harmless until a later exit; revisit
            # is treated as stable because branch exploration separately checks
            # the alternate exit path on first encounter.
            return True, "loop without v0 use"
        if rom_offset < 0 or rom_offset + 4 > len(rom):
            return False, f"path escaped ROM at 0x{rom_offset:X}"

        word = int.from_bytes(rom[rom_offset:rom_offset + 4], "big")
        pc = rom_offset + delta
        reads, writes, kind = decode_rw(word)
        if 2 in reads:
            return False, f"reads v0 at ROM 0x{rom_offset:X}: 0x{word:08X}"
        if 2 in writes:
            return True, f"v0 overwritten at ROM 0x{rom_offset:X}: 0x{word:08X}"

        new_seen = seen | {rom_offset}
        if kind in ("jal", "jalr"):
            # v0 is caller-saved in the MIPS ABI; once another call happens,
            # the earlier grant return cannot be relied upon by this caller.
            return True, f"call-clobber at ROM 0x{rom_offset:X}: 0x{word:08X}"
        if kind == "jr":
            return False, f"returns before clobber at ROM 0x{rom_offset:X}"

        if kind in ("j", "branch"):
            delay_offset = rom_offset + 4
            delay = int.from_bytes(rom[delay_offset:delay_offset + 4], "big")
            d_reads, d_writes, _ = decode_rw(delay)
            if 2 in d_reads:
                return False, f"delay slot reads v0 at ROM 0x{delay_offset:X}"
            if 2 in d_writes:
                return True, f"delay slot overwrites v0 at ROM 0x{delay_offset:X}"

            if kind == "j":
                target = jump_target(pc, word) - delta
                return walk(target, steps - 2, new_seen | {delay_offset})

            target = branch_target(pc, word) - delta
            taken = walk(target, steps - 2, new_seen | {delay_offset})
            fallthrough = walk(rom_offset + 8, steps - 2, new_seen | {delay_offset})
            if not taken[0]:
                return taken
            if not fallthrough[0]:
                return fallthrough
            return True, f"branch paths safe ({taken[1]}; {fallthrough[1]})"

        return walk(rom_offset + 4, steps - 1, new_seen)

    return walk(call_offset + 8, max_steps, frozenset())


def audit_rom(path: Path) -> None:
    rom = path.read_bytes()
    digest = sha1(rom).hexdigest()
    if digest != ROM_SHA1:
        raise SystemExit(f"wrong ROM SHA-1: {digest}; expected {ROM_SHA1}")

    found = call_offsets(rom)
    if found != EXPECTED_CALL_OFFSETS:
        raise SystemExit(
            "func_ovlN_801DC740 call-site set changed:\n"
            f"found={tuple(hex(x) for x in found)}\n"
            f"expected={tuple(hex(x) for x in EXPECTED_CALL_OFFSETS)}"
        )

    for offset in found:
        safe, reason = v0_safe_after_call(rom, offset)
        if not safe:
            raise SystemExit(f"grant ABI unsafe at ROM 0x{offset:X}: {reason}")

    print(f"central grant ABI ROM audit: PASS ({len(found)} callers, v0 discarded)")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: audit_randomizer_grant_abi_rom.py <Rev-A .z64>")
    audit_rom(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
