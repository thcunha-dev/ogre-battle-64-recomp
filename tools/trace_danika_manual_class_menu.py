#!/usr/bin/env python3
"""Trace candidates for Ogre Battle 64's manual Change Class UI.

Read-only static analysis. The proven func_8016EA54/func_8016F13C chain is a
class-transition/progression path, not by itself proof of the player's manual
Change Class UI. This tracer now emits the decisive caller chain in full so we
can separate automatic growth/simulation from an actual menu-driven commit.
"""
from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ASM_ROOT = ROOT / "asm"

FUNC = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL = re.compile(r"\bjal\s+(func_[0-9A-Fa-f]+)\b")
CLASS_SYM = re.compile(r"\bD_80187C(?:34|38|39|57|58|62|64|66|68|75|76|77|78|79|7A)\b")
CHAR_CLASS = re.compile(r"\b(?:lbu|lb|sb)\s+[^\n]*0x12\(\$[a-z0-9]+\)")
LOOP_BOUND = re.compile(r"\b(?:sltiu?|ori|addiu)\s+[^\n]*(?:0xFF|0xFE|0x100|0xA0|0x9F)\b", re.I)
STORE_BYTE = re.compile(r"\bsb\s+[^\n]+")
TEXTISH = re.compile(r"(?:0x303[0-9]|0x313[0-9]|0x323[0-9]|0x8194|0x8196|0x0D|0x0A)", re.I)

# These are the exact nodes currently proven around the transition engine.
DEEP_TARGETS = [
    "func_80184D90",  # only caller of F13C
    "func_80071EB0",  # caller of 80184D90
    "func_8019BB9C",  # caller of 80184D90
    "func_8016EBC4",  # per-step stat rebuild helper
    "func_8016F13C",
    "func_8016EA54",
]


def all_functions(path: Path):
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
        end = len(lines) - 1
        for j in range(i + 1, len(lines)):
            em = END.match(lines[j])
            if em:
                end = j
                break
            if FUNC.match(lines[j]):
                end = j - 1
                break
        out.append((name, start + 1, end + 1, lines[start:end + 1]))
        i = max(end + 1, i + 1)
    return out


def main():
    funcs = {}
    callers = {}
    candidates = []
    for path in sorted(ASM_ROOT.rglob("*.s")):
        try:
            blocks = all_functions(path)
        except OSError:
            continue
        for name, start, end, body in blocks:
            text = "\n".join(body)
            funcs[name] = (path, start, end, body, text)
            for callee in CALL.findall(text):
                callers.setdefault(callee, []).append((path, name, start, end))
            syms = sorted(set(CLASS_SYM.findall(text)))
            if not syms:
                continue
            has_char = bool(CHAR_CLASS.search(text))
            has_bound = bool(LOOP_BOUND.search(text))
            stores = len(STORE_BYTE.findall(text))
            calls = len(CALL.findall(text))
            textish = len(TEXTISH.findall(text))
            score = 0
            if has_char: score += 5
            if has_bound: score += 4
            if len(syms) >= 2: score += 2
            if stores: score += 1
            if calls >= 3: score += 1
            if textish >= 6: score -= 8
            candidates.append((score, path, name, start, end, syms, has_char, has_bound, stores, calls, textish))

    print("Knight of Danika manual Change Class candidate trace")
    print("====================================================")
    print("automatic_transition_path=func_8016EA54/func_8016F13C")
    print("known_text_parser_false_positive=func_8017FC48")
    print("goal=find_manual_class_list_or_selection_path")
    print()

    print("DEEP_NATIVE_CHAIN")
    for target in DEEP_TARGETS:
        if target not in funcs:
            print(f"TARGET {target} MISSING")
            continue
        p, s, e, body, text = funcs[target]
        print(f"--- TARGET {target} {p.relative_to(ROOT)}:{s}-{e} ---")
        print("CALLERS")
        for cp, cn, cs, ce in callers.get(target, []):
            print(f"  {cp.relative_to(ROOT)}:{cs}-{ce} {cn}")
        print("CALLEES")
        for callee in CALL.findall(text):
            print(f"  {callee}")
        print("BODY")
        for line in body:
            print(line)
        print()

    candidates.sort(key=lambda x: (-x[0], str(x[1]), x[3]))
    print("RANKED_CLASS_UI_CANDIDATES")
    for row in candidates[:30]:
        score, path, name, start, end, syms, has_char, has_bound, stores, calls, textish = row
        print(f"CAND score={score:02d} {path.relative_to(ROOT)}:{start}-{end} function={name} char_class={int(has_char)} broad_bound={int(has_bound)} stores={stores} calls={calls} textish={textish} syms={','.join(syms)}")
    print()

    assert all(t in funcs for t in ["func_80184D90", "func_8016F13C", "func_8016EA54"])
    assert any(cn == "func_80184D90" for _, cn, _, _ in callers.get("func_8016F13C", []))
    assert any(cn == "func_80071EB0" for _, cn, _, _ in callers.get("func_80184D90", []))
    assert any(cn == "func_8019BB9C" for _, cn, _, _ in callers.get("func_80184D90", []))
    print("manual class-menu candidate trace: PASS")


if __name__ == "__main__":
    main()
