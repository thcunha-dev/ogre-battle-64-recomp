#!/usr/bin/env python3
"""Trace writers and owners of the 0x1A-byte battle record backing Danika renderer flags.

The renderer-context word is proven to be battle_record+0x0C, reached through
D_801BA6D8 and func_801B3D1C.  This probe inventories every function that
references D_801BA6D8 (or its address), then highlights stores to +0x0C and
nearby bit construction.  The goal is to prove bit semantics from the producer,
not infer them from appearance.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM_ROOT = ROOT / "asm"
OUT = ROOT / "danika-battle-record-flags.txt"
SYMBOL = "D_801BA6D8"
ADDR = "801BA6D8"

FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
STORE_C_RE = re.compile(r"\b(sb|sh|sw)\s+\$([A-Za-z0-9]+),\s*0x0?C\(\$([A-Za-z0-9]+)\)", re.I)
LOAD_C_RE = re.compile(r"\b(lb|lbu|lh|lhu|lw)\s+\$([A-Za-z0-9]+),\s*0x0?C\(\$([A-Za-z0-9]+)\)", re.I)
BIT_RE = re.compile(r"\b(andi|ori|xori)\s+\$([A-Za-z0-9]+),\s*\$([A-Za-z0-9]+),\s*(0x[0-9A-Fa-f]+|[0-9]+)", re.I)
STRIDE_RE = re.compile(r"\b(?:addiu|ori)\b[^#]*(?:0x1A|26)\b", re.I)


def blocks(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        m = FUNC_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1); s = i; e = min(len(lines)-1, i+5000)
        for j in range(i+1, e+1):
            em = END_RE.match(lines[j])
            if em and em.group(1) == name:
                e = j; break
            if j > i+1 and FUNC_RE.match(lines[j]):
                e = j-1; break
        yield name, s+1, e+1, lines[s:e+1]
        i = e+1


def numbered(lines, start):
    return [(start+i, x) for i,x in enumerate(lines)]


def main() -> int:
    refs=[]; candidates=[]
    for path in sorted(ASM_ROOT.rglob("*.s")):
        rel=path.relative_to(ROOT).as_posix()
        for name,s,e,lines in blocks(path):
            nl=numbered(lines,s)
            sym=[(n,x.strip()) for n,x in nl if SYMBOL in x or (ADDR.lower() in x.lower() and SYMBOL not in x)]
            stores=[(n,x.strip()) for n,x in nl if STORE_C_RE.search(x)]
            loads=[(n,x.strip()) for n,x in nl if LOAD_C_RE.search(x)]
            bits=[(n,x.strip()) for n,x in nl if BIT_RE.search(x)]
            strides=[(n,x.strip()) for n,x in nl if STRIDE_RE.search(x)]
            if sym:
                refs.append((rel,name,s,e,sym,stores,loads,bits,strides,lines))
            # A derived-record writer may not repeat the global symbol in the same function.
            # Keep high-signal 0x1A-stride functions with +0x0C stores as secondary candidates.
            if stores and strides and not sym:
                candidates.append((rel,name,s,e,stores,loads,bits,strides,lines))

    out=[
        "Danika battle-record +0x0C producer trace",
        "=========================================",
        f"symbol={SYMBOL}",
        f"symbol_functions={len(refs)}",
        f"secondary_stride_store_candidates={len(candidates)}",
        "",
        "Known contract",
        "--------------",
        "func_801B3D1C indexes a 0x1A-byte record reached from D_801BA6D8.",
        "record+0x0C is copied into the renderer callback object and supplies renderer context bits 0/1.",
        "",
        "Functions directly referencing D_801BA6D8",
        "------------------------------------------",
    ]
    for rel,name,s,e,sym,stores,loads,bits,strides,lines in refs:
        score=len(stores)*20+len(strides)*5+len(bits)+len(loads)
        out.append(f"### score={score} {name} {rel}:{s}-{e} refs={len(sym)} stores+0C={len(stores)} loads+0C={len(loads)} bits={len(bits)} stride26={len(strides)}")
        interesting=[n for n,_ in sym+stores+loads+bits+strides]
        if interesting:
            for center in sorted(set(interesting)):
                lo=max(s,center-18); hi=min(e,center+24)
                out.append(f"  -- window {lo}-{hi} around {center} --")
                for n,x in numbered(lines,s):
                    if lo<=n<=hi:
                        mark=""
                        if STORE_C_RE.search(x): mark="  # STORE record+0x0C candidate"
                        elif LOAD_C_RE.search(x): mark="  # LOAD +0x0C"
                        elif BIT_RE.search(x): mark="  # bit construction/test"
                        elif SYMBOL in x: mark="  # table base"
                        out.append(f"  {n}: {x}{mark}")
        out.append("")

    out += ["Secondary 0x1A-stride +0x0C writers", "-----------------------------------"]
    for rel,name,s,e,stores,loads,bits,strides,lines in candidates[:80]:
        score=len(stores)*20+len(strides)*5+len(bits)+len(loads)
        out.append(f"### score={score} {name} {rel}:{s}-{e} stores+0C={len(stores)} loads+0C={len(loads)} bits={len(bits)} stride26={len(strides)}")
        centers=[n for n,_ in stores+strides]
        for center in sorted(set(centers)):
            lo=max(s,center-16); hi=min(e,center+22)
            for n,x in numbered(lines,s):
                if lo<=n<=hi:
                    mark=""
                    if STORE_C_RE.search(x): mark="  # STORE +0x0C"
                    elif BIT_RE.search(x): mark="  # bit construction/test"
                    out.append(f"  {n}: {x}{mark}")
        out.append("")

    out += [
        "Interpretation rule",
        "-------------------",
        "Only promote bit 0 or bit 1 to an allied/enemy/front/rear semantic if a producer or independent state machine proves it.",
        "Until then, the executable Danika gate must fail closed and preserve vanilla enemy/front behavior.",
    ]
    OUT.write_text("\n".join(out)+"\n", encoding="utf-8")
    assert refs, f"no {SYMBOL} references found"
    print(f"Danika battle-record flag producer trace: PASS (symbol_functions={len(refs)}, secondary={len(candidates)})")
    print(f"report={OUT.name}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
