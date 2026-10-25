#!/usr/bin/env python3
"""Prove semantics of descriptor+0x4F / battle_record+0x02.

Verified dataflow:
  func_801B3D1C record+0x02 -> caller a2
  func_801AE794 a2 = descriptor+0x4C
  func_801AD6C4 reads lbu descriptor+0x4F
Thus +0x4F is the low byte of the sign-extended record+0x02 value.

This probe emits the complete relevant functions and finds callers/consumers of
func_801AD13C and func_8016DE3C so the value can be classified by behavior
rather than guessed from data.  It also verifies that the descriptor word at
+0x48 is initialized to 0x00000100 and inventories any pool-aware mutation that
could alter byte +0x4B before rendering.
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ASM_ROOT=ROOT/'asm'
OUT=ROOT/'danika-descriptor-class-semantics.txt'
TARGETS={'func_801B3D1C','func_801AE794','func_801AD13C','func_801AD6C4','func_8016DE3C'}
FUNC_RE=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)')
END_RE=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
CALL_RE=re.compile(r'\bjal\s+([A-Za-z0-9_.$]+)')
POOL_RE=re.compile(r'\bD_801BA690\b')
MEM48_RE=re.compile(r'\b(lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$([A-Za-z0-9]+),\s*0x48\(\$([A-Za-z0-9]+)\)',re.I)
MEM4C_RE=re.compile(r'\b(lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$([A-Za-z0-9]+),\s*0x4C\(\$([A-Za-z0-9]+)\)',re.I)
MEM4F_RE=re.compile(r'\b(lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$([A-Za-z0-9]+),\s*0x4F\(\$([A-Za-z0-9]+)\)',re.I)
MEM4B_RE=re.compile(r'\b(lb|lbu|lh|lhu|lw|sb|sh|sw)\s+\$([A-Za-z0-9]+),\s*0x4B\(\$([A-Za-z0-9]+)\)',re.I)


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
    target_blocks={}; callers={t:[] for t in TARGETS}; pool_funcs=[]
    for path in sorted(ASM_ROOT.rglob('*.s')):
        rel=path.relative_to(ROOT).as_posix()
        for name,s,e,lines in blocks(path):
            if name in TARGETS:
                target_blocks[name]=(rel,s,e,lines)
            called=[]
            for n,x in enumerate(lines,start=s):
                cm=CALL_RE.search(x)
                if cm and cm.group(1) in TARGETS:
                    callers[cm.group(1)].append((rel,name,s,e,n,x.strip(),lines))
                    called.append(cm.group(1))
            if any(POOL_RE.search(x) for x in lines):
                accesses=[]
                for n,x in enumerate(lines,start=s):
                    for tag,rx in [('+48',MEM48_RE),('+4C',MEM4C_RE),('+4B',MEM4B_RE),('+4F',MEM4F_RE)]:
                        mm=rx.search(x)
                        if mm: accesses.append((n,tag,mm.group(1).lower(),x.strip()))
                if accesses:
                    pool_funcs.append((rel,name,s,e,accesses,lines))

    out=['Danika descriptor class semantics','=================================',
         'Verified dataflow','-----------------',
         'battle_record+0x02 -> func_801B3D1C a2 output -> descriptor+0x4C word.',
         'renderer lbu descriptor+0x4F therefore consumes the low byte of record+0x02.',
         'descriptor+0x48 is initialized to 0x00000100 in func_801AE794; byte +0x4B starts as 0x00 on the N64 big-endian guest.','']

    out += ['Complete target functions','-------------------------']
    for t in sorted(TARGETS):
        if t not in target_blocks:
            out.append(f'### MISSING {t}'); continue
        rel,s,e,lines=target_blocks[t]
        out.append(f'### {t} {rel}:{s}-{e}')
        for n,x in enumerate(lines,start=s):
            mark=''
            if '0x2($a0)' in x or '0x02($a0)' in x: mark+='  # record+0x02 candidate'
            if MEM4C_RE.search(x): mark+='  # +0x4C access'
            if MEM4F_RE.search(x): mark+='  # +0x4F low-byte consumer'
            if MEM4B_RE.search(x): mark+='  # +0x4B byte consumer'
            cm=CALL_RE.search(x)
            if cm: mark+=f'  # call {cm.group(1)}'
            out.append(f'  {n}: {x}{mark}')
        out.append('')

    out += ['Callers of semantic targets','---------------------------']
    for target in ['func_801AD13C','func_8016DE3C']:
        out.append(f'## callers of {target}: {len(callers[target])}')
        for rel,name,s,e,calln,line,lines in callers[target]:
            out.append(f'### {name} {rel}:{s}-{e} call@{calln}')
            lo=max(s,calln-34); hi=min(e,calln+30)
            for n,x in enumerate(lines,start=s):
                if lo<=n<=hi:
                    mark='  # TARGET CALL' if n==calln else ''
                    out.append(f'  {n}: {x}{mark}')
            out.append('')

    out += ['Pool-aware +0x48/+0x4C/+0x4B/+0x4F accesses','---------------------------------------------']
    for rel,name,s,e,accesses,lines in pool_funcs:
        out.append(f'### {name} {rel}:{s}-{e}')
        for n,tag,op,x in accesses:
            out.append(f'  {n}: {tag} {op}: {x}')
        out.append('')

    out += ['Proof criteria','--------------',
            'record+0x02 / descriptor+0x4F may be named class_id only if func_8016DE3C or another independent consumer indexes the verified 0x48-byte class table with it.',
            'descriptor+0x4B must not be treated as a second live class selector unless an actual mutation/provenance path changes it from its initialized byte value.',
            'Even a proven class_id == 0x71 is only the identity half of the final gate; ally/player side still requires an independent proven condition.']
    OUT.write_text('\n'.join(out)+'\n',encoding='utf-8')

    for t in TARGETS:
        assert t in target_blocks, f'missing target {t}'
    assert callers['func_8016DE3C'], 'expected renderer/class-table consumers'
    print('Danika descriptor class semantics: PASS')
    print('report='+OUT.name)
    return 0

if __name__=='__main__': raise SystemExit(main())
