#!/usr/bin/env python3
"""Decode DANIKA_BANKC EXP-filter snapshots and rank ownership predicates.

The battle-result EXP loop calls five bank-C predicates on each live participant
before considering that participant eligible for EXP.  This tool reuses the
runtime MIPS decoder, then adds a function-oriented pass that isolates each known
predicate, follows simple aliases of the participant pointer in $a0, reports
participant-relative memory accesses, branches/calls, and common boolean-return
forms.  It is evidence-only: a predicate is never called allied/enemy solely
because it reads a particular field.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from analyze_danika_bankj_dump import (
    decode,
    parse as parse_shared,
    plausibility,
    reg,
    summarize as summarize_shared,
    sx16,
)

FUNCTIONS = (
    (0x801C8B88, "func_801C8B88", True),
    (0x801C8BA4, "func_801C8BA4", True),
    (0x801C8C5C, "func_801C8C5C", True),
    (0x801C8E50, "func_801C8E50", True),
    (0x801C8EBC, "func_801C8EBC", True),
    (0x801C9008, "func_801C9008(index)->participant", False),
)

MEMORY_OPS = {
    0x20: "lb", 0x21: "lh", 0x23: "lw", 0x24: "lbu", 0x25: "lhu",
    0x28: "sb", 0x29: "sh", 0x2B: "sw",
}
BRANCH_OPS = {0x01, 0x04, 0x05, 0x06, 0x07}

FIELD_LABELS = {
    0x20: "PART_FIELD_20",
    0x31: "PART_LEVEL",
    0x32: "PART_EXP",
    0x4B: "PART_FIELD_4B",
    0x4F: "PART_FIELD_4F",
    0xF6: "PART_CHARIDX",
}


@dataclass
class FunctionEvidence:
    address: int
    name: str
    predicate: bool
    instructions: list[tuple[int, int, str]]
    accesses: list[tuple[int, str, int, str]]
    branches: list[tuple[int, str]]
    calls: list[tuple[int, int]]
    return_forms: list[tuple[int, str]]
    saw_return: bool


def parse(text: str):
    # Reuse the byte reconstruction / endian-safe MIPS decoder verbatim; the
    # wire format is deliberately identical except for the BANKC/BANKJ marker.
    return parse_shared(text.replace("DANIKA_BANKC", "DANIKA_BANKJ"))


def _parts(word: int):
    return (
        (word >> 26) & 0x3F,
        (word >> 21) & 31,
        (word >> 16) & 31,
        (word >> 11) & 31,
        word & 0x3F,
        word & 0xFFFF,
    )


def _writes_register(word: int, register: int) -> bool:
    op, _rs, rt, rd, fn, _imm = _parts(word)
    if register == 0:
        return False
    if op == 0:
        return rd == register and fn in {
            0x00, 0x02, 0x03, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x2A, 0x2B,
        }
    if op in {
        0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F,
        0x20, 0x21, 0x23, 0x24, 0x25,
    }:
        return rt == register
    return False


def _alias_assignment(word: int, aliases: set[int]) -> int | None:
    op, rs, rt, rd, fn, imm = _parts(word)
    # move dst,src encodings commonly emitted by GCC for pointers.
    if op == 0 and fn in {0x21, 0x25}:  # addu/or
        if rs in aliases and rt == 0:
            return rd
        if rt in aliases and rs == 0:
            return rd
    if op in {0x09, 0x0D} and imm == 0 and rs in aliases:  # addiu/ori
        return rt
    return None


def _return_form(word: int, decoded: str) -> str | None:
    op, rs, rt, rd, fn, imm = _parts(word)
    # Constant returns.
    if op == 0x09 and rt == 2 and rs == 0:
        return f"v0=constant {sx16(imm)}"
    if op == 0x0D and rt == 2 and rs == 0:
        return f"v0=constant 0x{imm:X}"
    if op == 0 and rd == 2 and fn in {0x21, 0x25} and rs == 0 and rt == 0:
        return "v0=constant 0"
    # Common boolean normalizers / comparisons.
    if op in {0x0A, 0x0B} and rt == 2:
        return f"v0=compare ({decoded})"
    if op == 0 and rd == 2 and fn in {0x2A, 0x2B}:
        return f"v0=compare ({decoded})"
    if op in {0x0C, 0x0E} and rt == 2:
        return f"v0=bit-test/transform ({decoded})"
    return None


def _slice_function(base: int, data: bytes, address: int, hard_end: int,
                    endian: str, name: str, predicate: bool) -> FunctionEvidence | None:
    start = address - base
    if start < 0 or start + 4 > len(data):
        return None
    hard_end = min(hard_end, base + len(data))
    if hard_end <= address:
        return None

    aliases = {4}  # $a0 = participant pointer for the five predicates.
    instructions: list[tuple[int, int, str]] = []
    accesses: list[tuple[int, str, int, str]] = []
    branches: list[tuple[int, str]] = []
    calls: list[tuple[int, int]] = []
    return_forms: list[tuple[int, str]] = []
    saw_return = False
    stop_after_delay = False

    pc = address
    while pc + 4 <= hard_end:
        off = pc - base
        word = int.from_bytes(data[off:off + 4], endian)
        decoded = decode(word, pc)
        instructions.append((pc, word, decoded))
        op, rs, rt, _rd, fn, imm = _parts(word)

        mem_name = MEMORY_OPS.get(op)
        if mem_name and rs in aliases:
            offset = sx16(imm)
            label = FIELD_LABELS.get(offset, "") if offset >= 0 else ""
            accesses.append((pc, mem_name, offset, label))

        if op in BRANCH_OPS or op == 0x02:
            branches.append((pc, decoded))
        if op == 0x03:
            target = ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
            calls.append((pc, target))

        form = _return_form(word, decoded)
        if form:
            return_forms.append((pc, form))

        alias_dst = _alias_assignment(word, aliases)
        if alias_dst is not None and alias_dst != 0:
            aliases.add(alias_dst)
        # Kill stale aliases when the same register is overwritten by a real
        # non-alias assignment. This keeps the report conservative.
        for alias in tuple(aliases):
            if alias == 4:
                continue
            if _writes_register(word, alias) and alias != alias_dst:
                aliases.discard(alias)

        if stop_after_delay:
            break
        if op == 0 and fn == 0x08 and rs == 31:  # jr $ra
            saw_return = True
            stop_after_delay = True
        pc += 4

    return FunctionEvidence(
        address=address,
        name=name,
        predicate=predicate,
        instructions=instructions,
        accesses=accesses,
        branches=branches,
        calls=calls,
        return_forms=return_forms,
        saw_return=saw_return,
    )


def analyze_functions(windows) -> list[FunctionEvidence]:
    if "exp_filters" not in windows:
        return []
    base, data = windows["exp_filters"]
    be = plausibility(data, "big")
    le = plausibility(data, "little")
    endian = "big" if be >= le else "little"

    rows: list[FunctionEvidence] = []
    for i, (address, name, predicate) in enumerate(FUNCTIONS):
        hard_end = FUNCTIONS[i + 1][0] if i + 1 < len(FUNCTIONS) else base + len(data)
        item = _slice_function(base, data, address, hard_end, endian, name, predicate)
        if item is not None:
            rows.append(item)
    return rows


def _format_offset(offset: int) -> str:
    return f"+0x{offset:X}" if offset >= 0 else f"-0x{-offset:X}"


def _interest(row: FunctionEvidence) -> str:
    if not row.predicate:
        return "n/a"
    if row.accesses and row.return_forms:
        return "high"
    if row.accesses or row.return_forms:
        return "medium"
    return "low"


def summarize(windows) -> str:
    base_report = summarize_shared(windows)
    lines = [
        base_report.rstrip(),
        "",
        "Bank-C EXP eligibility landmarks",
        "--------------------------------",
    ]
    for address, name, _predicate in FUNCTIONS:
        lines.append(f"0x{address:08X} {name}")

    rows = analyze_functions(windows)
    lines += [
        "",
        "Per-function participant dataflow",
        "---------------------------------",
    ]
    if not rows:
        lines.append("No exp_filters window covers the known bank-C functions.")
    for row in rows:
        lines += [
            "",
            f"[{row.name}] start=0x{row.address:08X} predicate={'yes' if row.predicate else 'no'} "
            f"ownership_review_interest={_interest(row)} return={'yes' if row.saw_return else 'not-seen'}",
            f"instruction_count={len(row.instructions)} participant_accesses={len(row.accesses)} "
            f"branches={len(row.branches)} calls={len(row.calls)} return_forms={len(row.return_forms)}",
        ]
        if row.accesses:
            lines.append("participant_relative_accesses:")
            for pc, op, offset, label in row.accesses:
                suffix = f" {label}" if label else ""
                lines.append(f"  0x{pc:08X} {op} {_format_offset(offset)}($a0/alias){suffix}")
        else:
            lines.append("participant_relative_accesses: -")

        if row.return_forms:
            lines.append("return_forms:")
            lines += [f"  0x{pc:08X} {text}" for pc, text in row.return_forms]
        else:
            lines.append("return_forms: -")

        if row.branches:
            lines.append("branches:")
            lines += [f"  0x{pc:08X} {text}" for pc, text in row.branches]
        else:
            lines.append("branches: -")

        if row.calls:
            lines.append("calls:")
            lines += [f"  0x{pc:08X} jal 0x{target:08X}" for pc, target in row.calls]
        else:
            lines.append("calls: -")

        lines.append("decoded_function:")
        lines += [f"  0x{pc:08X}: {word:08X}  {text}" for pc, word, text in row.instructions]

    lines += [
        "",
        "Ownership target",
        "----------------",
        "Independent upstream disassembly confirms that the battle-result EXP loop",
        "calls func_801C9008 for each of 20 participant indices, then applies the",
        "five predicates above before using participant level/class-derived values.",
        "Therefore one or more predicates encode EXP eligibility, and a side/team",
        "test is a strong candidate, but the report still requires instruction-level",
        "proof before promoting any field or predicate to DANIKA_SIDE_ALLIED.",
        "",
        "Review the high-interest predicates first: a small participant-relative",
        "load feeding a compare/branch and a 0/1 return is the exact shape expected",
        "for a side/status filter. Reproduce the interpretation against a second",
        "battle capture or an independent control-flow source before activation.",
        "Do not promote a predicate merely because it differs between two captures.",
    ]
    return "\n".join(lines) + "\n"


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
