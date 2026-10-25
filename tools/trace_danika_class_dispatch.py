#!/usr/bin/env python3
"""Resolve the class-pair dispatch around func_8016B774.

This probe follows the strongest current provenance signal: func_8016B774 reads
both character +0x11 and +0x12, then dispatches indirectly through D_80186FF4.
It resolves the table definition, maps any function pointers to labels, dumps
relevant dispatch targets, and classifies nearby helpers that previously looked
resource-like (80070F30, 80093060, 800712C4).

No patch is emitted; the purpose is to decide whether this route is combatant
presentation, gameplay/stat logic, or another false positive.
"""
from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ASM = ROOT / "asm"
OUT = ROOT / "danika-class-dispatch.txt"
TARGET_FUNCS = (
    "func_8016B774", "func_8016BA6C", "func_8016CEC4",
    "func_80070F30", "func_80093060", "func_800712C4",
)
TABLE = "D_80186FF4"

FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
ADDR_COMMENT_RE = re.compile(r"/\*\s*[0-9A-Fa-f]+\s+([0-9A-Fa-f]{8})\s*\*/")
WORD_RE = re.compile(r"\.word\s+(.+)$")
SYM_RE = re.compile(r"\b(func_[0-9A-Fa-f]+|D_80[0-9A-Fa-f]{6})\b")
HEX_RE = re.compile(r"0x([0-9A-Fa-f]+)")


def all_asm_files():
    return sorted(ASM.rglob("*.s"))


def parse_funcs():
    funcs = {}
    address_to_func = {}
    for path in all_asm_files():
        if "/data/" in path.as_posix():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        starts = {}
        start_addr = {}
        for i, line in enumerate(lines):
            m = FUNC_RE.match(line)
            if m:
                name = m.group(1)
                starts[name] = i
                # glabel itself may not carry address; inspect next instruction.
                for j in range(i + 1, min(i + 5, len(lines))):
                    am = ADDR_COMMENT_RE.search(lines[j])
                    if am:
                        start_addr[name] = int(am.group(1), 16)
                        break
            e = END_RE.match(line)
            if e and e.group(1) in starts:
                name = e.group(1)
                a = starts[name]
                funcs[name] = (path.relative_to(ROOT), a + 1, i + 1, lines[a:i+1])
                if name in start_addr:
                    address_to_func[start_addr[name]] = name
    return funcs, address_to_func


def calls(body):
    return [m.group(1) for line in body if (m := CALL_RE.search(line))]


def callers(funcs, target):
    pat = re.compile(rf"\bjal\s+{re.escape(target)}\b")
    out = []
    for name, (path, start, end, body) in funcs.items():
        for off, line in enumerate(body):
            if pat.search(line):
                out.append((name, path, start + off))
    return out


def find_table_definition():
    hits = []
    for path in all_asm_files():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            if re.search(rf"\bglabel\s+{re.escape(TABLE)}\b", line):
                block = []
                # capture until next label or 128 lines max
                for j in range(i, min(i + 128, len(lines))):
                    if j > i and re.match(r"^\s*glabel\s+", lines[j]):
                        break
                    block.append((j + 1, lines[j]))
                hits.append((path.relative_to(ROOT), block))
    return hits


def resolve_table_entries(block, address_to_func):
    entries = []
    for ln, line in block:
        wm = WORD_RE.search(line)
        if not wm:
            continue
        rhs = wm.group(1)
        syms = SYM_RE.findall(rhs)
        if syms:
            for s in syms:
                entries.append((ln, s, None, s if s.startswith("func_") else None))
            continue
        for hx in HEX_RE.findall(rhs):
            val = int(hx, 16)
            entries.append((ln, f"0x{val:08X}", val, address_to_func.get(val)))
    return entries


def dump_func(report, funcs, name):
    report.append(f"## {name}")
    if name not in funcs:
        report += ["NOT FOUND", ""]
        return
    path, start, end, body = funcs[name]
    report.append(f"location={path}:{start}-{end}")
    report.append("callees=" + (",".join(calls(body)) or "-"))
    report.append("callers=" + (",".join(f"{n}@{p}:{ln}" for n,p,ln in callers(funcs,name)) or "-"))
    report.append("full_body:")
    for i, line in enumerate(body, start=start):
        report.append(f"{i:6d}: {line}")
    report.append("")


def main():
    funcs, addrmap = parse_funcs()
    report = [
        "Knight of Danika class-pair dispatch trace",
        "==========================================",
        "",
        "Question",
        "--------",
        "Does func_8016B774's +0x11/+0x12 dispatch through D_80186FF4 lead",
        "to fighter visual/animation setup, or to unrelated gameplay logic?",
        "",
    ]

    for name in TARGET_FUNCS:
        dump_func(report, funcs, name)

    report += ["D_80186FF4 definition", "--------------------"]
    defs = find_table_definition()
    if not defs:
        report.append("NOT FOUND")
    dispatch_targets = []
    for path, block in defs:
        report.append(f"file={path}")
        for ln, line in block:
            report.append(f"{ln:6d}: {line}")
        entries = resolve_table_entries(block, addrmap)
        report.append(f"resolved_entries={len(entries)}")
        for idx, (ln, raw, addr, target) in enumerate(entries):
            report.append(f"entry[{idx:02d}] line={ln} raw={raw} target={target or '-'}")
            if target and target in funcs:
                dispatch_targets.append(target)
        report.append("")

    report += ["Resolved dispatch target bodies", "-------------------------------"]
    for name in sorted(set(dispatch_targets)):
        dump_func(report, funcs, name)

    # Search every textual reference to the table, useful if table definition is
    # emitted via raw words and callers reveal stride/index semantics instead.
    report += ["All D_80186FF4 references", "-------------------------"]
    refs = 0
    for path in all_asm_files():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            if TABLE in line:
                refs += 1
                a = max(0, i - 15); b = min(len(lines), i + 25)
                report.append(f"### {path.relative_to(ROOT)}:{i+1}")
                for j in range(a, b):
                    report.append(f"{j+1:6d}: {lines[j]}")
    report.append(f"reference_sites={refs}")
    report.append("")

    report += [
        "Classification guardrails",
        "-------------------------",
        "* A +0x11/+0x12 read is strong character provenance only when surrounding",
        "  operations agree with known character layout.",
        "* An indirect table is not visual merely because it is class-indexed.",
        "* 80093380 is already proven memset and is excluded as a graphics signal.",
        "* A future runtime override still requires independent allied-side proof.",
    ]

    text = "\n".join(report) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
