#!/usr/bin/env python3
"""Trace registration and source dataflow for the Danika battle renderer callback.

Known chain:
  func_801AE794 builds a temporary selection/result structure at sp+0x48 and
  passes it to func_801B3C78.  The word at structure+0x08 (sp+0x50) is later
  copied to object+0xB4, while bit0 also selects object+0x14 value 3 vs 2.
  func_801B3868 maps those object fields into func_801AD6C4 renderer flags.

This probe captures the callback construction and the producer function so the
meaning of that shared flag word can be established from writes, not guessed.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM_ROOT = ROOT / "asm"
TARGET = "func_801B3868"
TARGET_ADDR = "801B3868"
REGISTRATION = "func_801AE794"
PRODUCER = "func_801B3C78"
OUT = ROOT / "danika-render-callback-trace.txt"

FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
MEM14_RE = re.compile(r"\b(?:lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$[A-Za-z0-9]+,\s*0x14\(\$([A-Za-z0-9]+)\)", re.I)
MEMB4_RE = re.compile(r"\b(?:lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$[A-Za-z0-9]+,\s*0xB4\(\$([A-Za-z0-9]+)\)", re.I)
STACK_RESULT_RE = re.compile(r"\b(?:lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$[A-Za-z0-9]+,\s*0x(48|4C|50|54|58)\(\$sp\)", re.I)
STACK_RESULT_ADDR_RE = re.compile(r"\baddiu\s+\$([A-Za-z0-9]+),\s*\$sp,\s*0x(48|4C|50|54|58)\b", re.I)
OBJ14_STORE_RE = re.compile(r"\bsb\s+\$[A-Za-z0-9]+,\s*0x14\(\$([A-Za-z0-9]+)\)", re.I)
OBJB4_STORE_RE = re.compile(r"\bsw\s+\$[A-Za-z0-9]+,\s*0xB4\(\$([A-Za-z0-9]+)\)", re.I)
CALL_PRODUCER_RE = re.compile(r"\bjal\s+" + re.escape(PRODUCER) + r"\b")
STORE_RE = re.compile(r"\b(sb|sh|sw)\s+\$([A-Za-z0-9]+),\s*(?:0x)?([0-9A-Fa-f]+)\(\$([A-Za-z0-9]+)\)", re.I)
LOAD_RE = re.compile(r"\b(lb|lbu|lh|lhu|lw)\s+\$([A-Za-z0-9]+),\s*(?:0x)?([0-9A-Fa-f]+)\(\$([A-Za-z0-9]+)\)", re.I)


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
        e = min(len(lines) - 1, i + 3500)
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
    producer_blocks = []

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
            has14 = [(n, x.strip()) for n, x in nlines if (m := MEM14_RE.search(x)) and m.group(1).lower() != "sp"]
            hasb4 = [(n, x.strip()) for n, x in nlines if (m := MEMB4_RE.search(x)) and m.group(1).lower() != "sp"]
            if has14 or hasb4:
                score = (10 if has14 and hasb4 else 0) + len(has14) + len(hasb4)
                flag_funcs.append((score, rel, name, s, e, has14, hasb4, lines))

            target_hits = [(n, x) for n, x in nlines if TARGET in x]
            if target_hits and name != TARGET:
                stack_result = [(n, x.strip()) for n, x in nlines if STACK_RESULT_RE.search(x) or STACK_RESULT_ADDR_RE.search(x)]
                producer_calls = [(n, x.strip()) for n, x in nlines if CALL_PRODUCER_RE.search(x)]
                obj14stores = [(n, x.strip()) for n, x in nlines if OBJ14_STORE_RE.search(x) and "($sp)" not in x]
                objb4stores = [(n, x.strip()) for n, x in nlines if OBJB4_STORE_RE.search(x) and "($sp)" not in x]
                registrations.append((rel, name, s, e, target_hits, stack_result, producer_calls, obj14stores, objb4stores, lines))

            if name == PRODUCER:
                stores = []
                loads = []
                for n, x in nlines:
                    m = STORE_RE.search(x)
                    if m:
                        stores.append((n, m.group(1).lower(), m.group(2).lower(), int(m.group(3), 16), m.group(4).lower(), x.strip()))
                    m = LOAD_RE.search(x)
                    if m:
                        loads.append((n, m.group(1).lower(), m.group(2).lower(), int(m.group(3), 16), m.group(4).lower(), x.strip()))
                producer_blocks.append((rel, name, s, e, stores, loads, lines))

    flag_funcs.sort(reverse=True, key=lambda x: x[0])

    out = [
        "Danika render callback / side-flag trace",
        "=======================================",
        f"target={TARGET}",
        f"registration={REGISTRATION}",
        f"result_producer={PRODUCER}",
        f"symbol_refs={len(refs)}",
        f"numeric_refs={len(numeric_refs)}",
        f"registration_functions={len(registrations)}",
        f"producer_functions={len(producer_blocks)}",
        "wrapper_contract: a1=(object+0x14 != 3), a2=(object+0xB4 & 0x2)",
        "",
        "Registration dataflow",
        "---------------------",
    ]

    for rel, name, s, e, hits, stack_result, producer_calls, st14, stb4, lines in registrations:
        out.append(f"### {name} {rel}:{s}-{e}")
        for n, x in hits:
            out.append(f"  callback {n}: {x.strip()}")
        for n, x in producer_calls:
            out.append(f"  result producer call {n}: {x}")
        for n, x in stack_result:
            out.append(f"  result-struct {n}: {x}")
        for n, x in st14:
            out.append(f"  object+14 store {n}: {x}")
        for n, x in stb4:
            out.append(f"  object+B4 store {n}: {x}")

        interesting = [n for n, _ in hits + producer_calls + stack_result + st14 + stb4]
        if interesting:
            lo = max(s, min(interesting) - 28)
            hi = min(e, max(interesting) + 24)
            out.append(f"  -- focused snapshot {lo}-{hi} --")
            for n, x in numbered(lines, s):
                if lo <= n <= hi:
                    out.append(f"  {n}: {x}")
        out.append("")

    out += [
        "Result producer",
        "---------------",
        "Caller passes a3=&result[0] at sp+0x48; result+0x08 is the shared flag word.",
        "The dump below is intentionally complete so register aliases to a3 can be followed.",
    ]
    for rel, name, s, e, stores, loads, lines in producer_blocks:
        out.append(f"### {name} {rel}:{s}-{e} stores={len(stores)} loads={len(loads)}")
        out.append("  -- stores, useful for identifying writes through a3/aliases --")
        for n, op, src, off, base, x in stores:
            out.append(f"  STORE {n}: op={op} src=${src} off=0x{off:X} base=${base} :: {x}")
        out.append("  -- full producer snapshot --")
        for n, x in numbered(lines, s):
            out.append(f"  {n}: {x}")
        out.append("")

    out += [
        "Correlated contract",
        "-------------------",
        "func_801AE794 passes &sp[0x48] as a3 to func_801B3C78.",
        "result+0x08 (sp+0x50) is copied to object+0xB4 and bit0 selects object+0x14=3/2.",
        "Therefore renderer a1 and a2 are correlated views of one result word; the producer above",
        "is the authoritative place to determine the gameplay meaning of bits 0 and 1.",
        "Do not call either bit 'allied' until its producer/source field is semantically proven.",
        "",
        "Object functions touching +0x14 / +0xB4",
        "---------------------------------------",
    ]
    for score, rel, name, s, e, h14, hb4, lines in flag_funcs[:40]:
        out.append(f"### score={score} {name} {rel}:{s}-{e} +14={len(h14)} +B4={len(hb4)}")
        for n, line in h14:
            out.append(f"  +14 {n}: {line}")
        for n, line in hb4:
            out.append(f"  +B4 {n}: {line}")
        out.append("")

    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")

    assert registrations, "expected callback registration"
    assert producer_blocks, f"expected producer {PRODUCER}"
    assert any(r[6] for r in registrations), f"expected call to {PRODUCER} in callback registration function"
    assert any(r[5] and r[7] and r[8] for r in registrations), "registration must expose result structure and both object stores"
    print(f"Danika render callback trace: PASS (registrations={len(registrations)}, producers={len(producer_blocks)})")
    print(f"report={OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
