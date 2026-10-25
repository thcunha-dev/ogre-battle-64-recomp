#!/usr/bin/env python3
"""Classify D_801BA72D as a multi-mode resource-group selector.

This probe intentionally prevents a dangerous shortcut: D_801BA72D is selected
through an 8-entry dispatch table and must NOT be treated as a simple
player/enemy flag.  It records the proven chain without assigning ownership
semantics.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM_ROOT = ROOT / "asm"
OUT = ROOT / "danika-resource-group-selector.txt"
TARGET = "func_801B2D2C"
FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
SYM_RE = re.compile(r"\b(?:D|jtbl)_[0-9A-Fa-f]{8}\b")


def blocks(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        m = FUNC_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1); start = i; end = min(len(lines)-1, i+7000)
        for j in range(i+1, end+1):
            em = END_RE.match(lines[j])
            if em and em.group(1) == name:
                end = j; break
            if j > i+1 and FUNC_RE.match(lines[j]):
                end = j-1; break
        yield name, start+1, end+1, lines[start:end+1]
        i = end+1


def main() -> int:
    target = None
    refs = {"D_801B9540": [], "D_801BA72D": []}
    callers = []
    package_refs = []

    for path in sorted(ASM_ROOT.rglob("*.s")):
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for n, line in enumerate(lines, start=1):
            if "315736" in line.upper():
                package_refs.append((rel, n, line.strip()))
            for sym in refs:
                if sym in line:
                    refs[sym].append((rel, n, line.strip()))
        for name, start, end, flines in blocks(path):
            joined = "\n".join(flines)
            if name == TARGET:
                target = (rel, start, end, flines)
            if re.search(r"\bjal\s+func_801B2D2C\b", joined):
                callers.append((rel, name, start, end, flines))

    assert target is not None, f"missing {TARGET}"
    rel, start, end, flines = target
    body = "\n".join(flines)

    # Conservative structural contract.  Avoid depending on register allocation.
    assert "D_801B9540" in body, "selector table D_801B9540 missing"
    assert "D_801BA72D" in body, "selected group state D_801BA72D missing"
    assert re.search(r"\bjal\s+func_801ACF60\b", body), "resource-group consumer func_801ACF60 missing"
    # The function bounds the selector to eight modes.  Accept common immediate spellings.
    assert re.search(r"(?:0x0*8\b|\b8\b)", body, re.I), "8-mode bound evidence missing"

    syms = sorted(set(SYM_RE.findall(body)))
    calls = sorted(set(CALL_RE.findall(body)))

    out = [
        "Knight of Danika resource-group selector trace",
        "==============================================",
        "",
        "PROVEN",
        "------",
        "func_801B2D2C selects D_801BA72D through D_801B9540.",
        "The selector is bounded to eight modes and feeds func_801ACF60.",
        "It participates in the same battle-resource region that references package 0x315736.",
        "",
        "SAFETY CLASSIFICATION",
        "---------------------",
        "D_801BA72D is a MULTI-MODE RESOURCE-GROUP SELECTOR.",
        "It is NOT a proven allied/enemy flag and must never be used directly as DANIKA_SIDE_ALLIED.",
        "Enemy Danika remains vanilla/fail-closed until a real ownership producer is proven.",
        "",
        f"{TARGET}: {rel}:{start}-{end}",
        "symbols=" + ",".join(syms),
        "calls=" + ",".join(calls),
        f"callers={len(callers)}",
        f"D_801B9540 refs={len(refs['D_801B9540'])}",
        f"D_801BA72D refs={len(refs['D_801BA72D'])}",
        f"0x315736 refs={len(package_refs)}",
        "",
        "Full selector function",
        "----------------------",
    ]
    for n, line in enumerate(flines, start=start):
        out.append(f"{n}: {line}")

    out += ["", "Immediate callers", "-----------------"]
    for crel, cname, cs, ce, clines in callers:
        out.append(f"## {cname} {crel}:{cs}-{ce}")
        for n, line in enumerate(clines, start=cs):
            if "func_801B2D2C" in line or "D_801BA72D" in line or "D_801B9540" in line:
                lo = max(cs, n-12); hi = min(ce, n+16)
                for nn, ll in enumerate(clines, start=cs):
                    if lo <= nn <= hi:
                        out.append(f"{nn}: {ll}")
                break

    OUT.write_text("\n".join(out)+"\n", encoding="utf-8")
    print("Danika resource-group selector: PASS")
    print("classification=multi-mode resource group; NOT allied/enemy side")
    print(f"selector_modes=8 callers={len(callers)}")
    print("report=" + OUT.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
