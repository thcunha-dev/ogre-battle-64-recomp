#!/usr/bin/env python3
"""Trace the visual-descriptor initializer around func_801AD13C.

The renderer already proves descriptor+0x4F is class identity.  This probe moves
one stage upstream and inventories func_801AD13C plus every immediate caller,
looking for class bytes, resource/table symbols, pointer fields and calls that
could select the actual battle visual/animation resource.

This tool is evidence-only: it does not patch resources or infer allied side.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM_ROOT = ROOT / "asm"
OUT = ROOT / "danika-visual-descriptor-init.txt"
TARGET = "func_801AD13C"
FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
SYM_RE = re.compile(r"\b(?:D|jtbl)_[0-9A-Fa-f]{8}\b")
MEM_RE = re.compile(r"\b(?:lw|sw|lh|lhu|sh|lb|lbu|sb|lwc1|swc1)\s+\$[A-Za-z0-9]+,\s*(-?0x[0-9A-Fa-f]+|-?\d+)\(\$[A-Za-z0-9]+\)")
CLASS_RE = re.compile(r"\b(?:lb|lbu|sb)\s+\$[A-Za-z0-9]+,\s*0x(?:4B|4F)\(\$[A-Za-z0-9]+\)", re.I)


def blocks(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        m = FUNC_RE.match(lines[i])
        if not m:
            i += 1; continue
        name = m.group(1); start=i; end=min(len(lines)-1, i+7000)
        for j in range(i+1,end+1):
            em=END_RE.match(lines[j])
            if em and em.group(1)==name:
                end=j; break
            if j>i+1 and FUNC_RE.match(lines[j]):
                end=j-1; break
        yield name,start+1,end+1,lines[start:end+1]
        i=end+1


def signal_lines(lines, start):
    for n,line in enumerate(lines,start=start):
        tags=[]
        cm=CALL_RE.search(line)
        if cm: tags.append("CALL="+cm.group(1))
        syms=SYM_RE.findall(line)
        if syms: tags.append("SYMS="+",".join(sorted(set(syms))))
        if CLASS_RE.search(line): tags.append("CLASS_BYTE")
        mm=MEM_RE.search(line)
        if mm:
            try:
                off=int(mm.group(1),0)
                if off in {0x18,0x1C,0x20,0x34,0x40,0x4B,0x4C,0x4F,0xB4,0xF4}:
                    tags.append(f"HIGH_VALUE_OFFSET={off:#x}")
            except ValueError:
                pass
        if tags:
            yield n,";".join(tags),line


def main()->int:
    target=None; callers=[]; defs={}
    for path in sorted(ASM_ROOT.rglob("*.s")):
        rel=path.relative_to(ROOT).as_posix()
        for name,s,e,lines in blocks(path):
            defs[name]=(rel,s,e,lines)
            body="\n".join(lines)
            if name==TARGET:
                target=(rel,s,e,lines)
            if re.search(r"\bjal\s+func_801AD13C\b",body):
                callers.append((rel,name,s,e,lines))

    assert target is not None, f"missing {TARGET}"
    rel,s,e,lines=target
    body="\n".join(lines)
    calls=sorted(set(CALL_RE.findall(body)))
    syms=sorted(set(SYM_RE.findall(body)))

    # We intentionally require only that this is a non-trivial initializer;
    # stronger semantics are promoted to assertions only after they are proven.
    assert len(lines) >= 8, "visual descriptor initializer unexpectedly tiny"

    out=[
        "Knight of Danika visual descriptor initializer trace",
        "====================================================",
        "",
        "Purpose: find the smallest resource/animation selector upstream of func_801AD6C4.",
        "Known renderer identity remains descriptor+0x4F; this report does not infer side.",
        "",
        f"{TARGET}: {rel}:{s}-{e}",
        f"instructions/lines={len(lines)}",
        "symbols="+( ",".join(syms) if syms else "<none>"),
        "calls="+( ",".join(calls) if calls else "<none>"),
        f"immediate_callers={len(callers)}",
        "",
        "High-signal lines in initializer",
        "--------------------------------",
    ]
    signals=list(signal_lines(lines,s))
    for n,tags,line in signals:
        out.append(f"{n}: [{tags}] {line}")
    out += ["", "Full initializer", "----------------"]
    for n,line in enumerate(lines,start=s):
        out.append(f"{n}: {line}")

    out += ["", "Immediate callers / descriptor construction context", "---------------------------------------------------"]
    for crel,cname,cs,ce,clines in callers:
        out.append(f"## {cname} {crel}:{cs}-{ce}")
        call_indices=[n for n,line in enumerate(clines,start=cs) if "func_801AD13C" in line]
        for calln in call_indices:
            lo=max(cs,calln-45); hi=min(ce,calln+55)
            out.append(f"### call@{calln}")
            for n,line in enumerate(clines,start=cs):
                if lo<=n<=hi:
                    tags=[]
                    if n==calln: tags.append("TARGET_CALL")
                    if CLASS_RE.search(line): tags.append("CLASS_BYTE")
                    sy=SYM_RE.findall(line)
                    if sy: tags.append("SYMS="+",".join(sorted(set(sy))))
                    cm=CALL_RE.search(line)
                    if cm: tags.append("CALL="+cm.group(1))
                    out.append(f"{n}: {line}"+("  # "+";".join(tags) if tags else ""))

    out += [
        "",
        "Acceptance rule",
        "---------------",
        "Do not implement the Dragoon donor override here until data flow proves both:",
        "(1) class 0x71 reaches a concrete visual/animation resource decision, and",
        "(2) player/allied ownership is independently established.",
    ]
    OUT.write_text("\n".join(out)+"\n",encoding="utf-8")
    print(f"Danika visual descriptor init: PASS (callers={len(callers)}, signals={len(signals)})")
    print("report="+OUT.name)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
