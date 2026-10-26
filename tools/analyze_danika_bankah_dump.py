#!/usr/bin/env python3
"""Decode the transient battle-participant setup bank captured after its DMA.

Bank AH is more valuable than a visual correlation because it is the code that
constructs battle participants.  This analyzer isolates its three known entry
points and resolves simple LUI/addiu/ori constant-address chains so stores into
setup/unit/battle tables stand out.  Constant propagation is deliberately
conservative and reported as evidence, not as ownership semantics.
"""
from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path

from analyze_danika_bankj_dump import decode, plausibility, reg, sx16

LINE_RE = re.compile(
    r"\bDANIKA_BANKAH\s+addr=(?P<addr>[0-9A-Fa-f]{8})\s+"
    r"off=(?P<off>[0-9A-Fa-f]+)\s+bytes=(?P<bytes>[0-9A-Fa-f]+)"
)

FUNCTIONS = (
    (0x801D0860, 0x801D0AAC, "func_801D0860"),
    (0x801D0AAC, 0x801D1508, "func_801D0AAC_setup"),
    (0x801D1508, 0x801D16D0, "func_801D1508_participant_alloc"),
)

LANDMARKS = (
    (0x801D16D0, 0x801D16E0, "SETUP_TABLE_16B"),
    (0x801F0CD0, 0x801F0D80, "UNIT_SLOT_TABLE_NEAR_801F0CD0"),
    (0x801CE8DC, 0x801CE8E0, "LIVE_BATTLE_PTR"),
    (0x80193BE0, 0x801951C0, "PERSISTENT_ROSTER_100x38"),
)

MEMORY_OPS = {
    0x20: "lb", 0x21: "lh", 0x23: "lw", 0x24: "lbu", 0x25: "lhu",
    0x28: "sb", 0x29: "sh", 0x2B: "sw",
}
STORE_OPS = {0x28, 0x29, 0x2B}


def parse(text: str) -> tuple[int, bytes] | None:
    chunks = []
    for line in text.splitlines():
        m = LINE_RE.search(line)
        if not m:
            continue
        chunks.append((int(m.group("addr"), 16), int(m.group("off"), 16), bytes.fromhex(m.group("bytes"))))
    if not chunks:
        return None
    bases = {base for base, _, _ in chunks}
    if len(bases) != 1:
        raise ValueError(f"inconsistent bank-AH bases: {sorted(bases)}")
    base = next(iter(bases))
    size = max(off + len(raw) for _, off, raw in chunks)
    buf = bytearray(size)
    filled = bytearray(size)
    for _, off, raw in chunks:
        for i, value in enumerate(raw):
            pos = off + i
            if filled[pos] and buf[pos] != value:
                raise ValueError(f"conflicting byte at +0x{pos:X}")
            buf[pos] = value
            filled[pos] = 1
    if not all(filled):
        first = next(i for i, value in enumerate(filled) if not value)
        raise ValueError(f"incomplete bank-AH dump, first missing +0x{first:X}")
    return base, bytes(buf)


def parts(word: int):
    return (
        (word >> 26) & 0x3F,
        (word >> 21) & 31,
        (word >> 16) & 31,
        (word >> 11) & 31,
        word & 0x3F,
        word & 0xFFFF,
    )


def landmark(address: int) -> str:
    for lo, hi, name in LANDMARKS:
        if lo <= address < hi:
            return name
    return ""


