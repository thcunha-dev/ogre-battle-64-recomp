#!/usr/bin/env python3
"""Trace the Knight of Danika class->asset bridge without applying a patch.

This tool narrows the reverse-engineering target around func_8017FC48. It prints
its head/tail, the common terminal block reached by ROM-like 0x01DE.... resource
selections, all predecessors that feed that block, repository-wide uses of those
constants, and compact definitions/callers for the functions used near the end.

The output is evidence only. A 0x01DE.... value is deliberately called a
"resource-like constant" until its consumer proves the concrete asset format.
"""

from __future__ import annotations

import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
FOCUS_PATH = ROOT / "asm/40E80.s"
FOCUS = "func_8017FC48"
COMMON_LABEL = ".L80180564"
RESOURCE_RE = re.compile(r"0x1DE[0-9A-Fa-f]{3,5}")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
LABEL_RE = re.compile(r"^\s*([.$A-Za-z_][A-Za-z0-9_.$]*):\s*$")
FUNC_RE = re.compile(r"^\s*(?:glabel|nonmatching)\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")

# Functions immediately around the resource-selection tail.  We do not assume
# semantics from names; definitions/callers are emitted so the data flow can be
# proven from assembly.
TAIL_TARGETS = {
    "func_80093460",
    "func_8009C550",
    "func_8016DC4C",
    "func_8016DEE4",
    "func_8016E250",
    "func_8016E490",
    "func_8016E52C",
    "func_8016F500",
    "func_8016F520",
    "func_8016F5D0",
    "func_8016F5E8",
    "func_8017FB18",
}


def all_asm() -> list[Path]:
    return sorted((ROOT / "asm").rglob("*.s"))


def get_function(lines: list[str], name: str) -> tuple[int, int, list[str]]:
    start = None
    for i, line in enumerate(lines):
        m = FUNC_RE.match(line)
        if m and m.group(1) == name:
            start = i
            break
    if start is None:
        raise RuntimeError(f"function not found: {name}")
    end = None
    for i in range(start + 1, len(lines)):
        m = END_RE.match(lines[i])
        if m and m.group(1) == name:
            end = i
            break
    if end is None:
        # Some nonmatching blocks do not carry an endlabel in generated sources.
        for i in range(start + 1, len(lines)):
            m = FUNC_RE.match(lines[i])
            if m:
                end = i - 1
                break
    if end is None:
        end = len(lines) - 1
    return start, end, lines[start:end + 1]


def fmt_block(lines: list[str], start: int, end: int, marks: set[int] | None = None) -> list[str]:
    marks = marks or set()
    out = []
    start = max(0, start)
    end = min(len(lines) - 1, end)
    for i in range(start, end + 1):
        out.append(f"{'>>>' if i in marks else '   '} {i + 1:6d}: {lines[i]}")
    return out


def nearest_label(lines: list[str], idx: int, floor: int) -> tuple[int, str]:
    for i in range(idx, floor - 1, -1):
        m = LABEL_RE.match(lines[i])
        if m:
            return i, m.group(1)
    return floor, "<function-entry>"


def focus_report(lines: list[str]) -> tuple[list[str], set[str]]:
    start, end, body = get_function(lines, FOCUS)
    absolute_resource_lines: list[int] = []
    resources: set[str] = set()
    common_idx = None
    common_refs: list[int] = []
    tail_calls: list[tuple[int, str]] = []

    for i in range(start, end + 1):
        for value in RESOURCE_RE.findall(lines[i]):
            resources.add(value.upper())
            absolute_resource_lines.append(i)
        if re.search(rf"\b{re.escape(COMMON_LABEL)}\b", lines[i]):
            if LABEL_RE.match(lines[i]):
                common_idx = i
            else:
                common_refs.append(i)
        m = CALL_RE.search(lines[i])
        if m and m.group(1) in TAIL_TARGETS:
            tail_calls.append((i, m.group(1)))

    out = [
        "Danika asset bridge tracer",
        "==========================",
        f"focus={FOCUS}",
        f"source=asm/40E80.s:{start + 1}-{end + 1}",
        f"resource_like_constants={len(resources)} unique / {len(absolute_resource_lines)} materializations",
        f"common_terminal_label={COMMON_LABEL}",
        f"common_terminal_refs={len(common_refs)}",
        "",
        "Focus function head",
        "-------------------",
    ]
    out.extend(fmt_block(lines, start, min(end, start + 115)))
    out += ["", "Focus function tail", "-------------------"]
    out.extend(fmt_block(lines, max(start, end - 180), end, {i for i, _ in tail_calls}))

    out += ["", "Common terminal block", "---------------------"]
    if common_idx is None:
        out.append("NOT FOUND")
    else:
        out.extend(fmt_block(lines, max(start, common_idx - 28), min(end, common_idx + 60), {common_idx}))

    out += ["", "Predecessors feeding common terminal", "------------------------------------"]
    for idx in common_refs:
        label_idx, label = nearest_label(lines, idx, start)
        out.append(f"### predecessor label={label} jump_line={idx + 1}")
        # Show enough context to include construction of a0/a1/a2 before the jump.
        out.extend(fmt_block(lines, max(label_idx, idx - 12), min(end, idx + 3), {idx}))
        out.append("")

    out += ["Resource-like constants selected inside focus", "---------------------------------------------"]
    for value in sorted(resources):
        uses = [i for i in range(start, end + 1) if value[2:] in lines[i].upper() or value in lines[i].upper()]
        out.append(f"{value}: focus_lines={','.join(str(i + 1) for i in uses)}")

    out += ["", "Tail call sites", "---------------"]
    for idx, target in tail_calls:
        out.append(f"### {target} at line {idx + 1}")
        out.extend(fmt_block(lines, idx - 8, idx + 8, {idx}))
        out.append("")
    return out, resources


