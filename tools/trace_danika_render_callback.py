#!/usr/bin/env python3
"""Trace registration/dataflow for the Danika battle renderer callback.

Known contract:
  func_801B3868(object)
    a1 = (object+0x14 != 3)
    a2 = (object+0xB4 & 0x2)
    -> func_801AD6C4

This probe deliberately separates object-relative accesses from stack traffic,
locates the function that materializes func_801B3868 as a callback, and traces
the source flag used to initialize object+0x14 and object+0xB4.  It reports a
side/orientation candidate only; semantic names are not assigned without a
producer/consumer proof.
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
MEM14_RE = re.compile(r"\b(?:lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$[A-Za-z0-9]+,\s*0x14\(\$([A-Za-z0-9]+)\)", re.I)
MEMB4_RE = re.compile(r"\b(?:lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$[A-Za-z0-9]+,\s*0xB4\(\$([A-Za-z0-9]+)\)", re.I)
STACK50_RE = re.compile(r"\b(?:lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$[A-Za-z0-9]+,\s*0x50\(\$sp\)", re.I)
OBJ14_STORE_RE = re.compile(r"\bsb\s+\$[A-Za-z0-9]+,\s*0x14\(\$([A-Za-z0-9]+)\)", re.I)
OBJB4_STORE_RE = re.compile(r"\bsw\s+\$[A-Za-z0-9]+,\s*0xB4\(\$([A-Za-z0-9]+)\)", re.I)


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
        e = min(len(lines) - 1, i + 3000)
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


def numbered(lines, start):
    return [(start + i, line) for i, line in enumerate(lines)]


def main() -> int:
    refs = []
    numeric_refs = []
    flag_funcs = []
    registrations = []

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
            nlines = numbered(lines, s)
            # Do not count stack-frame saves/restores as object fields.
            has14 = [(n, x.strip()) for n, x in nlines if (m := MEM14_RE.search(x)) and m.group(1).lower() != "sp"]
            hasb4 = [(n, x.strip()) for n, x in nlines if (m := MEMB4_RE.search(x)) and m.group(1).lower() != "sp"]
            if has14 or hasb4:
                score = (10 if has14 and hasb4 else 0) + len(has14) + len(hasb4)
                flag_funcs.append((score, rel, name, s, e, has14, hasb4, lines))

            # A real registration block materializes the callback symbol; capture
            # all stack+0x50 traffic and the object-field initialization around it.
            target_hits = [(n, x) for n, x in nlines if TARGET in x]
            if target_hits and name != TARGET:
                stack50 = [(n, x.strip()) for n, x in nlines if STACK50_RE.search(x)]
                obj14stores = [(n, x.strip()) for n, x in nlines if OBJ14_STORE_RE.search(x) and "($sp)" not in x]
                objb4stores = [(n, x.strip()) for n, x in nlines if OBJB4_STORE_RE.search(x) and "($sp)" not in x]
                registrations.append((rel, name, s, e, target_hits, stack50, obj14stores, objb4stores, lines))

    flag_funcs.sort(reverse=True, key=lambda x: x[0])

    out = [
        "Danika render callback / side-flag trace",
        "=======================================",
        f"target={TARGET}",
        f"symbol_refs={len(refs)}",
        f"numeric_refs={len(numeric_refs)}",
        f"registration_functions={len(registrations)}",
        "wrapper_contract: a1=(object+0x14 != 3), a2=(object+0xB4 & 0x2)",
        "",
        "Registration dataflow",
        "---------------------",
    ]

    for rel, name, s, e, hits, stack50, st14, stb4, lines in registrations:
        out.append(f"### {name} {rel}:{s}-{e}")
        for n, x in hits:
            out.append(f"  callback {n}: {x.strip()}")
        for n, x in stack50:
            out.append(f"  stack+50 {n}: {x}")
        for n, x in st14:
            out.append(f"  object+14 store {n}: {x}")
        for n, x in stb4:
            out.append(f"  object+B4 store {n}: {x}")

        interesting = [n for n, _ in hits + stack50 + st14 + stb4]
        if interesting:
            lo = max(s, min(interesting) - 36)
            hi = min(e, max(interesting) + 24)
            out.append(f"  -- focused snapshot {lo}-{hi} --")
            for n, x in numbered(lines, s):
                if lo <= n <= hi:
                    out.append(f"  {n}: {x}")
        out.append("")

    out += [
        "Correlated contract",
        "-------------------",
        "At callback construction, verify whether the same source word is copied to object+0xB4",
        "and whether its bit0 selects object+0x14 value 3 versus 2.  If both hold, the two",
        "renderer arguments are correlated views of one source flag word rather than independent side flags.",
        "Do not call either bit 'allied' until the source word producer is identified.",
        "",
        "Symbol references",
        "-----------------",
    ]
    for rel, idx, line in refs:
        out.append(f"{rel}:{idx}: {line}")

    out += ["", "Numeric/materialized references", "-------------------------------"]
    for rel, idx, line in numeric_refs:
        out.append(f"{rel}:{idx}: {line}")

    out += ["", "Object functions touching +0x14 / +0xB4", "---------------------------------------"]
    for score, rel, name, s, e, h14, hb4, lines in flag_funcs[:80]:
        out.append(f"### score={score} {name} {rel}:{s}-{e} +14={len(h14)} +B4={len(hb4)}")
        for n, line in h14:
            out.append(f"  +14 {n}: {line}")
        for n, line in hb4:
            out.append(f"  +B4 {n}: {line}")
        if h14 and hb4:
            out.append("  -- full function snapshot (both object offsets present) --")
            for n, line in numbered(lines, s):
                out.append(f"  {n}: {line}")
        out.append("")

    out += [
        "Interpretation guardrail",
        "------------------------",
        "Callback registration proves construction dataflow, not gameplay semantics.",
        "object+0x14 is a render-state candidate until its source flag is named.",
        "object+0xB4 bit 0x2 is a render-mode candidate until its producer/consumers establish meaning.",
    ]

    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")

    assert registrations, "expected at least one callback registration function"
    assert any(r[5] and r[6] and r[7] for r in registrations), "registration must expose source flag and both object stores"
    print(f"Danika render callback trace: PASS (registrations={len(registrations)}, object_flag_funcs={len(flag_funcs)})")
    print(f"report={OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
