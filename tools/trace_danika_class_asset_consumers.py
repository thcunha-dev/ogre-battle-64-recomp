#!/usr/bin/env python3
"""Trace class-driven paths toward the real combatant asset loader.

The previous 0x315736 / func_801AD6C4 path has been proven to build static
battle-scene objects, not normal combatant class sprites.  This probe pivots
from verified class-table consumers and expands their local call graph instead
of assuming a renderer is a fighter renderer.
"""
from pathlib import Path
import re

ASM_FILES = [Path("asm/40E80.s"), Path("asm/1CE040.s"), Path("asm/1060.s")]
OUT = Path("danika-class-asset-consumers.txt")
TARGETS = ("func_8016E52C", "func_8016EBC4", "func_8016F13C")
CLASS_SYMS = (
    "D_80187C34", "D_80187C38", "D_80187C62", "D_80187C64",
    "D_80187C66", "D_80187C68", "D_80187C79",
)
LOADER_CALLEES = {
    "func_8009DAF4", "func_8009DBB8", "func_8009DD38", "func_80070F30",
    "func_800712C4", "func_80093060", "func_80093380",
}


def parse_functions():
    funcs = {}
    for path in ASM_FILES:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        starts = {}
        for i, line in enumerate(lines):
            m = re.match(r"\s*glabel\s+(\w+)", line)
            if m:
                starts[m.group(1)] = i
            m = re.match(r"\s*endlabel\s+(\w+)", line)
            if m and m.group(1) in starts:
                a = starts[m.group(1)]
                body = lines[a:i+1]
                funcs[m.group(1)] = (path, a+1, i+1, body)
    return funcs


def calls(body):
    out = []
    for line in body:
        m = re.search(r"\bjal\s+(\w+)", line)
        if m:
            out.append(m.group(1))
    return out


def callers_of(funcs, target):
    out = []
    for name, (path, start, end, body) in funcs.items():
        for off, line in enumerate(body):
            if re.search(rf"\bjal\s+{re.escape(target)}\b", line):
                out.append((name, path, start+off))
    return out


def dump_function(report, funcs, name, full=True):
    if name not in funcs:
        report += [f"## {name}: NOT FOUND", ""]
        return
    path, start, end, body = funcs[name]
    cs = calls(body)
    class_refs = sorted({s for s in CLASS_SYMS if any(s in x for x in body)})
    loader_calls = [c for c in cs if c in LOADER_CALLEES or "9DAF4" in c or "9DBB8" in c or "9DD38" in c]
    report += [
        f"## {name}",
        f"location={path}:{start}-{end}",
        f"class_refs={','.join(class_refs) if class_refs else '-'}",
        f"calls={','.join(cs) if cs else '-'}",
        f"loader_like_calls={','.join(loader_calls) if loader_calls else '-'}",
        "callers=" + ",".join(f"{n}@{p}:{ln}" for n,p,ln in callers_of(funcs, name)),
    ]
    if full:
        report.append("Full body")
        for i, line in enumerate(body, start=start):
            report.append(f"{i:6d}: {line}")
    report.append("")


def main():
    funcs = parse_functions()
    report = [
        "Knight of Danika class-driven asset consumer trace",
        "==================================================",
        "",
        "Locked correction",
        "-----------------",
        "The func_801AD6C4 / resource 0x315736 route is a static scene-object path.",
        "It must not be used as the playable-Danika fighter sprite override.",
        "This report starts from verified class-table consumers instead.",
        "",
    ]

    for t in TARGETS:
        dump_function(report, funcs, t, True)

    report += ["Direct class-table consumers", "----------------------------"]
    consumers = []
    for name, (path, start, end, body) in funcs.items():
        refs = [s for s in CLASS_SYMS if any(s in x for x in body)]
        if refs:
            cs = calls(body)
            consumers.append((name, path, start, end, refs, cs))
    report.append(f"count={len(consumers)}")
    for name, path, start, end, refs, cs in consumers:
        report.append(
            f"{name} {path}:{start}-{end} refs={','.join(refs)} "
            f"calls={','.join(cs) if cs else '-'}"
        )

    report += ["", "Two-hop caller expansion", "------------------------"]
    frontier = set(TARGETS)
    seen = set(frontier)
    for depth in (1, 2):
        nxt = set()
        report.append(f"depth={depth}")
        for target in sorted(frontier):
            for caller, path, line in callers_of(funcs, target):
                report.append(f"  {target} <- {caller} @ {path}:{line}")
                if caller not in seen:
                    nxt.add(caller)
                    seen.add(caller)
        frontier = nxt

    report += ["", "Loader adjacency candidates", "---------------------------"]
    for name in sorted(seen):
        if name not in funcs:
            continue
        path, start, end, body = funcs[name]
        cs = calls(body)
        loader = [c for c in cs if c in LOADER_CALLEES]
        if loader:
            report.append(f"{name} {path}:{start}-{end} -> {','.join(loader)}")

    text = "\n".join(report) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