def repository_resource_uses(resources: set[str]) -> list[str]:
    out = ["Repository-wide uses of focus resource-like constants", "----------------------------------------------------"]
    if not resources:
        return out + ["(none)", ""]
    wanted = {v.upper().replace("0X", "") for v in resources}
    hits: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in {".s", ".S", ".c", ".h", ".txt", ".md", ".toml", ".json", ".yml", ".yaml"}:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for i, line in enumerate(lines):
            up = line.upper()
            for raw in wanted:
                if raw in up:
                    hits[raw].append((rel, i + 1, line.strip()))
    for raw in sorted(wanted):
        rows = hits.get(raw, [])
        out.append(f"0x{raw}: total_uses={len(rows)}")
        for rel, line_no, text in rows[:80]:
            out.append(f"  {rel}:{line_no}: {text}")
        if len(rows) > 80:
            out.append(f"  ... {len(rows) - 80} more")
    out.append("")
    return out


def function_definitions_and_callers() -> list[str]:
    files = all_asm()
    definitions: dict[str, tuple[Path, int, int, list[str]]] = {}
    callers: dict[str, list[tuple[Path, int, str]]] = defaultdict(list)

    for path in files:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for target in TAIL_TARGETS:
            if target not in definitions:
                try:
                    s, e, _ = get_function(lines, target)
                except RuntimeError:
                    pass
                else:
                    definitions[target] = (path, s, e, lines)
        for i, line in enumerate(lines):
            m = CALL_RE.search(line)
            if m and m.group(1) in TAIL_TARGETS:
                callers[m.group(1)].append((path, i, line.strip()))

    out = ["Definitions and caller census for bridge functions", "-----------------------------------------------"]
    for target in sorted(TAIL_TARGETS):
        out.append(f"### {target}")
        rows = callers.get(target, [])
        out.append(f"caller_count={len(rows)}")
        for path, idx, text in rows[:30]:
            out.append(f"  {path.relative_to(ROOT).as_posix()}:{idx + 1}: {text}")
        if target not in definitions:
            out.append("definition=(not found in asm/*.s)")
            out.append("")
            continue
        path, s, e, lines = definitions[target]
        out.append(f"definition={path.relative_to(ROOT).as_posix()}:{s + 1}-{e + 1}")
        # Compact head and tail; enough to determine argument/return behavior.
        head_end = min(e, s + 45)
        out.extend(fmt_block(lines, s, head_end))
        if e > head_end + 1:
            out.append("   ...")
            out.extend(fmt_block(lines, max(head_end + 1, e - 25), e))
        out.append("")
    return out


def main() -> int:
    lines = FOCUS_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    out, resources = focus_report(lines)
    out += [""] + repository_resource_uses(resources)
    out += [""] + function_definitions_and_callers()
    out += [
        "Interpretation guardrail",
        "------------------------",
        "Do not label a 0x01DE.... value as a sprite, animation, palette, texture, or table",
        "until the common terminal consumer proves that format. Patch only the class-0x71",
        "allied-side path after that proof; enemy/front behavior remains vanilla.",
        "",
    ]
    text = "\n".join(out)
    output = ROOT / "danika-asset-bridge-report.txt"
    output.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
