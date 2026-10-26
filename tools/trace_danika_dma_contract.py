#!/usr/bin/env python3
"""Trace the exact ABI contract of func_8009DA50 used by the Danika bank-AH probe.

The runtime probe hooks this routine after return to capture the transient battle
setup bank.  This report makes the hook's a0/a1/a2 assumption reviewable from the
tracked resident assembly instead of leaving it as an undocumented guess.

No gameplay semantics are inferred here.  In particular, this script does not
label any participant as allied/enemy; it only records the DMA wrapper body and
all tracked call sites with the argument-setup window that precedes each call.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ASM = ROOT / "asm"
OUT = ROOT / "danika-dma-contract.txt"
TARGET = "func_8009DA50"

FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
ADDR_RE = re.compile(r"/\*\s*[0-9A-Fa-f]+\s+([0-9A-Fa-f]{8})\s+[0-9A-Fa-f]{8}\s*\*/")
ARG_WRITE_RE = re.compile(
    r"\b(?:lui|li|la|move|addu|addiu|ori|or|lw|lhu|lh|lbu|lb|sll|srl|andi)\s+\$(a[0-3])\b",
    re.I,
)


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
        active = None
        start = 0
        for i, line in enumerate(lines):
            m = FUNC_RE.match(line)
            if m:
                active = m.group(1)
                start = i
            e = END_RE.match(line)
            if e and active == e.group(1):
                funcs[active] = Func(
                    active, path.relative_to(ROOT), start + 1, i + 1,
                    lines[start:i + 1],
                )
                active = None
    return funcs


def instruction_addresses(body: list[str]) -> list[int]:
    out = []
    for line in body:
        m = ADDR_RE.search(line)
        if m:
            out.append(int(m.group(1), 16))
    return out


def main() -> int:
    funcs = parse_funcs()
    if TARGET not in funcs:
        raise SystemExit(f"missing {TARGET}")
    target = funcs[TARGET]

    addrs = instruction_addresses(target.body)
    if not addrs:
        raise SystemExit(f"{TARGET}: no instruction addresses parsed")
    start_addr = min(addrs)
    end_exclusive = max(addrs) + 4
    size = end_exclusive - start_addr
    if start_addr != 0x8009DA50:
        raise SystemExit(f"{TARGET}: unexpected start 0x{start_addr:08X}")
    if size != 0x9C:
        raise SystemExit(f"{TARGET}: unexpected size 0x{size:X}, expected 0x9C")

    callers = []
    for func in funcs.values():
        for i, line in enumerate(func.body):
            m = CALL_RE.search(line)
            if m and m.group(1) == TARGET:
                callers.append((func, i))

    report = [
        "Knight of Danika DMA hook contract trace",
        "========================================",
        "",
        f"target={TARGET}",
        f"location={target.path}:{target.start}-{target.end}",
        f"vram_start=0x{start_addr:08X}",
        f"code_size=0x{size:X}",
        f"tracked_callers={len(callers)}",
        "",
        "Target body",
        "-----------",
    ]
    for n, line in enumerate(target.body, start=target.start):
        report.append(f"{n}: {line}")

    report += ["", "Caller argument setup", "---------------------"]
    arg_hits = 0
    for func, idx in callers:
        call_line = func.start + idx
        lo = max(0, idx - 32)
        hi = min(len(func.body), idx + 5)
        report += [
            "",
            f"## {func.name} {func.path}:{func.start}-{func.end} call@{call_line}",
        ]
        for j in range(lo, hi):
            line = func.body[j]
            mark = ">>>" if j == idx else "   "
            tags = []
            aw = ARG_WRITE_RE.search(line)
            if aw:
                tags.append("writes_$" + aw.group(1).lower())
                arg_hits += 1
            if "0x23A370" in line or "23A370" in line:
                tags.append("BANK_AH_ROM")
            if "0x801D0860" in line or "801D0860" in line:
                tags.append("BANK_AH_RAM")
            if re.search(r"(?:0x0*E80|\b3712\b)", line, re.I):
                tags.append("BANK_AH_SIZE")
            suffix = "  # " + ",".join(tags) if tags else ""
            report.append(f"{mark} {func.start + j}: {line}{suffix}")

    report += [
        "",
        "Hook acceptance rule",
        "--------------------",
        "RECOMP_HOOK_RETURN(func_8009DA50) may treat a0/a1/a2 as ROM/RAM/size only",
        "after the target body/caller dataflow demonstrates that ordering.  Merely",
        "matching three plausible numeric values is not enough.  If ordering remains",
        "ambiguous, the bank-AH capture must stay diagnostic-only and fail closed.",
        "",
        "Expected capture constants once ABI is proven:",
        "  ROM  = 0x0023A370",
        "  RAM  = 0x801D0860",
        "  SIZE = 0x00000E80",
    ]

    OUT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(
        f"Danika DMA contract trace: PASS (start=0x{start_addr:08X}, "
        f"size=0x{size:X}, callers={len(callers)}, arg_writes={arg_hits})"
    )
    print(f"report={OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
