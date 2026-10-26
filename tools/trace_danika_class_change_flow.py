#!/usr/bin/env python3
"""Trace the real class-transition flow used by Ogre Battle 64.

Read-only source analysis.  The playable Danika project previously used a
roster-write smoke test; this tracer instead focuses on the game's native class
selection path so class 0x71 can eventually be exposed through the real menu.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ASM_ROOT = ROOT / "asm"
TARGETS = {"func_8016EA54", "func_8016F13C"}
TAIL_SYMBOLS = {"D_80187C75", "D_80187C76", "D_80187C77", "D_80187C78"}
FUNC = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL = re.compile(r"\bjal\s+(func_[0-9A-Fa-f]+)\b")


def functions(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out = []
    i = 0
    while i < len(lines):
        m = FUNC.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        start = i
        end = i
        for j in range(i + 1, len(lines)):
            if END.match(lines[j]):
                end = j
                break
            if FUNC.match(lines[j]):
                end = j - 1
                break
        out.append((name, start + 1, end + 1, lines[start:end + 1]))
        i = max(end + 1, i + 1)
    return out


def main():
    found = {}
    refs = []
    callers = []

    for path in sorted(ASM_ROOT.rglob("*.s")):
        try:
            blocks = functions(path)
        except OSError:
            continue
        for name, start, end, body in blocks:
            text = "\n".join(body)
            if name in TARGETS:
                found[name] = (path, start, end, body)
            syms = sorted(sym for sym in TAIL_SYMBOLS if sym in text)
            if syms:
                refs.append((path, name, start, end, syms))
            for called in CALL.findall(text):
                if called in TARGETS:
                    callers.append((path, name, start, end, called))

    print("Knight of Danika native class-change flow trace")
    print("===============================================")
    print("goal=expose class 0x71 through native class-selection logic")
    print("legacy_auto_roster_swap=REJECTED_AS_MENU_TEST")
    print()

    for target in sorted(TARGETS):
        assert target in found, f"missing target function {target}"
        path, start, end, body = found[target]
        print(f"TARGET {target} {path.relative_to(ROOT)}:{start}-{end}")
        for line in body:
            print(line)
        print()

    print("CLASS_TAIL_REFERENCES")
    for path, name, start, end, syms in refs:
        print(f"REF {path.relative_to(ROOT)}:{start}-{end} function={name} symbols={','.join(syms)}")
    print()

    print("TARGET_CALLERS")
    for path, name, start, end, called in callers:
        print(f"CALLER {path.relative_to(ROOT)}:{start}-{end} function={name} calls={called}")
    print()

    assert any(name == "func_8016EA54" for _, name, *_ in refs), "EA54 must consume transition fields"
    assert any(name == "func_8016F13C" for _, name, *_ in refs), "F13C must consume transition fields"
    print("class-change flow trace: PASS")


if __name__ == "__main__":
    main()
