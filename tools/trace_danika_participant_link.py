#!/usr/bin/env python3
"""Trace the bridge from static render descriptors to live battle participants.

The renderer identity half is proven: descriptor+0x4F is a class_id.  The
remaining blocker is an independent allied/player-side condition.  This probe
focuses on the post-descriptor setup function func_801B2314, its callers and
callees, and functions in the battle overlay that read a character/unit-like
class byte at +0x12 while also touching descriptor/object globals.

It deliberately does not guess which adjacent field is team/side; it emits the
candidate structures and call graph so a side field can be proven from control
flow.
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ASM_ROOT=ROOT/'asm'
OUT=ROOT/'danika-participant-link.txt'
TARGET='func_801B2314'
FUNC_RE=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)')
END_RE=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
CALL_RE=re.compile(r'\bjal\s+([A-Za-z0-9_.$]+)')
CLASS12_RE=re.compile(r'\b(?:lb|lbu)\s+\$([A-Za-z0-9]+),\s*0x12\(\$([A-Za-z0-9]+)\)',re.I)
NEAR_RE=re.compile(r'\b(?:lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$([A-Za-z0-9]+),\s*0x([0-3][0-9A-Fa-f])\(\$([A-Za-z0-9]+)\)',re.I)
BATTLE_GLOBAL_RE=re.compile(r'D_801BA(?:68C|690|694|6D8|72D|624|600)|D_801B9[0-9A-Fa-f]{3}')
OBJ34_RE=re.compile(r'\b(?:lw|sw)\s+\$([A-Za-z0-9]+),\s*0x34\(\$([A-Za-z0-9]+)\)',re.I)
STRIDES=(0xF8,0xB8,0x60,0x1A,0x48)


def blocks(path):
    lines=path.read_text(encoding='utf-8',errors='replace').splitlines(); i=0
    while i<len(lines):
        m=FUNC_RE.match(lines[i])
        if not m: i+=1; continue
        name=m.group(1); s=i; e=min(len(lines)-1,i+6500)
        for j in range(i+1,e+1):
            em=END_RE.match(lines[j])
            if em and em.group(1)==name: e=j; break
            if j>i+1 and FUNC_RE.match(lines[j]): e=j-1; break
        yield name,s+1,e+1,lines[s:e+1]; i=e+1


def stride_hits(lines,s):
    out=[]
    for n,x in enumerate(lines,start=s):
        for v in STRIDES:
            if re.search(rf'\b(?:addiu|ori)\b[^#]*(?:0x{v:X}|{v})\b',x,re.I):
                out.append((n,v,x.strip()))
    return out


def main():
    target_block=None; callers=[]; target_callees=[]; class_candidates=[]
    all_blocks=[]
    for path in sorted(ASM_ROOT.rglob('*.s')):
        rel=path.relative_to(ROOT).as_posix()
        # prioritize battle overlay for candidates, but target may be anywhere
        for name,s,e,lines in blocks(path):
            all_blocks.append((rel,name,s,e,lines))
            if name==TARGET:
                target_block=(rel,name,s,e,lines)
            calls=[]
            for n,x in enumerate(lines,start=s):
                cm=CALL_RE.search(x)
                if cm: calls.append((n,cm.group(1),x.strip()))
            if any(c==TARGET for _,c,_ in calls):
                callers.append((rel,name,s,e,calls,lines))
            classreads=[]
            for n,x in enumerate(lines,start=s):
                m=CLASS12_RE.search(x)
                if m: classreads.append((n,m.group(1),m.group(2),x.strip()))
            if classreads and rel.endswith('1CE040.s'):
                globals_=[(n,x.strip()) for n,x in enumerate(lines,start=s) if BATTLE_GLOBAL_RE.search(x)]
                obj34=[(n,x.strip()) for n,x in enumerate(lines,start=s) if OBJ34_RE.search(x)]
                sh=stride_hits(lines,s)
                calls2=[(n,c,x) for n,c,x in calls]
                score=50*len(classreads)+12*len(globals_)+10*len(obj34)+4*len(sh)
                class_candidates.append((score,rel,name,s,e,classreads,globals_,obj34,sh,calls2,lines))

    assert target_block, 'func_801B2314 not found'
    rel,name,s,e,lines=target_block
    for n,x in enumerate(lines,start=s):
        cm=CALL_RE.search(x)
        if cm: target_callees.append((n,cm.group(1),x.strip()))

    # Pull direct callee bodies too, because the participant link may be one hop down.
    callee_names={c for _,c,_ in target_callees}
    callee_blocks=[b for b in all_blocks if b[1] in callee_names]
    class_candidates.sort(key=lambda x:x[0],reverse=True)

    out=['Danika live participant bridge trace','===================================',
         f'target={TARGET}',f'direct_callers={len(callers)}',f'direct_callees={len(target_callees)}',
         f'battle_overlay_class+0x12_candidates={len(class_candidates)}','',
         'Goal','----',
         'Find a live battle participant/unit record carrying class_id plus an independently meaningful owner/team/side field.',
         'Do not use scene-layout IDs or renderer interpolation flags as side proxies.','']

    out += ['Target function','---------------',f'### {name} {rel}:{s}-{e}']
    for n,x in enumerate(lines,start=s):
        mark=''
        cm=CALL_RE.search(x)
        if cm: mark+=f'  # call {cm.group(1)}'
        if CLASS12_RE.search(x): mark+='  # class-like +0x12 read'
        if BATTLE_GLOBAL_RE.search(x): mark+='  # battle global'
        if OBJ34_RE.search(x): mark+='  # object+0x34 descriptor link'
        out.append(f'  {n}: {x}{mark}')
    out.append('')

    out += ['Direct callers','--------------']
    for rel2,name2,s2,e2,calls2,lines2 in callers:
        out.append(f'### {name2} {rel2}:{s2}-{e2}')
        centers=[n for n,c,_ in calls2 if c==TARGET]
        for center in centers:
            lo=max(s2,center-60); hi=min(e2,center+45)
            for n,x in enumerate(lines2,start=s2):
                if lo<=n<=hi:
                    mark='  # TARGET CALL' if n==center else ''
                    if BATTLE_GLOBAL_RE.search(x): mark+='  # battle global'
                    out.append(f'  {n}: {x}{mark}')
        out.append('')

    out += ['Direct callee bodies','--------------------']
    for rel2,name2,s2,e2,lines2 in callee_blocks:
        out.append(f'### {name2} {rel2}:{s2}-{e2}')
        # cap enormous unrelated callees, but include complete modest functions
        maxn=min(e2,s2+550)
        for n,x in enumerate(lines2,start=s2):
            if n>maxn: break
            mark=''
            if CLASS12_RE.search(x): mark+='  # class-like +0x12 read'
            if BATTLE_GLOBAL_RE.search(x): mark+='  # battle global'
            if OBJ34_RE.search(x): mark+='  # descriptor link'
            out.append(f'  {n}: {x}{mark}')
        if e2>maxn: out.append(f'  ... truncated at {maxn}, function ends {e2}')
        out.append('')

    out += ['Battle-overlay live class-record candidates','-------------------------------------------']
    for score,rel2,name2,s2,e2,classreads,globals_,obj34,sh,calls2,lines2 in class_candidates[:80]:
        out.append(f'### score={score} {name2} {rel2}:{s2}-{e2} class12={len(classreads)} globals={len(globals_)} obj34={len(obj34)} strides={[(hex(v),n) for n,v,_ in sh[:6]]}')
        centers=sorted(set(n for n,_,_,_ in classreads) | set(n for n,_ in globals_) | set(n for n,_ in obj34))
        for center in centers[:20]:
            lo=max(s2,center-24); hi=min(e2,center+30)
            out.append(f'  -- window {lo}-{hi} around {center} --')
            for n,x in enumerate(lines2,start=s2):
                if lo<=n<=hi:
                    mark=''
                    m=CLASS12_RE.search(x)
                    if m: mark+=f'  # CLASS +0x12 base=${m.group(2)}'
                    if BATTLE_GLOBAL_RE.search(x): mark+='  # battle global'
                    if OBJ34_RE.search(x): mark+='  # descriptor link'
                    out.append(f'  {n}: {x}{mark}')
        out.append('')

    out += ['Proof rule','----------',
            'A field becomes the allied/player gate only if its producer or control-flow consumer independently identifies ownership/team.',
            'Class 0x71 alone is insufficient: enemy Danika must remain vanilla.',
            'If no live side field is proven, executable override remains disabled/fail-closed.']
    OUT.write_text('\n'.join(out)+'\n',encoding='utf-8')
    print(f'Danika participant bridge trace: PASS (callers={len(callers)}, callees={len(target_callees)}, class_candidates={len(class_candidates)})')
    print('report='+OUT.name)
    return 0

if __name__=='__main__': raise SystemExit(main())
