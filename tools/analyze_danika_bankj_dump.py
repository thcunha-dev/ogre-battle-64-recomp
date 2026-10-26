#!/usr/bin/env python3
"""Decode DANIKA_BANKJ runtime byte snapshots as MIPS instructions.

The diagnostic mod may capture original streamed bank-J bytes directly from
RDRAM.  This tool reconstructs each named window and decodes the subset of MIPS
instructions useful for tracing participant/roster fields.  It is intentionally
an evidence tool: an immediate like +0xF6 is highlighted, but no field is called
allied/enemy without control-flow proof.
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

LINE_RE = re.compile(
    r"\bDANIKA_BANKJ\s+name=(?P<name>[A-Za-z0-9_]+)\s+"
    r"addr=(?P<addr>[0-9A-Fa-f]{8})\s+off=(?P<off>[0-9A-Fa-f]+)\s+"
    r"bytes=(?P<bytes>[0-9A-Fa-f]+)"
)

REG = [
    "$zero", "$at", "$v0", "$v1", "$a0", "$a1", "$a2", "$a3",
    "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7",
    "$s0", "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$s7",
    "$t8", "$t9", "$k0", "$k1", "$gp", "$sp", "$fp", "$ra",
]

FIELD_NAMES = {
    0x0031: "PART_LEVEL",
    0x0032: "PART_EXP",
    0x00F6: "PART_CHARIDX",
    0x00F8: "PART_STRIDE",
    0x01C4: "PART_OFF",
    0x020C: "PART_VALID",
    0x0012: "ROSTER_CLASS",
    0x0013: "ROSTER_LEVEL",
    0x0035: "ROSTER_EXP",
    0x0038: "ROSTER_STRIDE",
    0x0064: "CHAR_COUNT_100",
}

KNOWN_OPS = {
    0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B,
    0x0C, 0x0D, 0x0E, 0x0F, 0x20, 0x21, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2B,
}
KNOWN_SPECIAL = {0x00, 0x02, 0x03, 0x08, 0x09, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x2A, 0x2B}


def sx16(v: int) -> int:
    return v - 0x10000 if v & 0x8000 else v


def parse(text: str) -> dict[str, tuple[int, bytes]]:
    chunks: dict[str, list[tuple[int, int, bytes]]] = defaultdict(list)
    for line in text.splitlines():
        m = LINE_RE.search(line)
        if not m:
            continue
        raw = bytes.fromhex(m.group("bytes"))
        chunks[m.group("name")].append(
            (int(m.group("addr"), 16), int(m.group("off"), 16), raw)
        )

    out: dict[str, tuple[int, bytes]] = {}
    for name, entries in chunks.items():
        bases = {base for base, _, _ in entries}
        if len(bases) != 1:
            raise ValueError(f"{name}: inconsistent base addresses: {sorted(bases)}")
        base = next(iter(bases))
        size = max(off + len(raw) for _, off, raw in entries)
        buf = bytearray(size)
        filled = bytearray(size)
        for _, off, raw in entries:
            for i, b in enumerate(raw):
                pos = off + i
                if filled[pos] and buf[pos] != b:
                    raise ValueError(f"{name}: conflicting byte at +0x{pos:X}")
                buf[pos] = b
                filled[pos] = 1
        if not all(filled):
            missing = [i for i, v in enumerate(filled) if not v]
            raise ValueError(f"{name}: incomplete dump, first missing +0x{missing[0]:X}")
        out[name] = (base, bytes(buf))
    return out


def plausibility(data: bytes, endian: str) -> int:
    score = 0
    for i in range(0, len(data) - 3, 4):
        word = int.from_bytes(data[i:i+4], endian)
        if word == 0:
            score += 2  # nop is common
            continue
        op = (word >> 26) & 0x3F
        if op == 0:
            score += 3 if (word & 0x3F) in KNOWN_SPECIAL else -1
        elif op in KNOWN_OPS:
            score += 3
        else:
            score -= 1
    return score


def reg(n: int) -> str:
    return REG[n & 31]


def decode(word: int, pc: int) -> str:
    op = (word >> 26) & 0x3F
    rs = (word >> 21) & 31
    rt = (word >> 16) & 31
    rd = (word >> 11) & 31
    sa = (word >> 6) & 31
    fn = word & 0x3F
    imm = word & 0xFFFF
    simm = sx16(imm)

    if word == 0:
        return "nop"
    if op == 0:
        if fn == 0x00: return f"sll {reg(rd)}, {reg(rt)}, {sa}"
        if fn == 0x02: return f"srl {reg(rd)}, {reg(rt)}, {sa}"
        if fn == 0x03: return f"sra {reg(rd)}, {reg(rt)}, {sa}"
        if fn == 0x08: return f"jr {reg(rs)}"
        if fn == 0x09: return f"jalr {reg(rd)}, {reg(rs)}"
        if fn == 0x20: return f"add {reg(rd)}, {reg(rs)}, {reg(rt)}"
        if fn == 0x21: return f"addu {reg(rd)}, {reg(rs)}, {reg(rt)}"
        if fn == 0x22: return f"sub {reg(rd)}, {reg(rs)}, {reg(rt)}"
        if fn == 0x23: return f"subu {reg(rd)}, {reg(rs)}, {reg(rt)}"
        if fn == 0x24: return f"and {reg(rd)}, {reg(rs)}, {reg(rt)}"
        if fn == 0x25: return f"or {reg(rd)}, {reg(rs)}, {reg(rt)}"
        if fn == 0x2A: return f"slt {reg(rd)}, {reg(rs)}, {reg(rt)}"
        if fn == 0x2B: return f"sltu {reg(rd)}, {reg(rs)}, {reg(rt)}"
        return f"special fn=0x{fn:02X} raw=0x{word:08X}"

    target = ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
    branch = (pc + 4 + (simm << 2)) & 0xFFFFFFFF
    if op == 0x01:
        kind = {0x00: "bltz", 0x01: "bgez", 0x10: "bltzal", 0x11: "bgezal"}.get(rt)
        if kind: return f"{kind} {reg(rs)}, 0x{branch:08X}"
    if op == 0x02: return f"j 0x{target:08X}"
    if op == 0x03: return f"jal 0x{target:08X}"
    if op == 0x04: return f"beq {reg(rs)}, {reg(rt)}, 0x{branch:08X}"
    if op == 0x05: return f"bne {reg(rs)}, {reg(rt)}, 0x{branch:08X}"
    if op == 0x06: return f"blez {reg(rs)}, 0x{branch:08X}"
    if op == 0x07: return f"bgtz {reg(rs)}, 0x{branch:08X}"
    if op == 0x08: return f"addi {reg(rt)}, {reg(rs)}, {simm}"
    if op == 0x09: return f"addiu {reg(rt)}, {reg(rs)}, {simm}"
    if op == 0x0A: return f"slti {reg(rt)}, {reg(rs)}, {simm}"
    if op == 0x0B: return f"sltiu {reg(rt)}, {reg(rs)}, 0x{imm:04X}"
    if op == 0x0C: return f"andi {reg(rt)}, {reg(rs)}, 0x{imm:04X}"
    if op == 0x0D: return f"ori {reg(rt)}, {reg(rs)}, 0x{imm:04X}"
    if op == 0x0E: return f"xori {reg(rt)}, {reg(rs)}, 0x{imm:04X}"
    if op == 0x0F: return f"lui {reg(rt)}, 0x{imm:04X}"

    mem = {
        0x20: "lb", 0x21: "lh", 0x23: "lw", 0x24: "lbu", 0x25: "lhu",
        0x28: "sb", 0x29: "sh", 0x2B: "sw",
    }.get(op)
    if mem:
        return f"{mem} {reg(rt)}, {simm}({reg(rs)})"
    return f"op=0x{op:02X} raw=0x{word:08X}"


def field_hits(word: int) -> list[str]:
    op = (word >> 26) & 0x3F
    imm = word & 0xFFFF
    hits = []
    if op in KNOWN_OPS and imm in FIELD_NAMES:
        hits.append(FIELD_NAMES[imm])
    return hits


def summarize(windows: dict[str, tuple[int, bytes]]) -> str:
    out = [
        "Knight of Danika bank-J runtime dump analysis",
        "==============================================",
    ]
    if not windows:
        out.append("No DANIKA_BANKJ records found.")
        return "\n".join(out) + "\n"

    for name in sorted(windows):
        base, data = windows[name]
        be = plausibility(data, "big")
        le = plausibility(data, "little")
        endian = "big" if be >= le else "little"
        nontrivial = len(set(data)) > 2 and any(data) and any(b != 0xFF for b in data)
        out += [
            "",
            f"[{name}] base=0x{base:08X} bytes=0x{len(data):X}",
            f"signal={'yes' if nontrivial else 'no'} mips_score_big={be} mips_score_little={le} chosen={endian}",
        ]
        hits = []
        for off in range(0, len(data) - 3, 4):
            word = int.from_bytes(data[off:off+4], endian)
            pc = base + off
            decoded = decode(word, pc)
            marks = field_hits(word)
            suffix = f"  ; >>> {','.join(marks)}" if marks else ""
            out.append(f"0x{pc:08X}: {word:08X}  {decoded}{suffix}")
            if marks:
                hits.append((pc, marks, decoded))
        out.append("field_hits=" + str(len(hits)))
        for pc, marks, decoded in hits:
            out.append(f"  HIT 0x{pc:08X} {','.join(marks)} :: {decoded}")

    out += [
        "",
        "Interpretation rule",
        "-------------------",
        "PART_CHARIDX (+0xF6) is only an identity/roster bridge until surrounding",
        "control flow proves ownership semantics. A load/store hit alone is not an",
        "allied/enemy proof. If the dump contains real MIPS, inspect branches and",
        "the participant->record / record->participant dataflow around highlighted hits.",
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
