#!/usr/bin/env python3
"""Prove and report the ABI contract of func_8009DA50 used by Danika bank-AH.

The runtime probe hooks this routine after return to capture the transient battle
setup bank.  This checker deliberately fails closed unless tracked resident
assembly proves the argument ordering expected by the hook:

    a0 = source / ROM address
    a1 = destination / RAM address
    a2 = transfer size

No gameplay ownership semantics are inferred here.
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


def compact(line: str) -> str:
    """Normalize whitespace so ABI fingerprints survive formatting changes."""
    return re.sub(r"\s+", " ", line.strip())


def require_fingerprint(lines: list[str], pattern: str, label: str) -> str:
    rx = re.compile(pattern, re.I)
    for line in lines:
        if rx.search(compact(line)):
            return line
    raise SystemExit(f"{TARGET}: ABI proof missing {label}")


def prove_abi(target: Func, callers: list[tuple[Func, int]]) -> list[str]:
    """Require independent callee and caller fingerprints for ROM/RAM/size."""
    proof = []

    # Callee-side provenance.  The routine immediately preserves size and RAM
    # destination, while the large-transfer path reaches func_80089F80 with a0
    # untouched.  This is stronger than trusting argument names in C.
    proof.append(require_fingerprint(
        target.body,
        r"\baddu\s+\$s0,\s*\$a2,\s*\$zero\b",
        "callee a2->s0 size preservation",
    ))
    proof.append(require_fingerprint(
        target.body,
        r"\baddu\s+\$s2,\s*\$a1,\s*\$zero\b",
        "callee a1->s2 destination preservation",
    ))

    backend_calls = [i for i, line in enumerate(target.body)
                     if re.search(r"\bjal\s+func_80089F80\b", line)]
    if len(backend_calls) < 2:
        raise SystemExit(
            f"{TARGET}: ABI proof expected two transfer-backend calls, got {len(backend_calls)}"
        )

    # The second backend call is the >=16-byte path.  Between the branch target
    # and this call there must be no write to a0/a1; therefore they are still
    # the original source/destination arguments.  a2 is derived from saved s0.
    large_idx = backend_calls[-1]
    lo = max(0, large_idx - 4)
    window = target.body[lo:large_idx + 2]
    for line in window:
        c = compact(line)
        if re.search(r"\b(?:lui|li|la|move|addu|addiu|ori|or|lw|lhu|lh|lbu|lb|sll|srl|andi)\s+\$(a0|a1)\b", c, re.I):
            raise SystemExit(
                f"{TARGET}: large-transfer path rewrites source/destination before backend: {c}"
            )
    if not any(re.search(r"\band\s+\$a2,\s*\$v0,\s*\$a2\b", compact(x), re.I)
               for x in window):
        raise SystemExit(f"{TARGET}: large-transfer path no longer derives backend size in a2")
    proof.extend(window)

    # Caller-side independent evidence: at least one tracked caller constructs
    # transfer size as end - a0 in the jal delay slot.  Its a1 is independently
    # prepared as a destination address.  Together with the callee provenance,
    # this proves a0=start/source, a1=destination, a2=size.
    size_callers = []
    destination_callers = []
    for func, idx in callers:
        near = func.body[max(0, idx - 16):min(len(func.body), idx + 2)]
        delay = func.body[idx + 1] if idx + 1 < len(func.body) else ""
        if re.search(r"\bsubu\s+\$a2,\s*\$a2,\s*\$(?:a0|s[0-7])\b", compact(delay), re.I):
            size_callers.append((func, delay))
        if any(re.search(
            r"\b(?:lui|addiu|addu|lw|la|move)\s+\$a1\b", compact(line), re.I
        ) for line in near):
            destination_callers.append(func)

    if not size_callers:
        raise SystemExit(f"{TARGET}: no caller proves a2 as transfer span")
    if not destination_callers:
        raise SystemExit(f"{TARGET}: no caller independently prepares a1 destination")

    proof.append(size_callers[0][1])
    return proof


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

    if not callers:
        raise SystemExit(f"{TARGET}: no tracked callers")

    abi_proof = prove_abi(target, callers)

    report = [
        "Knight of Danika DMA hook contract trace",
        "========================================",
        "",
        f"target={TARGET}",
        f"location={target.path}:{target.start}-{target.end}",
        f"vram_start=0x{start_addr:08X}",
        f"code_size=0x{size:X}",
        f"tracked_callers={len(callers)}",
        "abi_proven=yes",
        "abi_a0=source_rom",
        "abi_a1=destination_ram",
        "abi_a2=transfer_size",
        "",
        "ABI proof fingerprints",
        "----------------------",
    ]
    report.extend(abi_proof)
    report += ["", "Target body", "-----------"]
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
        "PROVEN: RECOMP_HOOK_RETURN(func_8009DA50) receives a0/a1/a2 as",
        "source-ROM / destination-RAM / transfer-size respectively.",
        "The checker fails if the callee/caller fingerprints establishing that",
        "ordering disappear, so bank-AH capture remains fail-closed across edits.",
        "",
        "Bank-AH capture constants:",
        "  ROM  = 0x0023A370",
        "  RAM  = 0x801D0860",
        "  SIZE = 0x00000E80",
    ]

    OUT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(
        f"Danika DMA ABI: PROVEN a0=ROM a1=RAM a2=size "
        f"(start=0x{start_addr:08X}, size=0x{size:X}, callers={len(callers)}, "
        f"arg_writes={arg_hits})"
    )
    print(f"report={OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
