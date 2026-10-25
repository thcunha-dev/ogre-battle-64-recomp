#!/usr/bin/env python3
"""Trace the full battle class word behind descriptor+0x4C.

Verified: battle_record+0x02 is loaded as signed halfword by func_801B3D1C and
stored as a 32-bit word at descriptor+0x4C by func_801AE794. The renderer uses
only descriptor+0x4F (low byte) as class_id. This leaves the upper byte(s) as a
high-value place to look for participant/side flags tied to the same combatant.

This probe inventories reads of +0x4C/+0x4D/+0x4E/+0x4F, bit masks/branches on
values derived from them, and the source halfword's consumers. It is evidence
only: no high bit is named allied/enemy until independent control-flow proves it.
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ASM_ROOT=ROOT/'asm'
OUT=ROOT/'danika-classword-flags.txt'
FUNC_RE=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)')
END_RE=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
MEM_RE=re.compile(r'\b(lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$([A-Za-z0-9]+),\s*0x(4[C-Fc-f])\(\$([A-Za-z0-9]+)\)',re.I)
BIT_RE=re.compile(r'\b(andi|ori|xori|sll|srl|sra)\s+\$([A-Za-z0-9]+),\s*\$([A-Za-z0-9]+)(?:,\s*(0x[0-9A-Fa-f]+|[0-9]+))?',re.I)
BR_RE=re.compile(r'\b(beq|bne|beqz|bnez|sltiu|slti|sltu|slt)\b',re.I)
CALL_RE=re.compile(r'\bjal\s+([A-Za-z0-9_.$]+)')
POOL_RE=re.compile(r'D_801BA690|0xF8\b|248\b',re.I)


def blocks(path):
    lines=path.read_text(encoding='utf-8',errors='replace').splitlines(); i=0
    while i<len(lines):
        m=FUNC_RE.match(lines[i])
        if not m: i+=1; continue
        name=m.group(1); s=i; e=min(len(lines)-1,i+6000)
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
            accesses=[]; bits=[]; branches=[]; calls=[]; pool=[]
            for n,x in enumerate(lines,start=s):
                mm=MEM_RE.search(x)
                if mm: accesses.append((n,mm.groups(),x.strip()))
                bm=BIT_RE.search(x)
                if bm: bits.append((n,bm.groups(),x.strip()))
                if BR_RE.search(x): branches.append((n,x.strip()))
                cm=CALL_RE.search(x)
                if cm: calls.append((n,cm.group(1),x.strip()))
                if POOL_RE.search(x): pool.append((n,x.strip()))
            if accesses:
                writes=sum(1 for _,g,_ in accesses if g[0].lower() in {'sb','sh','sw'})
                upper=sum(1 for _,g,_ in accesses if int(g[2],16) in {0x4C,0x4D,0x4E})
                low=sum(1 for _,g,_ in accesses if int(g[2],16)==0x4F)
                score=35*writes+22*upper+12*low+4*len(bits)+8*len(pool)
                funcs.append((score,rel,name,s,e,accesses,bits,branches,calls,pool,lines))
    funcs.sort(key=lambda x:x[0],reverse=True)
    out=['Danika descriptor class-word flag trace','=======================================',
         f'functions={len(funcs)}','',
         'Verified source contract','------------------------',
         'battle_record+0x02 (signed halfword) -> descriptor+0x4C word.',
         'descriptor+0x4F low byte -> proven class_id; Danika identity is 0x71.',
         'Upper byte(s) remain unclassified until independent behavioral proof.','']
    for score,rel,name,s,e,accesses,bits,branches,calls,pool,lines in funcs[:140]:
        writes=sum(1 for _,g,_ in accesses if g[0].lower() in {'sb','sh','sw'})
        out.append(f'### score={score} {name} {rel}:{s}-{e} accesses={len(accesses)} writes={writes} pool={len(pool)}')
        centers=sorted(set(n for n,_,_ in accesses))
        for center in centers[:30]:
            lo=max(s,center-26); hi=min(e,center+34)
            out.append(f'  -- window {lo}-{hi} around {center} --')
            taint={}
            for n,x in enumerate(lines,start=s):
                if n<lo or n>hi: continue
                mark=''
                mm=MEM_RE.search(x)
                if mm:
                    op,dst,off,base=mm.groups(); kind='WRITE' if op.lower() in {'sb','sh','sw'} else 'READ'
                    mark+=f'  # {kind} +0x{off.upper()} base=${base}'
                    if kind=='READ': taint[dst.lower()]=(off.upper(),n)
                bm=BIT_RE.search(x)
                if bm:
                    op,dst,src,imm=bm.groups(); src=src.lower()
                    if src in taint:
                        mark+=f'  # {op} on value from +0x{taint[src][0]}'
                        if imm: mark+=f' imm={imm}'
                        taint[dst.lower()]=(taint[src][0],n)
                if BR_RE.search(x):
                    regs=[r.lower() for r in re.findall(r'\$([A-Za-z0-9]+)',x)]
                    if any(r in taint for r in regs): mark+='  # BRANCH on class-word-derived value'
                cm=CALL_RE.search(x)
                if cm: mark+=f'  # call {cm.group(1)}'
                if POOL_RE.search(x): mark+='  # descriptor-pool context'
                out.append(f'  {n}: {x}{mark}')
        out.append('')
    out += ['Proof rule','----------',
            'A high byte/bit becomes DANIKA_SIDE_ALLIED only if a separate gameplay/control path proves that meaning.',
            'If upper bits are merely class flags, animation metadata, or resource modifiers, they must not be used as side.',
            'Enemy Danika remains vanilla for UNKNOWN/ENEMY.']
    OUT.write_text('\n'.join(out)+'\n',encoding='utf-8')
    assert funcs,'no descriptor class-word consumers found'
    print(f'Danika class-word flags trace: PASS (functions={len(funcs)})')
    print('report='+OUT.name)
    return 0

if __name__=='__main__': raise SystemExit(main())
