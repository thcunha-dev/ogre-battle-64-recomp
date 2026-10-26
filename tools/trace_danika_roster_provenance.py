#!/usr/bin/env python3
"""Formalize what is and is not proven about D_80193BE0.

This report intentionally separates two claims:
  1. D_80193BE0 is a persistent 100-record character roster (proven here).
  2. A battle participant backed by that roster is always allied (NOT proven by
     the tracked resident assembly; bank-J/runtime evidence is still required).
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ASM = ROOT / "asm"
OUT = ROOT / "danika-roster-provenance.txt"

FUNC_RE = re.compile(r"^\s*glabel\s+(\S+)")
END_RE = re.compile(r"^\s*endlabel\s+(\S+)")


def functions() -> dict[str, tuple[Path, int, list[str]]]:
    out = {}
    for path in sorted(ASM.rglob("*.s")):
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
                out[active] = (path.relative_to(ROOT), start + 1, lines[start:i+1])
                active = None
    return out


def require(body: str, tokens: tuple[str, ...], label: str) -> None:
    for token in tokens:
        if token not in body:
            raise SystemExit(f"{label}: missing expected evidence {token!r}")


def excerpt(lines: list[str], needles: tuple[str, ...], radius: int = 3) -> list[str]:
    picked = set()
    for i, line in enumerate(lines):
        if any(n in line for n in needles):
            picked.update(range(max(0, i-radius), min(len(lines), i+radius+1)))
    return [f"  {i+1:5d}: {lines[i]}" for i in sorted(picked)]


def main() -> None:
    funcs = functions()
    required_names = ("func_8019BB9C", "func_80184D90", "func_8016B774")
    for name in required_names:
        if name not in funcs:
            raise SystemExit(f"missing function {name}")

    clear_path, clear_start, clear_lines = funcs["func_8019BB9C"]
    clear_body = "\n".join(clear_lines)
    require(clear_body, (
        "D_80193BE0", "func_80093380", "0x15E0", "func_80184D90",
    ), "func_8019BB9C")

    init_path, init_start, init_lines = funcs["func_80184D90"]
    init_body = "\n".join(init_lines)
    require(init_body, ("D_80193BE0",), "func_80184D90")

    scan_path, scan_start, scan_lines = funcs["func_8016B774"]
    scan_body = "\n".join(scan_lines)
    require(scan_body, (
        "D_80193BE0", "0x38", "0x64", "0x11", "0x12",
    ), "func_8016B774")

    stride = 0x38
    total = 0x15E0
    count = total // stride
    assert count == 100 and total % stride == 0

    report = [
        "Knight of Danika persistent roster provenance",
        "==============================================",
        "",
        "Proven structural facts",
        "-----------------------",
        f"D_80193BE0 reset span = 0x{total:X} bytes",
        f"record stride          = 0x{stride:X} bytes",
        f"record count           = {count}",
        "class byte             = +0x12 (already proven by class-to-battle trace)",
        "presence/history byte  = +0x11 (used by roster scan before class dispatch)",
        "",
        "Evidence A: whole-roster reset then initializer",
        "-----------------------------------------------",
        f"func_8019BB9C @ {clear_path}:{clear_start}",
        "The function passes D_80193BE0 and length 0x15E0 to the same bulk-clear",
        "routine used for other game-state arrays, then calls func_80184D90.",
        *excerpt(clear_lines, ("D_80193BE0", "0x15E0", "func_80184D90"), 2),
        "",
        "Evidence B: character-state initializer writes into the roster",
        "---------------------------------------------------------------",
        f"func_80184D90 @ {init_path}:{init_start}",
        "This initializer directly targets D_80193BE0 after preparing initial",
        "character data, corroborating that the array is persistent character state.",
        *excerpt(init_lines, ("D_80193BE0",), 5),
        "",
        "Evidence C: exactly 100 x 0x38 records are scanned as characters",
        "---------------------------------------------------------------",
        f"func_8016B774 @ {scan_path}:{scan_start}",
        "The scan advances by 0x38, terminates at 0x64 records, checks +0x11 and",
        "feeds +0x12 into class-driven dispatch/resource logic.",
        *excerpt(scan_lines, ("D_80193BE0", "0x38", "0x64", "0x11", "0x12"), 2),
        "",
        "Safe conclusion",
        "---------------",
        "D_80193BE0 is a persistent 100-slot character roster, and a live battle",
        "participant whose +0xF6 value indexes this array can be called roster-backed.",
        "This is substantially stronger than an arbitrary nearby byte correlation.",
        "",
        "NOT yet proven",
        "--------------",
        "The tracked resident assembly does not prove that every roster-backed battle",
        "participant is allied, nor that every enemy uses an out-of-range/0xFF +0xF6.",
        "The decisive participant<->record sync code is in generated streamed bank J.",
        "Therefore roster-backed != allied remains a hypothesis until bank-J control",
        "flow or reproduced runtime evidence proves the ownership semantic.",
        "DanikaSide must remain UNKNOWN on roster backing alone.",
    ]
    text = "\n".join(report) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
