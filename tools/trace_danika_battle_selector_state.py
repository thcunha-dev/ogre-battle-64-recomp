#!/usr/bin/env python3
"""Trace the battle-group selector D_801BA72D used by func_801AE794.

func_801AE794 calls func_801B3D1C(a0=D_801BA72D, a1=slot, ...).  Therefore
D_801BA72D selects the top-level 0x1A-record group while slot selects a record
inside that group.  This probe inventories reads/writes and nearby state-machine
branches to establish which selector value corresponds to the player/allied side.
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ASM_ROOT=ROOT/'asm'
OUT=ROOT/'danika-battle-selector-state.txt'
SYMBOL='D_801BA72D'
ADDR='801BA72D'
FUNC_RE=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)')
END_RE=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
WRITE_RE=re.compile(r'\b(?:sb|sh|sw)\s+\$([A-Za-z0-9]+),\s*%lo\(D_801BA72D\)\(\$([A-Za-z0-9]+)\)',re.I)
READ_RE=re.compile(r'\b(?:lb|lbu|lh|lhu|lw)\s+\$([A-Za-z0-9]+),\s*%lo\(D_801BA72D\)\(\$([A-Za-z0-9]+)\)',re.I)
IMM_RE=re.compile(r'\b(?:addiu|ori)\s+\$([A-Za-z0-9]+),\s*\$zero,\s*(0x[0-9A-Fa-f]+|-?[0-9]+)',re.I)


def blocks(path):
    lines=path.read_text(encoding='utf-8',errors='replace').splitlines(); i=0
    while i<len(lines):
        m=FUNC_RE.match(lines[i])
        if not m: i+=1; continue
        name=m.group(1); s=i; e=min(len(lines)-1,i+4500)
        for j in range(i+1,e+1):
            em=END_RE.match(lines[j])
            if em and em.group(1)==name: e=j; break
            if j>i+1 and FUNC_RE.match(lines[j]): e=j-1; break
        yield name,s+1,e+1,lines[s:e+1]; i=e+1

def main():
    hits=[]
    for path in sorted(ASM_ROOT.rglob('*.s')):
        rel=path.relative_to(ROOT).as_posix()
        for name,s,e,lines in blocks(path):
            refs=[]; writes=[]; reads=[]
            for k,x in enumerate(lines,start=s):
                if SYMBOL in x or (ADDR.lower() in x.lower() and SYMBOL not in x): refs.append((k,x.strip()))
                if WRITE_RE.search(x): writes.append((k,x.strip()))
                if READ_RE.search(x): reads.append((k,x.strip()))
            if refs:
                hits.append((rel,name,s,e,refs,writes,reads,lines))
    out=['Danika battle group selector trace','=================================',f'symbol={SYMBOL}',f'functions={len(hits)}','',
         'Contract','--------','func_801AE794 passes D_801BA72D as selector/group a0 to func_801B3D1C and slot index as a1.','']
    for rel,name,s,e,refs,writes,reads,lines in hits:
        score=30*len(writes)+5*len(reads)+len(refs)
        out.append(f'### score={score} {name} {rel}:{s}-{e} refs={len(refs)} writes={len(writes)} reads={len(reads)}')
        centers=sorted(set(n for n,_ in refs+writes+reads))
        for center in centers:
            lo=max(s,center-30); hi=min(e,center+36)
            out.append(f'  -- window {lo}-{hi} around {center} --')
            reg_imm={}
            for n,x in enumerate(lines,start=s):
                if lo<=n<=hi:
                    im=IMM_RE.search(x)
                    if im: reg_imm[im.group(1).lower()]=(n,im.group(2))
                    mark=''
                    wm=WRITE_RE.search(x)
                    rm=READ_RE.search(x)
                    if wm:
                        src=wm.group(1).lower(); mark='  # WRITE selector'
                        if src in reg_imm: mark+=f' (recent immediate {reg_imm[src][1]} at line {reg_imm[src][0]})'
                    elif rm: mark='  # READ selector'
                    elif SYMBOL in x: mark='  # selector symbol'
                    out.append(f'  {n}: {x}{mark}')
        out.append('')
    out += ['Interpretation guardrail','------------------------',
            'A numeric selector value is named player/allied only when surrounding battle-state control flow proves that meaning.',
            'Until proven, class 0x71 remains vanilla outside a fail-closed context gate.']
    OUT.write_text('\n'.join(out)+'\n',encoding='utf-8')
    assert hits,'selector symbol not found'
    assert any(w for *_,w,r,l in hits),'selector has no writer'
    print(f'Danika battle selector state trace: PASS (functions={len(hits)})')
    print(f'report={OUT.name}')
    return 0

if __name__=='__main__': raise SystemExit(main())
