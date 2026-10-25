#!/usr/bin/env python3
"""Trace func_801AD6C4 argument a1 as a facing/orientation candidate.

The callback passes a1=(object+0x14 != 3).  This probe performs a lightweight
register taint within func_801AD6C4, starting from incoming $a1, and emits every
instruction whose source/destination remains tainted, plus nearby branches,
float conversions and matrix/transform calls.  The purpose is to prove whether
a1 affects facing/flip geometry strongly enough to be a safe allied/rear gate.
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ASM=ROOT/'asm/1CE040.s'
OUT=ROOT/'danika-renderer-facing-trace.txt'
TARGET='func_801AD6C4'
FUNC_RE=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)')
END_RE=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
REG_RE=re.compile(r'\$([A-Za-z0-9]+)')
CALL_RE=re.compile(r'\bjal\s+([A-Za-z0-9_.$]+)')
BRANCH_RE=re.compile(r'\b(beq|bne|beqz|bnez|beql|bnel|bltz|bgez|blez|bgtz)\b')

DEST_FIRST={'addu','addiu','subu','or','ori','and','andi','xor','xori','sll','srl','sra','slt','sltu','slti','sltiu','lui','move','lw','lh','lhu','lb','lbu','mflo','mfhi','mfc1'}
STORE_OP={'sw','sh','sb','swc1','sdc1'}


def get_block():
    lines=ASM.read_text(encoding='utf-8',errors='replace').splitlines(); start=None
    for i,x in enumerate(lines):
        m=FUNC_RE.match(x)
        if m and m.group(1)==TARGET: start=i; break
    assert start is not None
    end=min(len(lines)-1,start+5000)
    for j in range(start+1,end+1):
        em=END_RE.match(lines[j])
        if em and em.group(1)==TARGET: end=j; break
        if j>start+1 and FUNC_RE.match(lines[j]): end=j-1; break
    return start+1,end+1,lines[start:end+1]


def opcode(line):
    # strip leading disassembly comment and labels
    t=line.split('*/',1)[-1].strip() if '*/' in line else line.strip()
    if not t or t.endswith(':'): return ''
    return t.split()[0].lower()


def main():
    s,e,lines=get_block()
    tainted={'a1'}
    events=[]
    for n,x in enumerate(lines,start=s):
        op=opcode(x); regs=[r.lower() for r in REG_RE.findall(x)]
        src_tainted=any(r in tainted for r in regs)
        cm=CALL_RE.search(x)
        if src_tainted or cm or BRANCH_RE.search(x):
            events.append((n,x.strip(),sorted(set(regs)&tainted),cm.group(1) if cm else None))
        if op in DEST_FIRST and regs:
            dest=regs[0]
            # Loads overwrite dest; arithmetic/moves propagate if any source after dest is tainted.
            if op in {'lw','lh','lhu','lb','lbu','lui','mflo','mfhi','mfc1'}:
                # address dependence is meaningful for loads, except lui/mf*.
                if op in {'lw','lh','lhu','lb','lbu'} and any(r in tainted for r in regs[1:]): tainted.add(dest)
                elif dest in tainted: tainted.remove(dest)
            else:
                if any(r in tainted for r in regs[1:]): tainted.add(dest)
                elif dest in tainted: tainted.remove(dest)
        # mtc1 propagates GPR taint into FPR name for later arithmetic.
        if op=='mtc1' and len(regs)>=2 and regs[0] in tainted:
            tainted.add(regs[1])
        if op in {'mov.s','cvt.s.w','cvt.d.s','cvt.s.d','neg.s','abs.s'} and len(regs)>=2:
            if regs[1] in tainted: tainted.add(regs[0])
        if op in {'add.s','sub.s','mul.s','div.s','add.d','sub.d','mul.d','div.d'} and len(regs)>=3:
            if regs[1] in tainted or regs[2] in tainted: tainted.add(regs[0])

    out=['Danika renderer facing/orientation taint','========================================',
         f'target={TARGET}', 'seed=$a1 from callback: (object+0x14 != 3)',
         f'events={len(events)}','',
         'Tainted/control-flow events','---------------------------']
    for n,x,t,c in events:
        mark=[]
        if t: mark.append('tainted='+','.join(t))
        if c: mark.append('call='+c)
        if BRANCH_RE.search(x): mark.append('branch')
        out.append(f'{n}: {x}' + (f"  # {'; '.join(mark)}" if mark else ''))
    out += ['','Interpretation rule','-------------------',
            'a1 is accepted as a rear/front gate only if its taint reaches a geometric sign, matrix choice, coordinate reflection, or equivalent orientation behavior.',
            'If it only changes generic state/resource selection, it remains unnamed and cannot protect enemy Danika.',
            'The identity half remains descriptor+0x4F == 0x71.']
    OUT.write_text('\n'.join(out)+'\n',encoding='utf-8')
    assert events,'no a1/control-flow events found'
    print(f'Danika renderer facing trace: PASS (events={len(events)})')
    print('report='+OUT.name)
    return 0

if __name__=='__main__': raise SystemExit(main())
