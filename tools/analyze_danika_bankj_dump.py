#!/usr/bin/env python3
"""Decode DANIKA_BANKJ runtime byte snapshots and trace participant->roster flow.

Besides reconstructing streamed MIPS, this analyzer follows the distinctive
participant+0xF6 character index through local register dataflow.  It reports a
strong roster-bridge chain only when the same value is range-checked against 100
and participates in a 0x38-stride roster lookup reaching class +0x12.

This remains fail-closed: a roster bridge is not called allied by itself.  A true
ownership promotion still requires the streamed control flow to distinguish the
player roster from opposing/generated records, or independent runtime evidence.
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass
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


@dataclass
class Insn:
    pc: int
    word: int
    text: str


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
            score += 2
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
    if word == 0: return "nop"
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
    mem = {0x20:"lb",0x21:"lh",0x23:"lw",0x24:"lbu",0x25:"lhu",0x28:"sb",0x29:"sh",0x2B:"sw"}.get(op)
    if mem: return f"{mem} {reg(rt)}, {simm}({reg(rs)})"
    return f"op=0x{op:02X} raw=0x{word:08X}"


def field_hits(word: int) -> list[str]:
    op = (word >> 26) & 0x3F
    imm = word & 0xFFFF
    return [FIELD_NAMES[imm]] if op in KNOWN_OPS and imm in FIELD_NAMES else []


def decoded_stream(base: int, data: bytes, endian: str) -> list[Insn]:
    return [
        Insn(base + off, int.from_bytes(data[off:off+4], endian),
             decode(int.from_bytes(data[off:off+4], endian), base + off))
        for off in range(0, len(data) - 3, 4)
    ]


def trace_charidx_chains(insns: list[Insn]) -> list[list[str]]:
    """Bounded symbolic trace starting at lbu/lb reg,246(base)."""
    chains: list[list[str]] = []
    load_re = re.compile(r"\b(?:lbu|lb) (\$\w+), 246\((\$\w+)\)")
    copy_re = re.compile(r"\b(?:addu|or) (\$\w+), (\$\w+), \$zero\b")
    slti_re = re.compile(r"\bsltiu (\$\w+), (\$\w+), 0x0064\b")
    shift_re = re.compile(r"\bsll (\$\w+), (\$\w+), ([0-9]+)\b")
    add_re = re.compile(r"\baddu (\$\w+), (\$\w+), (\$\w+)\b")
    class_re = re.compile(r"\b(?:lbu|lb) (\$\w+), 18\((\$\w+)\)")

    for i, insn in enumerate(insns):
        m = load_re.search(insn.text)
        if not m:
            continue
        tainted = {m.group(1)}
        derived = set(tainted)
        range_checked = False
        shift2 = set()
        shift3 = set()
        stride38 = False
        roster_class = False
        evidence = [f"0x{insn.pc:08X} {insn.text}  [charidx seed]"]

        for cur in insns[i+1:min(len(insns), i+42)]:
            text = cur.text
            cm = copy_re.search(text)
            if cm and cm.group(2) in derived:
                derived.add(cm.group(1)); evidence.append(f"0x{cur.pc:08X} {text}  [propagate]")
            sm = slti_re.search(text)
            if sm and sm.group(2) in derived:
                range_checked = True; derived.add(sm.group(1)); evidence.append(f"0x{cur.pc:08X} {text}  [index<100]")
            sh = shift_re.search(text)
            if sh and sh.group(2) in derived:
                dest, _, amount = sh.groups(); derived.add(dest)
                if amount == "2": shift2.add(dest)
                if amount == "3": shift3.add(dest)
                evidence.append(f"0x{cur.pc:08X} {text}  [scaled index]")
            am = add_re.search(text)
            if am:
                dest, left, right = am.groups()
                if left in derived or right in derived:
                    derived.add(dest)
                # 0x38 = index*8 + index*? combinations are commonly built as
                # 7*8 or (index*8-index)*8. We conservatively accept only when
                # both independently derived shifted terms participate nearby.
                if ((left in shift2 and right in shift3) or
                    (left in shift3 and right in shift2)):
                    stride38 = True
                evidence.append(f"0x{cur.pc:08X} {text}" + ("  [derived add]" if dest in derived else ""))
            # Direct addiu by 56 to a tainted pointer also establishes stride use.
            if re.search(r"\baddiu (\$\w+), (\$\w+), 56\b", text):
                mm = re.search(r"\baddiu (\$\w+), (\$\w+), 56\b", text)
                if mm and mm.group(2) in derived:
                    stride38 = True; derived.add(mm.group(1)); evidence.append(f"0x{cur.pc:08X} {text}  [0x38 stride]")
            cl = class_re.search(text)
            if cl and cl.group(2) in derived:
                roster_class = True; evidence.append(f"0x{cur.pc:08X} {text}  [roster class +0x12]")

        status = []
        if range_checked: status.append("range100")
        if stride38: status.append("stride38")
        if roster_class: status.append("class12")
        evidence.insert(0, "chain=" + ("+".join(status) if status else "seed_only"))
        chains.append(evidence)
    return chains


def summarize(windows: dict[str, tuple[int, bytes]]) -> str:
    out = ["Knight of Danika bank-J runtime dump analysis", "=============================================="]
    if not windows:
        out.append("No DANIKA_BANKJ records found.")
        return "\n".join(out) + "\n"

    strong_chains = 0
    for name in sorted(windows):
        base, data = windows[name]
        be, le = plausibility(data, "big"), plausibility(data, "little")
        endian = "big" if be >= le else "little"
        nontrivial = len(set(data)) > 2 and any(data) and any(b != 0xFF for b in data)
        out += ["", f"[{name}] base=0x{base:08X} bytes=0x{len(data):X}",
                f"signal={'yes' if nontrivial else 'no'} mips_score_big={be} mips_score_little={le} chosen={endian}"]
        insns = decoded_stream(base, data, endian)
        hits = []
        for insn in insns:
            marks = field_hits(insn.word)
            suffix = f"  ; >>> {','.join(marks)}" if marks else ""
            out.append(f"0x{insn.pc:08X}: {insn.word:08X}  {insn.text}{suffix}")
            if marks: hits.append((insn.pc, marks, insn.text))
        out.append("field_hits=" + str(len(hits)))
        for pc, marks, text in hits:
            out.append(f"  HIT 0x{pc:08X} {','.join(marks)} :: {text}")

        chains = trace_charidx_chains(insns)
        out.append(f"charidx_chains={len(chains)}")
        for chain in chains:
            status = chain[0]
            if "range100" in status and "stride38" in status and "class12" in status:
                strong_chains += 1
                out.append("  ROSTER_BRIDGE_CHAIN=STRONG")
            else:
                out.append("  ROSTER_BRIDGE_CHAIN=PARTIAL")
            out.extend("    " + line for line in chain)

    out += ["", "Ownership synthesis", "-------------------",
            f"strong_participant_to_roster_chains={strong_chains}"]
    if strong_chains:
        out.append("participant_charidx_to_persistent_roster=SUPPORTED")
    else:
        out.append("participant_charidx_to_persistent_roster=UNPROVEN")
    out += [
        "ownership_side=UNKNOWN",
        "",
        "Interpretation rule",
        "-------------------",
        "A strong chain proves participant+0xF6 is used as a bounded index into the",
        "100x0x38 persistent roster and reaches class +0x12. It still does NOT by",
        "itself prove allied ownership. Promotion to DANIKA_SIDE_ALLIED requires",
        "either streamed control flow that excludes opposing/generated records or",
        "independent runtime correlation of both sides while holding class constant.",
    ]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    args = ap.parse_args()
    report = summarize(parse(args.log.read_text(encoding="utf-8", errors="replace")))
    if args.output: args.output.write_text(report, encoding="utf-8")
    else: print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
