#!/usr/bin/env python3
"""Trace provenance of descriptor class bytes +0x4B and +0x4F.

The real renderer reads descriptor+0x4B and +0x4F as class IDs.  The descriptor
pool is allocated through D_801BA690 by func_801AE794 with 0xF8-byte entries,
but those bytes are not directly written in that constructor.  This probe finds
functions that touch the descriptor pool and nearby +0x48..+0x52 bytes, including
base-adjusted stores/copies, to identify the semantic owner of each class byte.
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ASM_ROOT=ROOT/'asm'
OUT=ROOT/'danika-descriptor-class-provenance.txt'
POOL='D_801BA690'
FUNC_RE=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)')
END_RE=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
MEM_NEAR_RE=re.compile(r'\b(lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$([A-Za-z0-9]+),\s*0x(4[89A-Fa-f]|5[0-2])\(\$([A-Za-z0-9]+)\)',re.I)
ADD_NEAR_RE=re.compile(r'\baddiu\s+\$([A-Za-z0-9]+),\s*\$([A-Za-z0-9]+),\s*0x(4[89A-Fa-f]|5[0-2])\b',re.I)
STRIDE_RE=re.compile(r'\b(?:addiu|ori)\b[^#]*(?:0xF8|248)\b',re.I)
COPY_RE=re.compile(r'\bjal\s+(func_80093380|memcpy|bcopy|func_[A-Za-z0-9_]+)')
POOL_RE=re.compile(r'\bD_801BA690\b')
OBJ34_RE=re.compile(r'\b(?:lw|sw)\s+\$([A-Za-z0-9]+),\s*0x34\(\$([A-Za-z0-9]+)\)',re.I)


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
            near=[]; adds=[]; pool=[]; stride=[]; obj34=[]; calls=[]
            for n,x in enumerate(lines,start=s):
                if MEM_NEAR_RE.search(x): near.append((n,x.strip(),MEM_NEAR_RE.search(x).groups()))
                if ADD_NEAR_RE.search(x): adds.append((n,x.strip()))
                if POOL_RE.search(x): pool.append((n,x.strip()))
                if STRIDE_RE.search(x): stride.append((n,x.strip()))
                if OBJ34_RE.search(x): obj34.append((n,x.strip()))
                cm=COPY_RE.search(x)
                if cm: calls.append((n,cm.group(1),x.strip()))
            if near and (pool or stride or obj34 or name in {'func_801AE794','func_801AD6C4'}):
                writes=sum(1 for _,_,g in near if g[0].lower() in {'sb','sh','sw'})
                exact=sum(1 for _,_,g in near if int(g[2],16) in {0x4B,0x4F})
                score=40*writes+50*exact+15*len(pool)+8*len(stride)+8*len(obj34)+len(adds)
                funcs.append((score,rel,name,s,e,near,adds,pool,stride,obj34,calls,lines))
    funcs.sort(key=lambda x:x[0],reverse=True)
    out=['Danika descriptor class provenance','==================================',
         f'candidate_functions={len(funcs)}','',
         'Known contract','--------------',
         'func_801AE794 allocates 0xF8-byte descriptor records in D_801BA690.',
         'Each battle render object stores its descriptor pointer at object+0x34.',
         'func_801AD6C4 reads descriptor+0x4B and descriptor+0x4F as class IDs.','']
    for score,rel,name,s,e,near,adds,pool,stride,obj34,calls,lines in funcs[:100]:
        writes=sum(1 for _,_,g in near if g[0].lower() in {'sb','sh','sw'})
        out.append(f'### score={score} {name} {rel}:{s}-{e} near={len(near)} writes={writes} poolrefs={len(pool)} strideF8={len(stride)} obj34={len(obj34)}')
        centers=sorted(set(n for n,_,_ in near) | set(n for n,_ in pool) | set(n for n,_ in obj34))
        for center in centers:
            lo=max(s,center-30); hi=min(e,center+38)
            out.append(f'  -- window {lo}-{hi} around {center} --')
            for n,x in enumerate(lines,start=s):
                if not(lo<=n<=hi): continue
                mark=''
                mm=MEM_NEAR_RE.search(x)
                if mm:
                    op,reg,off,base=mm.groups(); kind='WRITE' if op.lower() in {'sb','sh','sw'} else 'READ'
                    mark+=f'  # {kind} descriptor-near +0x{off.upper()} base=${base}'
                    if int(off,16) in {0x4B,0x4F}: mark+=' CLASS-BYTE'
                if POOL in x: mark+='  # descriptor pool'
                if OBJ34_RE.search(x): mark+='  # object+0x34 descriptor link'
                if STRIDE_RE.search(x): mark+='  # 0xF8 stride/size'
                cm=COPY_RE.search(x)
                if cm: mark+=f'  # call {cm.group(1)}'
                out.append(f'  {n}: {x}{mark}')
        out.append('')
    out += ['Interpretation guardrail','------------------------',
            'A +0x4B/+0x4F write becomes a player/enemy semantic only after its source value is traced to a known combatant/roster field.',
            'Do not infer side merely from field order or from which class happens to render correctly.',
            'The final Danika override remains class 0x71 plus a proven allied-side condition, with all unresolved cases vanilla.']
    OUT.write_text('\n'.join(out)+'\n',encoding='utf-8')
    assert funcs,'no descriptor provenance candidates found'
    print(f'Danika descriptor class provenance: PASS (candidates={len(funcs)})')
    print(f'report={OUT.name}')
    return 0

if __name__=='__main__': raise SystemExit(main())
