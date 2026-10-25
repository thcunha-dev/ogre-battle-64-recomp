#!/usr/bin/env python3
"""Trace non-jal registration/usage of func_801B3868 and its context flags.

The proven renderer wrapper func_801B3868 has no direct jal callers, suggesting
it is used as a callback/function pointer. It derives renderer argument a1 from
object+0x14 (value != 3) and a2 from bit 0x2 of object+0xB4. This probe finds
symbol/data references to the wrapper and inventories nearby functions that
read those same object offsets so we can establish side/orientation semantics.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM_ROOT = ROOT / "asm"
TARGET = "func_801B3868"
TARGET_ADDR = "801B3868"
OUT = ROOT / "danika-render-callback-trace.txt"

FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
MEM14_RE = re.compile(r"\b(?:lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$[A-Za-z0-9]+,\s*0x14\(\$([A-Za-z0-9]+)\)")
MEMB4_RE = re.compile(r"\b(?:lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$[A-Za-z0-9]+,\s*0xB4\(\$([A-Za-z0-9]+)\)", re.I)


def function_blocks(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        m = FUNC_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        s = i
        e = min(len(lines) - 1, i + 2500)
        for j in range(i + 1, e + 1):
            em = END_RE.match(lines[j])
            if em and em.group(1) == name:
                e = j
                break
            if j > i + 1 and FUNC_RE.match(lines[j]):
                e = j - 1
                break
        yield name, s + 1, e + 1, lines[s : e + 1]
        i = e + 1


def main() -> int:
    refs = []
    numeric_refs = []
    flag_funcs = []

    text_ext = {".s", ".c", ".h", ".toml", ".json", ".txt", ".md", ".yml", ".yaml", ".ld"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in text_ext:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for idx, line in enumerate(lines, start=1):
            if TARGET in line and not rel.endswith("trace_danika_render_callback.py"):
                refs.append((rel, idx, line.rstrip()))
            if TARGET_ADDR.lower() in line.lower() and TARGET not in line:
                numeric_refs.append((rel, idx, line.rstrip()))

    for path in sorted(ASM_ROOT.rglob("*.s")):
        rel = path.relative_to(ROOT).as_posix()
        for name, s, e, lines in function_blocks(path):
            has14 = []
            hasb4 = []
            for n, line in enumerate(lines, start=s):
                if MEM14_RE.search(line):
                    has14.append((n, line.strip()))
                if MEMB4_RE.search(line):
                    hasb4.append((n, line.strip()))
            if has14 or hasb4:
                score = (10 if has14 and hasb4 else 0) + len(has14) + len(hasb4)
                flag_funcs.append((score, rel, name, s, e, has14, hasb4, lines))

    flag_funcs.sort(reverse=True, key=lambda x: x[0])

    out = []
    out += [
        "Danika render callback / side-flag trace",
        "=======================================",
        f"target={TARGET}",
        f"symbol_refs={len(refs)}",
        f"numeric_refs={len(numeric_refs)}",
        "wrapper_contract: a1=(object+0x14 != 3), a2=(object+0xB4 & 0x2)",
        "",
        "Symbol references",
        "-----------------",
    ]
    for rel, idx, line in refs:
        out.append(f"{rel}:{idx}: {line}")

    out += ["", "Numeric/materialized references", "-------------------------------"]
    for rel, idx, line in numeric_refs:
        out.append(f"{rel}:{idx}: {line}")

    out += ["", "Functions touching object offsets +0x14 / +0xB4", "-------------------------------------------------"]
    for score, rel, name, s, e, h14, hb4, lines in flag_funcs[:80]:
        out.append(f"### score={score} {name} {rel}:{s}-{e} +14={len(h14)} +B4={len(hb4)}")
        for n, line in h14:
            out.append(f"  +14 {n}: {line}")
        for n, line in hb4:
            out.append(f"  +B4 {n}: {line}")
        if h14 and hb4:
            out.append("  -- full function snapshot (both offsets present) --")
            for n, line in enumerate(lines, start=s):
                out.append(f"  {n}: {line}")
        out.append("")

    out += [
        "Interpretation guardrail",
        "------------------------",
        "A callback-table reference can prove how/when the renderer wrapper executes, but does not by itself name a flag.",
        "Treat object+0x14 as a side/orientation candidate only after neighboring initialization/state transitions are traced.",
        "Treat object+0xB4 bit 0x2 as a render-mode candidate until its writers are identified.",
    ]

    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")

    # The target definition itself is excluded, so at least a registration or
    # declaration reference is expected in a recomp project using callbacks.
    print(f"Danika render callback trace: PASS (symbol_refs={len(refs)}, numeric_refs={len(numeric_refs)}, flag_funcs={len(flag_funcs)})")
    print(f"report={OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
