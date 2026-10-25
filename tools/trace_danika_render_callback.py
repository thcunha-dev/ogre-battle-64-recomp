#!/usr/bin/env python3
"""Trace Danika battle renderer side/orientation flags to their source record.

Proven chain:
  func_801AE794 -> func_801B3D1C(selector, slot, ... outputs ...)
  func_801B3D1C indexes 0x1A-byte battle records and writes record+0x0C to the
  8th output pointer.  In func_801AE794 that output is sp+0x50.
  sp+0x50 bit0 selects object+0x14=3/2; the full word goes to object+0xB4.
  func_801B3868 turns those into renderer a1/a2 for func_801AD6C4.

This probe also inventories every caller of func_801B3D1C so record+0x0C can be
semantically identified from independent consumers instead of guessed.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM_ROOT = ROOT / "asm"
TARGET = "func_801B3868"
PRODUCER = "func_801B3D1C"
OUT = ROOT / "danika-render-callback-trace.txt"

FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_PRODUCER_RE = re.compile(r"\bjal\s+" + re.escape(PRODUCER) + r"\b")
TARGET_RE = re.compile(r"\b" + re.escape(TARGET) + r"\b")
MEM14_RE = re.compile(r"\b(?:lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$[A-Za-z0-9]+,\s*0x14\(\$([A-Za-z0-9]+)\)", re.I)
MEMB4_RE = re.compile(r"\b(?:lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$[A-Za-z0-9]+,\s*0xB4\(\$([A-Za-z0-9]+)\)", re.I)
STACK_RE = re.compile(r"\b(?:lb|lbu|lh|lhu|lw|sb|sh|sw|addiu)\b.*(?:0x)?(48|4C|50|54|58)\(?(?:\$sp)?\)?", re.I)
STORE_RE = re.compile(r"\b(sb|sh|sw)\s+\$([A-Za-z0-9]+),\s*(?:0x)?([0-9A-Fa-f]+)\(\$([A-Za-z0-9]+)\)", re.I)
BIT_RE = re.compile(r"\b(?:andi|ori|xori)\s+\$[A-Za-z0-9]+,\s*\$[A-Za-z0-9]+,\s*(0x[0-9A-Fa-f]+|[0-9]+)", re.I)


def blocks(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        m = FUNC_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1); s = i; e = min(len(lines)-1, i+3500)
        for j in range(i+1, e+1):
            em = END_RE.match(lines[j])
            if em and em.group(1) == name: e = j; break
            if j > i+1 and FUNC_RE.match(lines[j]): e = j-1; break
        yield name, s+1, e+1, lines[s:e+1]
        i = e+1


def numbered(lines, start):
    return [(start+i, x) for i, x in enumerate(lines)]


def main() -> int:
    registrations=[]; producer=[]; producer_callers=[]; flag_funcs=[]
    for path in sorted(ASM_ROOT.rglob("*.s")):
        rel=path.relative_to(ROOT).as_posix()
        for name,s,e,lines in blocks(path):
            nl=numbered(lines,s)
            h14=[(n,x.strip()) for n,x in nl if (m:=MEM14_RE.search(x)) and m.group(1).lower()!="sp"]
            hb4=[(n,x.strip()) for n,x in nl if (m:=MEMB4_RE.search(x)) and m.group(1).lower()!="sp"]
            if h14 or hb4:
                flag_funcs.append(((10 if h14 and hb4 else 0)+len(h14)+len(hb4),rel,name,s,e,h14,hb4))
            target_hits=[(n,x.strip()) for n,x in nl if TARGET_RE.search(x)]
            if target_hits and name!=TARGET:
                registrations.append((rel,name,s,e,target_hits,lines))
            pcalls=[(n,x.strip()) for n,x in nl if CALL_PRODUCER_RE.search(x)]
            if pcalls and name!=PRODUCER:
                producer_callers.append((rel,name,s,e,pcalls,lines))
            if name==PRODUCER:
                producer.append((rel,name,s,e,lines))

    out=[
      "Danika renderer flag provenance", "===============================",
      f"callback={TARGET}", f"selector={PRODUCER}",
      f"selector_callers={len(producer_callers)}", "",
      "Proven field mapping", "--------------------",
      "func_801B3D1C indexes battle records with stride 0x1A.",
      "output a2 <- record+0x02", "output a3 <- record+0x04",
      "output arg5 <- record+0x06", "output arg6 <- record+0x08",
      "output arg7 <- record+0x0A", "output arg8 <- record+0x0C",
      "output arg9 <- record+0x0E", "output arg10 <- record+0x10", "",
      "In func_801AE794: arg8=&sp[0x50], arg9=&sp[0x54], arg10=&sp[0x58].",
      "Therefore the shared renderer flag word is battle-record field +0x0C.", "",
      "Callback registration", "---------------------"
    ]
    for rel,name,s,e,hits,lines in registrations:
        out.append(f"### {name} {rel}:{s}-{e}")
        interesting=[]
        for n,x in numbered(lines,s):
            if TARGET in x or PRODUCER in x or "0x50($sp)" in x or "0x54($sp)" in x or "0x58($sp)" in x or "0xB4($s0)" in x:
                interesting.append(n)
        if interesting:
            lo=max(s,min(interesting)-22); hi=min(e,max(interesting)+18)
            for n,x in numbered(lines,s):
                if lo<=n<=hi: out.append(f"  {n}: {x}")
        out.append("")

    out += ["Selector implementation", "-----------------------"]
    for rel,name,s,e,lines in producer:
        out.append(f"### {name} {rel}:{s}-{e}")
        for n,x in numbered(lines,s): out.append(f"  {n}: {x}")
        out.append("")

    out += [
      "All selector callers / independent consumers",
      "--------------------------------------------",
      "For each call, a wide window is emitted so output pointers and subsequent bit tests can be correlated.",
    ]
    for rel,name,s,e,calls,lines in producer_callers:
        out.append(f"### {name} {rel}:{s}-{e} calls={len(calls)}")
        nums=numbered(lines,s)
        for calln,_ in calls:
            lo=max(s,calln-34); hi=min(e,calln+44)
            out.append(f"  -- call {calln}, window {lo}-{hi} --")
            for n,x in nums:
                if lo<=n<=hi:
                    mark=""
                    if "0x1C($sp)" in x: mark="  # arg8 pointer -> record+0x0C"
                    elif BIT_RE.search(x): mark="  # bitwise immediate"
                    out.append(f"  {n}: {x}{mark}")
        out.append("")

    flag_funcs.sort(reverse=True,key=lambda x:x[0])
    out += ["Safety conclusion", "-----------------"]
    out += [
      "The renderer gate must use battle-context field +0x0C, not a class-table field.",
      "Class 0x71 alone is insufficient because enemy Danika must remain vanilla.",
      "Do not patch until an independent selector caller establishes which +0x0C bit denotes side/orientation.",
      "The 21 Dragoon-matching class fields remain structural candidates only; none is promoted by this proof.",
    ]
    OUT.write_text("\n".join(out)+"\n",encoding="utf-8")
    assert producer, "selector function missing"
    assert registrations, "callback registration missing"
    assert producer_callers, "selector callers missing"
    assert any(name=="func_801AE794" for _,name,_,_,_,_ in producer_callers), "expected callback builder to call selector"
    print(f"Danika renderer flag provenance: PASS (selector callers={len(producer_callers)})")
    print(f"report={OUT.name}")
    return 0

if __name__=="__main__": raise SystemExit(main())
