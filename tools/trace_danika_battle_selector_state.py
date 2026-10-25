#!/usr/bin/env python3
"""Trace the battle-group selector D_801BA72D used by func_801AE794.

func_801AE794 calls func_801B3D1C(a0=D_801BA72D, a1=slot, ...).  D_801BA72D
is written by func_801B2D2C from the low byte of D_801B9540[s3]; the high bit of
the same table entry controls D_801BA624.  This probe traces:
  * all reads/writes of D_801BA72D;
  * the complete writer prologue around func_801B2D2C;
  * every direct caller of func_801B2D2C and how it constructs a0/s3;
  * every reference/definition of D_801B9540, including nearby static values.
The goal is to name the selector groups from independent battle-state evidence.
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ASM_ROOT=ROOT/'asm'
OUT=ROOT/'danika-battle-selector-state.txt'
SYMBOL='D_801BA72D'
ADDR='801BA72D'
WRITER='func_801B2D2C'
TABLE='D_801B9540'
TABLE_ADDR='801B9540'
FUNC_RE=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)')
END_RE=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
WRITE_RE=re.compile(r'\b(?:sb|sh|sw)\s+\$([A-Za-z0-9]+),\s*%lo\(D_801BA72D\)\(\$([A-Za-z0-9]+)\)',re.I)
READ_RE=re.compile(r'\b(?:lb|lbu|lh|lhu|lw)\s+\$([A-Za-z0-9]+),\s*%lo\(D_801BA72D\)\(\$([A-Za-z0-9]+)\)',re.I)
IMM_RE=re.compile(r'\b(?:addiu|ori)\s+\$([A-Za-z0-9]+),\s*\$zero,\s*(0x[0-9A-Fa-f]+|-?[0-9]+)',re.I)
CALL_WRITER_RE=re.compile(r'\bjal\s+'+re.escape(WRITER)+r'\b')
TABLE_REF_RE=re.compile(r'\b'+re.escape(TABLE)+r'\b|'+TABLE_ADDR,re.I)
DATA_LINE_RE=re.compile(r'/\*\s*[0-9A-Fa-f]+\s+([0-9A-Fa-f]{8})\s*\*/\s*\.(byte|short|word)\s+(.+?)\s*$')
HEX_RE=re.compile(r'0x([0-9A-Fa-f]+)')


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


def numbered(lines,start):
    return [(start+i,x) for i,x in enumerate(lines)]


def main():
    hits=[]; callers=[]; writer_block=None; table_refs=[]; table_data=[]
    for path in sorted(ASM_ROOT.rglob('*.s')):
        rel=path.relative_to(ROOT).as_posix()
        raw=path.read_text(encoding='utf-8',errors='replace').splitlines()
        for idx,x in enumerate(raw,start=1):
            if TABLE_REF_RE.search(x):
                table_refs.append((rel,idx,x.strip()))
            dm=DATA_LINE_RE.search(x)
            if dm:
                addr=int(dm.group(1),16)
                if 0x801B9500 <= addr <= 0x801B95A0:
                    table_data.append((rel,idx,x.strip(),addr,dm.group(2),dm.group(3)))
        for name,s,e,lines in blocks(path):
            refs=[]; writes=[]; reads=[]; wcalls=[]
            for k,x in enumerate(lines,start=s):
                if SYMBOL in x or (ADDR.lower() in x.lower() and SYMBOL not in x): refs.append((k,x.strip()))
                if WRITE_RE.search(x): writes.append((k,x.strip()))
                if READ_RE.search(x): reads.append((k,x.strip()))
                if CALL_WRITER_RE.search(x): wcalls.append((k,x.strip()))
            if refs:
                hits.append((rel,name,s,e,refs,writes,reads,lines))
            if wcalls and name!=WRITER:
                callers.append((rel,name,s,e,wcalls,lines))
            if name==WRITER:
                writer_block=(rel,name,s,e,lines)

    out=['Danika battle group selector trace','=================================',
         f'symbol={SYMBOL}',f'writer={WRITER}',f'source_table={TABLE}',
         f'selector_functions={len(hits)}',f'writer_callers={len(callers)}',f'table_refs={len(table_refs)}','',
         'Verified contract','-----------------',
         'func_801AE794 passes D_801BA72D as selector/group a0 to func_801B3D1C and slot index as a1.',
         'func_801B2D2C computes v1 = D_801B9540[s3], stores low byte(v1) to D_801BA72D,',
         'uses bit 0x8000 of v1 to choose D_801BA624, and also passes low byte(v1) to func_801ACF60.',
         '']

    out += ['Selector readers/writer','-----------------------']
    for rel,name,s,e,refs,writes,reads,lines in hits:
        score=30*len(writes)+5*len(reads)+len(refs)
        out.append(f'### score={score} {name} {rel}:{s}-{e} refs={len(refs)} writes={len(writes)} reads={len(reads)}')
        centers=sorted(set(n for n,_ in refs+writes+reads))
        for center in centers:
            lo=max(s,center-24); hi=min(e,center+30)
            out.append(f'  -- window {lo}-{hi} around {center} --')
            reg_imm={}
            for n,x in numbered(lines,s):
                if lo<=n<=hi:
                    im=IMM_RE.search(x)
                    if im: reg_imm[im.group(1).lower()]=(n,im.group(2))
                    mark=''
                    wm=WRITE_RE.search(x); rm=READ_RE.search(x)
                    if wm:
                        src=wm.group(1).lower(); mark='  # WRITE selector'
                        if src in reg_imm: mark+=f' (recent immediate {reg_imm[src][1]} at line {reg_imm[src][0]})'
                    elif rm: mark='  # READ selector'
                    elif SYMBOL in x: mark='  # selector symbol'
                    out.append(f'  {n}: {x}{mark}')
        out.append('')

    out += ['Complete selector writer context','-------------------------------']
    if writer_block:
        rel,name,s,e,lines=writer_block
        out.append(f'### {name} {rel}:{s}-{e}')
        # Full prologue and the first half of the function are most useful for resolving s3.
        hi=min(e,s+170)
        for n,x in numbered(lines,s):
            if n<=hi:
                mark=''
                if TABLE in x: mark='  # source table'
                if SYMBOL in x: mark='  # selector output'
                out.append(f'  {n}: {x}{mark}')
        out.append('')

    out += ['Direct callers of func_801B2D2C','-------------------------------']
    for rel,name,s,e,wcalls,lines in callers:
        out.append(f'### {name} {rel}:{s}-{e} calls={len(wcalls)}')
        nums=numbered(lines,s)
        for calln,_ in wcalls:
            lo=max(s,calln-55); hi=min(e,calln+45)
            out.append(f'  -- call {calln}, window {lo}-{hi} --')
            for n,x in nums:
                if lo<=n<=hi:
                    mark=''
                    if CALL_WRITER_RE.search(x): mark='  # CALL selector writer'
                    elif re.search(r'\b(?:move|addu|or)\s+\$a0\b',x): mark='  # possible a0 construction'
                    elif re.search(r'\b(?:addiu|ori)\s+\$a0\b',x): mark='  # immediate a0 construction'
                    out.append(f'  {n}: {x}{mark}')
        out.append('')

    out += ['D_801B9540 references / static neighborhood','------------------------------------------']
    for rel,idx,x in table_refs:
        out.append(f'{rel}:{idx}: {x}')
    if table_data:
        out.append('')
        out.append('Static data lines near 0x801B9540:')
        for rel,idx,x,addr,kind,vals in table_data:
            mark=''
            if addr==0x801B9540: mark='  # exact table origin'
            out.append(f'{rel}:{idx}: {x}{mark}')

    out += ['','Interpretation guardrail','------------------------',
            'A numeric selector value is named player/allied only when caller/state-table evidence proves that meaning.',
            'Until proven, class 0x71 remains vanilla outside a fail-closed context gate.',
            'The high-bit mode in D_801B9540 and the low-byte group selector are distinct semantics and must not be conflated.']
    OUT.write_text('\n'.join(out)+'\n',encoding='utf-8')
    assert hits,'selector symbol not found'
    assert writer_block,'selector writer not found'
    assert callers,'selector writer has no direct caller'
    assert table_refs,'source table has no references'
    print(f'Danika battle selector state trace: PASS (functions={len(hits)}, writer_callers={len(callers)}, table_refs={len(table_refs)})')
    print(f'report={OUT.name}')
    return 0

if __name__=='__main__': raise SystemExit(main())