def analyze_function(base: int, data: bytes, start: int, end: int, endian: str):
    constants: dict[int, int] = {0: 0}
    absolute = []
    calls = []
    branches = []
    offset_hist = Counter()
    decoded_rows = []

    for pc in range(start, min(end, base + len(data)), 4):
        off = pc - base
        if off < 0 or off + 4 > len(data):
            continue
        word = int.from_bytes(data[off:off + 4], endian)
        text = decode(word, pc)
        decoded_rows.append((pc, word, text))
        op, rs, rt, rd, fn, imm = parts(word)
        simm = sx16(imm)

        mem = MEMORY_OPS.get(op)
        if mem:
            offset_hist[(reg(rs), simm, mem)] += 1
            if rs in constants:
                address = (constants[rs] + simm) & 0xFFFFFFFF
                absolute.append((pc, mem, address, rt, landmark(address), op in STORE_OPS))

        if op == 0x03:
            target = ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
            calls.append((pc, target))
        if op in {0x01, 0x02, 0x04, 0x05, 0x06, 0x07}:
            branches.append((pc, text))

        # Conservative straight-line constants. We intentionally drop values on
        # instructions we do not model rather than inventing an address.
        if op == 0x0F:  # lui
            constants[rt] = (imm << 16) & 0xFFFFFFFF
        elif op == 0x09 and rs in constants:  # addiu
            constants[rt] = (constants[rs] + simm) & 0xFFFFFFFF
        elif op == 0x0D and rs in constants:  # ori
            constants[rt] = constants[rs] | imm
        elif op == 0 and fn in {0x21, 0x25}:  # addu/or, useful for moves
            if rs in constants and rt in constants:
                constants[rd] = ((constants[rs] + constants[rt]) if fn == 0x21
                                 else (constants[rs] | constants[rt])) & 0xFFFFFFFF
            else:
                constants.pop(rd, None)
        else:
            # Instructions writing rt/rd invalidate a tracked constant unless
            # handled above. Loads are included here.
            if op in {0x08, 0x0A, 0x0B, 0x0C, 0x0E, 0x20, 0x21, 0x23, 0x24, 0x25}:
                constants.pop(rt, None)
            if op == 0 and fn in {0x00, 0x02, 0x03, 0x20, 0x22, 0x23, 0x24, 0x2A, 0x2B}:
                constants.pop(rd, None)

    return decoded_rows, absolute, calls, branches, offset_hist


def summarize(parsed: tuple[int, bytes] | None) -> str:
    out = [
        "Knight of Danika bank-AH battle-setup analysis",
        "===============================================",
    ]
    if parsed is None:
        out.append("No DANIKA_BANKAH records found.")
        return "\n".join(out) + "\n"

    base, data = parsed
    be = plausibility(data[:0xE70], "big")
    le = plausibility(data[:0xE70], "little")
    endian = "big" if be >= le else "little"
    out += [
        f"base=0x{base:08X} bytes=0x{len(data):X}",
        f"mips_score_big={be} mips_score_little={le} chosen={endian}",
        "",
        "Known upstream landmarks",
        "------------------------",
        "0x801D0860 func_801D0860",
        "0x801D0AAC func_801D0AAC_setup (reads 16-byte setup table at 0x801D16D0)",
        "0x801D1508 func_801D1508_participant_alloc (allocates/tags battle unit slot)",
    ]

    for start, end, name in FUNCTIONS:
        if not (base <= start < base + len(data)):
            continue
        rows, absolute, calls, branches, hist = analyze_function(base, data, start, end, endian)
        out += [
            "",
            f"[{name}] 0x{start:08X}..0x{end:08X}",
            f"instructions={len(rows)} absolute_refs={len(absolute)} calls={len(calls)} branches={len(branches)}",
            "absolute_memory_refs:",
        ]
        if not absolute:
            out.append("  -")
        for pc, op, address, rt, mark, is_store in absolute:
            suffix = f" >>> {mark}" if mark else ""
            kind = "STORE" if is_store else "LOAD"
            out.append(f"  0x{pc:08X} {kind} {op} {reg(rt)} @0x{address:08X}{suffix}")

        out.append("frequent_base_offsets:")
        if not hist:
            out.append("  -")
        for (base_reg, offset, op), count in hist.most_common(20):
            sign = f"+0x{offset:X}" if offset >= 0 else f"-0x{-offset:X}"
            out.append(f"  {count:3d}x {op} {sign}({base_reg})")

        out.append("calls:")
        if calls:
            out += [f"  0x{pc:08X} -> 0x{target:08X}" for pc, target in calls]
        else:
            out.append("  -")
        out.append("branches:")
        if branches:
            out += [f"  0x{pc:08X} {text}" for pc, text in branches]
        else:
            out.append("  -")
        out.append("decoded_function:")
        out += [f"  0x{pc:08X}: {word:08X}  {text}" for pc, word, text in rows]

    out += [
        "",
        "Interpretation rule",
        "-------------------",
        "This module executes at battle participant construction time, before bank J",
        "reuses the same RAM. Stores into a participant/unit field are therefore much",
        "stronger ownership candidates than renderer flags. Even so, do not name a",
        "field allied/enemy until its branch/store semantics are independently proven.",
        "A candidate side tag must also agree with the bank-C EXP eligibility path and",
        "must leave original enemy Danika class 0x71 on the vanilla selector path.",
    ]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    args = ap.parse_args()
    report = summarize(parse(args.log.read_text(encoding="utf-8", errors="replace")))
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
