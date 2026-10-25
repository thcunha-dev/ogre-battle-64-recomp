#!/usr/bin/env python3
"""Trace semantic consumers of battle-object +0x14 and +0xB4.

For objects created by func_801AE794, battle_record+0x0C bit0 selects +0x14 = 3
or 2, while the full word is copied to +0xB4.  This probe ranks functions that
read these offsets, especially branches comparing +0x14 against 2/3 and bit
tests on +0xB4.  It also records nearby calls/stores so the state can be named
from behavior instead of sprite appearance.
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ASM_ROOT=ROOT/'asm'
OUT=ROOT/'danika-object-state-semantics.txt'
FUNC_RE=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)')
END_RE=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
M14_RE=re.compile(r'\b(lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$([A-Za-z0-9]+),\s*0x14\(\$([A-Za-z0-9]+)\)',re.I)
MB4_RE=re.compile(r'\b(lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$([A-Za-z0-9]+),\s*0xB4\(\$([A-Za-z0-9]+)\)',re.I)
IMM23_RE=re.compile(r'\b(?:addiu|ori)\s+\$([A-Za-z0-9]+),\s*\$zero,\s*(?:0x)?([23])\b',re.I)
BIT_RE=re.compile(r'\b(?:andi|ori|xori)\s+\$([A-Za-z0-9]+),\s*\$([A-Za-z0-9]+),\s*(0x[0-9A-Fa-f]+|[0-9]+)',re.I)
BR_RE=re.compile(r'\b(beq|bne|beql|bnel)\s+\$([A-Za-z0-9]+),\s*\$([A-Za-z0-9]+)',re.I)
CALL_RE=re.compile(r'\bjal\s+([A-Za-z0-9_.$]+)')


def blocks(path):
    lines=path.read_text(encoding='utf-8',errors='replace').splitlines(); i=0
    while i<len(lines):
        m=FUNC_RE.match(lines[i])
        if not m: i+=1; continue
        name=m.group(1); s=i; e=min(len(lines)-1,i+5000)
        for j in range(i+1,e+1):
            em=END_RE.match(lines[j])
            if em and em.group(1)==name: e=j; break
            if j>i+1 and FUNC_RE.match(lines[j]): e=j-1; break
        yield name,s+1,e+1,lines[s:e+1]; i=e+1


def main():
    funcs=[]
    for path in sorted(ASM_ROOT.rglob('*.s')):
        rel=path.relative_to(ROOT).as_posix()
        for name,s,e,lines in blocks(path):
            h14=[]; hb4=[]; imms=[]; bits=[]; branches=[]; calls=[]
            for n,x in enumerate(lines,start=s):
                if M14_RE.search(x): h14.append((n,x.strip()))
                if MB4_RE.search(x): hb4.append((n,x.strip()))
                if IMM23_RE.search(x): imms.append((n,x.strip()))
                if BIT_RE.search(x): bits.append((n,x.strip()))
                if BR_RE.search(x): branches.append((n,x.strip()))
                cm=CALL_RE.search(x)
                if cm: calls.append((n,cm.group(1),x.strip()))
            if h14 or hb4:
                score=40*(bool(h14) and bool(hb4))+20*len(h14)+25*len(hb4)+6*len(imms)+3*len(bits)
                funcs.append((score,rel,name,s,e,h14,hb4,imms,bits,branches,calls,lines))
    funcs.sort(key=lambda x:x[0],reverse=True)
    out=['Danika battle-object state semantics','====================================',
         f'functions_touching_state={len(funcs)}','',
         'Known provenance','----------------',
         'func_801AE794: battle_record+0x0C bit0 set -> object+0x14=3; clear -> object+0x14=2.',
         'func_801AE794: complete battle_record+0x0C word -> object+0xB4.',
         'func_801B3868: renderer a1=(object+0x14 != 3), a2=(object+0xB4 & 0x2).','']
    for score,rel,name,s,e,h14,hb4,imms,bits,branches,calls,lines in funcs[:120]:
        out.append(f'### score={score} {name} {rel}:{s}-{e} +14={len(h14)} +B4={len(hb4)} imm2/3={len(imms)} bits={len(bits)}')
        centers=sorted(set(n for n,_ in h14+hb4))
        for center in centers:
            lo=max(s,center-28); hi=min(e,center+34)
            out.append(f'  -- semantic window {lo}-{hi} around {center} --')
            recent_state_regs={}
            recent_imms={}
            for n,x in enumerate(lines,start=s):
                if n<lo or n>hi: continue
                m14=M14_RE.search(x); mb4=MB4_RE.search(x); im=IMM23_RE.search(x); bit=BIT_RE.search(x); br=BR_RE.search(x)
                mark=''
                if m14:
                    recent_state_regs[m14.group(2).lower()]=('14',n)
                    mark='  # object+0x14 access'
                elif mb4:
                    recent_state_regs[mb4.group(2).lower()]=('B4',n)
                    mark='  # object+0xB4 access'
                if im:
                    recent_imms[im.group(1).lower()]=(im.group(2),n)
                    mark += '  # immediate state 2/3'
                if bit:
                    src=bit.group(2).lower()
                    if src in recent_state_regs:
                        mark += f'  # bit-op on recent +0x{recent_state_regs[src][0]} value'
                if br:
                    r1=br.group(2).lower(); r2=br.group(3).lower()
                    pairs=[]
                    for state_reg,other in ((r1,r2),(r2,r1)):
                        if state_reg in recent_state_regs and other in recent_imms:
                            pairs.append((recent_state_regs[state_reg],recent_imms[other]))
                    if pairs:
                        mark += '  # DIRECT state comparison'
                cm=CALL_RE.search(x)
                if cm: mark += f'  # call {cm.group(1)}'
                out.append(f'  {n}: {x}{mark}')
        out.append('')
    out += ['Interpretation rule','-------------------',
            'Do not call +0x14 state 2/3 player/enemy or front/rear merely from renderer behavior.',
            'Promote a semantic only when another consumer performs behavior whose meaning is independently clear.',
            'An allied-Danika executable gate must fail closed until that proof exists.']
    OUT.write_text('\n'.join(out)+'\n',encoding='utf-8')
    assert funcs,'no object state consumers found'
    print(f'Danika object-state semantics trace: PASS (functions={len(funcs)})')
    print(f'report={OUT.name}')
    return 0

if __name__=='__main__': raise SystemExit(main())
