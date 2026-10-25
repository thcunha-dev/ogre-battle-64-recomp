#!/usr/bin/env python3
"""Trace the unique caller of the proven battle renderer.

func_801AD6C4 is a real display-list renderer and has one known incoming caller,
func_801B3868.  This probe snapshots func_801B3868, its incoming callers, its
outgoing call graph, global references, and the exact callsite into the renderer.
It also highlights pointer-field accesses that can reveal where the battle
visual descriptor is prepared before rendering.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM_ROOT = ROOT / "asm"
TARGET = "func_801B3868"
RENDERER = "func_801AD6C4"
OUT = ROOT / "danika-renderer-caller-trace.txt"

FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
GLOBAL_RE = re.compile(r"\b(D_[0-9A-Fa-f]{8}|D_[A-Za-z0-9_]+)\b")
MEM_RE = re.compile(r"\b(lb|lbu|lh|lhu|lw|sb|sh|sw|lwc1|swc1)\s+\$([A-Za-z0-9]+),\s*(-?0x[0-9A-Fa-f]+|-?\d+)\(\$([A-Za-z0-9]+)\)")
REG_MOVE_RE = re.compile(r"\b(addu|or)\s+\$([A-Za-z0-9]+),\s*\$([A-Za-z0-9]+),\s*\$zero\b")
ADDIU_RE = re.compile(r"\baddiu\s+\$([A-Za-z0-9]+),\s*\$([A-Za-z0-9]+),\s*(-?0x[0-9A-Fa-f]+|-?\d+)")


def blocks(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        m = FUNC_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        start = i
        end = min(len(lines) - 1, i + 3000)
        for j in range(i + 1, end + 1):
            em = END_RE.match(lines[j])
            if em and em.group(1) == name:
                end = j
                break
            if j > i + 1 and FUNC_RE.match(lines[j]):
                end = j - 1
                break
        yield name, start + 1, end + 1, lines[start : end + 1]
        i = end + 1


def all_blocks():
    for path in sorted(ASM_ROOT.rglob("*.s")):
        rel = path.relative_to(ROOT).as_posix()
        for name, s, e, lines in blocks(path):
            yield rel, name, s, e, lines


def parse_imm(s: str) -> int:
    return int(s, 0)


def main() -> int:
    corpus = list(all_blocks())
    target = None
    incoming = []
    renderer_incoming = []
    for rel, name, s, e, lines in corpus:
        text = "\n".join(lines)
        if name == TARGET:
            target = (rel, name, s, e, lines)
        calls = CALL_RE.findall(text)
        if TARGET in calls:
            incoming.append((rel, name, s, e, calls.count(TARGET)))
        if RENDERER in calls:
            renderer_incoming.append((rel, name, s, e, calls.count(RENDERER)))

    if target is None:
        raise SystemExit(f"{TARGET} not found")

    rel, _name, s, e, lines = target
    text = "\n".join(lines)
    calls = CALL_RE.findall(text)
    globals_used = sorted(set(GLOBAL_RE.findall(text)))

    memops = []
    for idx, line in enumerate(lines, start=s):
        m = MEM_RE.search(line)
        if not m:
            continue
        op, reg, off_s, base = m.groups()
        try:
            off = parse_imm(off_s)
        except ValueError:
            continue
        memops.append((idx, op, reg, off, base, line.strip()))

    # We care especially about pointer-like structure fields around the known
    # renderer descriptor path and common object offsets.
    hot_offsets = {0x20,0x24,0x28,0x2C,0x30,0x34,0x38,0x3C,0x40,0x44,0x48,0x4B,0x4C,0x4F,0x50,0x54,0x58,0x5C}
    hot_mem = [m for m in memops if m[3] in hot_offsets]

    renderer_callsites = []
    for i, line in enumerate(lines):
        if re.search(rf"\bjal\s+{re.escape(RENDERER)}\b", line):
            lo = max(0, i - 24)
            hi = min(len(lines), i + 18)
            renderer_callsites.append((s + i, list(enumerate(lines[lo:hi], start=s + lo))))

    out = []
    out += [
        "Danika unique renderer-caller trace",
        "===================================",
        f"target={TARGET}",
        f"renderer={RENDERER}",
        f"definition={rel}:{s}-{e}",
        f"target_lines={len(lines)}",
        f"incoming_callers={len(incoming)}",
        f"renderer_incoming_functions={len(renderer_incoming)}",
        f"outgoing_calls={len(calls)} unique={len(set(calls))}",
        f"global_refs={len(globals_used)}",
        "",
        "Incoming callers to target",
        "--------------------------",
    ]
    for item in incoming:
        out.append(f"{item[0]}:{item[2]} {item[1]} calls={item[4]}")

    out += ["", "All renderer incoming functions", "-------------------------------"]
    for item in renderer_incoming:
        out.append(f"{item[0]}:{item[2]} {item[1]} calls={item[4]}")

    out += ["", "Outgoing call targets", "---------------------"]
    for c in sorted(set(calls)):
        out.append(f"{c}: count={calls.count(c)}")

    out += ["", "Global references", "-----------------"]
    out.extend(globals_used or ["(none)"])

    out += ["", "Hot structure-field memory accesses", "-----------------------------------"]
    for idx, op, reg, off, base, line in hot_mem:
        out.append(f"{idx}: {op} ${reg}, +0x{off:X}(${base}) :: {line}")

    out += ["", "Renderer callsite context", "-------------------------"]
    for addrline, ctx in renderer_callsites:
        out.append(f"### renderer jal at source line {addrline}")
        for lineno, line in ctx:
            mark = ">>>" if lineno == addrline else "   "
            out.append(f"{mark} {lineno}: {line}")
        out.append("")

    out += ["", "Full target function snapshot", "-----------------------------"]
    for idx, line in enumerate(lines, start=s):
        out.append(f"{idx}: {line}")

    out += [
        "",
        "Interpretation guardrail",
        "------------------------",
        "The renderer callsite is a patch candidate only after descriptor/resource data flow is proven.",
        "Do not substitute class 0x14 globally. The final override must be class 0x71 + allied-side specific.",
    ]

    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")

    assert renderer_callsites, f"{TARGET} must call {RENDERER}"
    assert len(renderer_incoming) == 1, "renderer is expected to have a unique incoming function"
    assert renderer_incoming[0][1] == TARGET
    print(f"Danika renderer caller trace: PASS ({TARGET}, {len(lines)} lines, {len(calls)} calls)")
    print(f"report={OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
