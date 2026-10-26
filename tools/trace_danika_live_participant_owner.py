#!/usr/bin/env python3
"""Trace ownership/team candidates from the verified live battle participant layout.

This is an evidence-only scanner.  It starts from the participant layout already
verified by the EXP-overflow mod and looks for tracked assembly functions that
use the distinctive offsets/stride, especially branches fed by the roster index
at +0xF6.  It does not promote any field to allied/enemy by itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ASM = ROOT / "asm"
OUT = ROOT / "danika-live-participant-owner.txt"

FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")

# Verified layout from mods/exp-overflow/src/exp_overflow.c.
OFF_PART = 0x1C4
OFF_VALID = 0x20C
OFF_LEVEL = 0x31
OFF_EXP = 0x32
OFF_ROSTER = 0xF6
STRIDE = 0xF8
BATTLE_PTR = "D_801CE8DC"
CHAR_TABLE = "D_80193BE0"

OFFSET_PATTERNS = {
    "part_payload_1c4": re.compile(r"(?<![0-9A-Fa-f])0x0*1c4(?![0-9A-Fa-f])", re.I),
    "slot_valid_20c": re.compile(r"(?<![0-9A-Fa-f])0x0*20c(?![0-9A-Fa-f])", re.I),
    "part_level_31": re.compile(r"(?<![0-9A-Fa-f])0x0*31\s*\(", re.I),
    "part_exp_32": re.compile(r"(?<![0-9A-Fa-f])0x0*32\s*\(", re.I),
    "roster_f6": re.compile(r"(?<![0-9A-Fa-f])0x0*f6\s*\(", re.I),
    "stride_f8": re.compile(r"(?<![0-9A-Fa-f])0x0*f8(?![0-9A-Fa-f])", re.I),
}

ROSTER_LOAD_RE = re.compile(
    r"\b(?:lbu|lb|lhu|lh|lw)\s+(\$[A-Za-z0-9]+),\s*0x0*f6\s*\((\$[A-Za-z0-9]+)\)",
    re.I,
)
BRANCH_RE = re.compile(r"\b(?:beq|bne|beql|bnel|bgez|bgtz|blez|bltz|slti|sltiu|slt|sltu|andi|xori)\b", re.I)
IMM_COMPARE_RE = re.compile(r"\b(?:slti|sltiu|andi|xori|addiu|ori)\b.*?(?:0x[0-9A-Fa-f]+|\b\d+\b)", re.I)
MEM_RE = re.compile(r"\b(?:lbu|lb|lhu|lh|lw|sb|sh|sw)\b")


@dataclass
class Func:
    name: str
    path: Path
    start: int
    end: int
    body: list[str]


def parse_funcs() -> dict[str, Func]:
    funcs: dict[str, Func] = {}
    for path in sorted(ASM.rglob("*.s")):
        if "/data/" in path.as_posix():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        active_name: str | None = None
        active_start = 0
        for i, line in enumerate(lines):
            m = FUNC_RE.match(line)
            if m:
                active_name = m.group(1)
                active_start = i
            e = END_RE.match(line)
            if e and active_name == e.group(1):
                funcs[active_name] = Func(
                    active_name,
                    path.relative_to(ROOT),
                    active_start + 1,
                    i + 1,
                    lines[active_start : i + 1],
                )
                active_name = None
    return funcs


def tags_for(body: list[str]) -> set[str]:
    tags: set[str] = set()
    for line in body:
        if BATTLE_PTR in line:
            tags.add("battle_ptr")
        if CHAR_TABLE in line:
            tags.add("char_table")
        for tag, pat in OFFSET_PATTERNS.items():
            if pat.search(line):
                tags.add(tag)
    return tags


def context(body: list[str], idx: int, before: int = 18, after: int = 28) -> list[tuple[int, str]]:
    lo = max(0, idx - before)
    hi = min(len(body), idx + after + 1)
    return [(j, body[j]) for j in range(lo, hi)]


def branch_candidates(func: Func) -> list[tuple[int, str, list[tuple[int, str]]]]:
    out = []
    for i, line in enumerate(func.body):
        load = ROSTER_LOAD_RE.search(line)
        if not load:
            continue
        reg = re.escape(load.group(1))
        # Follow a bounded local window.  We deliberately report rather than
        # claim dataflow because MIPS delay slots/register copies need review.
        window = func.body[i + 1 : min(len(func.body), i + 22)]
        evidence = []
        for rel, candidate in enumerate(window, start=i + 1):
            if re.search(rf"(?<![A-Za-z0-9_]){reg}(?![A-Za-z0-9_])", candidate) and (
                BRANCH_RE.search(candidate) or IMM_COMPARE_RE.search(candidate) or MEM_RE.search(candidate)
            ):
                evidence.append((rel, candidate))
        out.append((i, line, evidence))
    return out


def score(tags: set[str], branches: list[tuple[int, str, list[tuple[int, str]]]]) -> int:
    value = 0
    value += 40 if "roster_f6" in tags else 0
    value += 24 if "battle_ptr" in tags else 0
    value += 18 if "slot_valid_20c" in tags else 0
    value += 16 if "part_payload_1c4" in tags else 0
    value += 16 if "stride_f8" in tags else 0
    value += 8 if "part_level_31" in tags else 0
    value += 8 if "part_exp_32" in tags else 0
    value += 8 if "char_table" in tags else 0
    value += 12 * sum(bool(ev) for _, _, ev in branches)
    return value


def main() -> None:
    funcs = parse_funcs()
    rows = []
    for func in funcs.values():
        tags = tags_for(func.body)
        branches = branch_candidates(func)
        if not tags and not branches:
            continue
        s = score(tags, branches)
        if s == 0:
            continue
        calls = sorted({m.group(1) for line in func.body if (m := CALL_RE.search(line))})
        rows.append((s, func, tags, branches, calls))
    rows.sort(key=lambda r: (-r[0], r[1].name))

    report = [
        "Knight of Danika live battle participant ownership trace",
        "========================================================",
        "",
        "Verified participant contract used as seeds:",
        "  battle_state_ptr = *(0x801CE8DC)",
        "  slot_stride      = 0xF8",
        "  participant      = slot + 0x1C4",
        "  slot_valid       = slot + 0x20C (word != 0)",
        "  participant+31   = level",
        "  participant+32   = EXP",
        "  participant+F6   = roster/character index",
        "  roster class     = D_80193BE0[index*0x38 + 0x12]",
        "",
        f"tracked_asm_functions={len(funcs)}",
        f"seed_matches={len(rows)}",
        "",
        "Ranked functions",
        "----------------",
    ]

    for s, func, tags, branches, calls in rows[:80]:
        report.append(
            f"score={s:3d} {func.name} {func.path}:{func.start}-{func.end} "
            f"tags={','.join(sorted(tags)) or '-'} calls={','.join(calls) or '-'}"
        )

    report += ["", "Roster-index branch/dataflow candidates", "--------------------------------------"]
    branch_count = 0
    for s, func, tags, branches, _ in rows:
        for idx, load_line, evidence in branches:
            branch_count += 1
            abs_line = func.start + idx
            report += [
                "",
                f"## score={s} {func.name} {func.path}:{abs_line}",
                f"load: {load_line.strip()}",
                "nearby_uses:",
            ]
            if evidence:
                report += [f"  {func.start + j}: {line.strip()}" for j, line in evidence]
            else:
                report.append("  -")
            report.append("context:")
            report += [f"  {func.start + j:6d}: {line}" for j, line in context(func.body, idx)]

    report += [
        "",
        f"roster_load_sites={branch_count}",
        "",
        "Participant-layout co-occurrence candidates",
        "------------------------------------------",
    ]
    for s, func, tags, _, _ in rows:
        core = {"stride_f8", "part_payload_1c4", "slot_valid_20c"}
        if len(tags & core) >= 2 or ("roster_f6" in tags and tags & core):
            report.append(
                f"score={s:3d} {func.name} {func.path}:{func.start}-{func.end} "
                f"tags={','.join(sorted(tags))}"
            )

    report += [
        "",
        "Acceptance rule",
        "---------------",
        "Do NOT call +0xF6 or any neighbouring byte allied/enemy merely because it",
        "differs in a capture.  Ownership is promoted only if control flow or a",
        "downstream table lookup proves a side semantic, or if reproduced runtime",
        "captures correlate the same field with both sides while holding class",
        "constant.  Until then DanikaSide stays UNKNOWN and the override stays off.",
        "",
        "Bank-J note",
        "-----------",
        "The actual result-loop functions func_ovlJ_* live in generated bank J code",
        "(bankRec10a, ROM 0x213AE0 -> VRAM 0x801D0860) and are gitignored.  This",
        "scanner therefore reports every ownership clue available in the tracked",
        "resident assembly and explicitly does not pretend the missing generated",
        "bank assembly was inspected.",
    ]

    text = "\n".join(report) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
