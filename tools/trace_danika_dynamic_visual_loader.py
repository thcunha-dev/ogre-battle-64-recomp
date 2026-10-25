#!/usr/bin/env python3
"""Trace the dynamic battle visual loader path for playable Knight of Danika.

This probe intentionally separates two callers of func_801AD13C:

* func_801AE794: static/group-driven battle-scene object construction.
* func_801AD368: direct/dynamic visual descriptor initialization candidate.

The static resource 0x315736 route is useful renderer evidence, but ROM analysis
shows its record+0x02 low byte does not directly enumerate class IDs 0x14/0x71/0x9C.
Therefore it must not be treated as the unit-class donor table without additional
provenance.
"""

from pathlib import Path
import re

ASM = Path("asm/1CE040.s")
OUT = Path("danika-dynamic-visual-loader.txt")
TARGETS = ("func_801AD13C", "func_801AD368", "func_801AE794")


def load_lines():
    return ASM.read_text(encoding="utf-8", errors="replace").splitlines()


def function_bounds(lines):
    bounds = {}
    starts = {}
    for i, line in enumerate(lines):
        m = re.match(r"\s*glabel\s+(\w+)", line)
        if m:
            starts[m.group(1)] = i
        m = re.match(r"\s*endlabel\s+(\w+)", line)
        if m and m.group(1) in starts:
            bounds[m.group(1)] = (starts[m.group(1)], i)
    return bounds


def calls_in(body):
    result = []
    for idx, line in body:
        m = re.search(r"\bjal\s+(func_[0-9A-Fa-f]+)", line)
        if m:
            result.append((idx, m.group(1), line))
    return result


def refs(body, needles):
    out = []
    for idx, line in body:
        if any(n in line for n in needles):
            out.append((idx, line))
    return out


def body_for(lines, bounds, name):
    if name not in bounds:
        return []
    a, b = bounds[name]
    return list(enumerate(lines[a:b + 1], start=a + 1))


def caller_sites(lines, bounds, callee):
    out = []
    needle = f"jal        {callee}"
    for name, (a, b) in bounds.items():
        for i in range(a, b + 1):
            if needle in lines[i] or re.search(rf"\bjal\s+{re.escape(callee)}\b", lines[i]):
                out.append((name, i + 1))
    return out


def emit_context(lines, line_no, radius=18):
    a = max(1, line_no - radius)
    b = min(len(lines), line_no + radius)
    return [f"{i:6d}: {lines[i - 1]}" for i in range(a, b + 1)]


def main():
    lines = load_lines()
    bounds = function_bounds(lines)
    report = []
    report += [
        "Knight of Danika dynamic visual loader trace",
        "============================================",
        "",
        "Safety premise",
        "--------------",
        "func_801AE794 is group/static-record driven and must not be assumed to be",
        "the combatant class->sprite mapping merely because it reaches func_801AD13C.",
        "The dynamic caller func_801AD368 is the next primary target.",
        "",
    ]

    for target in TARGETS:
        body = body_for(lines, bounds, target)
        report.append(f"## {target}")
        if not body:
            report += ["NOT FOUND", ""]
            continue
        report.append(f"lines={body[0][0]}-{body[-1][0]}")
        report.append("calls=" + ",".join(c for _, c, _ in calls_in(body)))
        interesting = refs(body, (
            "func_801AD13C", "D_80187C", "0x48", "0x71", "0x14", "0x9C",
            "0x3B6CD0", "0x315736", "D_801BA688", "D_801BA690",
            "D_801BA694", "0x4C", "0x50", "0x4F", "0x34",
        ))
        report.append(f"interesting_refs={len(interesting)}")
        for idx, line in interesting:
            report.append(f"{idx:6d}: {line}")
        report.append("")
        report.append("Full body")
        report.append("---------")
        for idx, line in body:
            report.append(f"{idx:6d}: {line}")
        report.append("")

    report += ["Caller sites", "------------"]
    for callee in ("func_801AD13C", "func_801AD368"):
        sites = caller_sites(lines, bounds, callee)
        report.append(f"{callee}: {len(sites)}")
        for name, line_no in sites:
            report.append(f"  {name} @ {line_no}")
            report.extend("    " + x for x in emit_context(lines, line_no, 14))
        report.append("")

    report += [
        "Interpretation guardrail",
        "------------------------",
        "A Danika donor patch is allowed only after a dynamic path is tied to a live",
        "combatant class ID and an independently proven player/allied ownership source.",
        "Static scene-object selectors are not sufficient evidence.",
    ]

    text = "\n".join(report) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
