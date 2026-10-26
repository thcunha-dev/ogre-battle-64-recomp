#!/usr/bin/env python3
"""Trace the selected-character menu path for playable Knight of Danika.

The manual Change Class UI must operate on a selected player character. Prior
work identified D_801939F4 as the selected roster index used by dynamic UI text.
This read-only tracer finds every function that references that selection state,
then ranks those that also touch roster/class data, class helpers, input/menu
state, or byte stores. It emits callers/callees and full high-signal bodies.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
ASM=ROOT/'asm'
FUNC=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)')
END=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
CALL=re.compile(r'\bjal\s+(func_[0-9A-Fa-f]+)\b')
SELECTED=re.compile(r'\bD_801939F[4-9]\b|\bD_801939F[A-Fa-f]\b')
ROSTER=re.compile(r'\bD_80193BE0\b|\bD_80193BF[12]\b')
CLASS_TABLE=re.compile(r'\bD_80187C[A-Fa-f0-9]{2}\b')
CLASS_BYTE=re.compile(r'\b(?:lbu|lb|sb)\s+[^\n]*0x12\(\$[a-z0-9]+\)',re.I)
STORE=re.compile(r'\bsb\s+')
CLASS_HELPER=re.compile(r'\bfunc_8016(?:D[0-9A-Fa-f]{3}|E[0-9A-Fa-f]{3}|F[0-9A-Fa-f]{3})\b')
INPUT_HELPER=re.compile(r'\bfunc_(?:8009|8018)[0-9A-Fa-f]{4}\b')


def blocks(path):
    lines=path.read_text(encoding='utf-8',errors='replace').splitlines(); out=[]; i=0
    while i<len(lines):
        m=FUNC.match(lines[i])
        if not m: i+=1; continue
        n=m.group(1); s=i; e=len(lines)-1
        for j in range(i+1,len(lines)):
            if END.match(lines[j]): e=j; break
            if FUNC.match(lines[j]): e=j-1; break
        out.append((n,s+1,e+1,lines[s:e+1])); i=max(e+1,i+1)
    return out


def main():
    funcs={}; callers={}
    for p in sorted(ASM.rglob('*.s')):
        try: bs=blocks(p)
        except OSError: continue
        for n,s,e,b in bs:
            t='\n'.join(b); calls=CALL.findall(t)
            funcs[n]={'p':p,'s':s,'e':e,'b':b,'t':t,'calls':calls}
            for c in calls: callers.setdefault(c,[]).append(n)

    rows=[]
    for n,f in funcs.items():
        t=f['t']; sels=sorted(set(SELECTED.findall(t)))
        if not sels: continue
        roster=bool(ROSTER.search(t)); cls=bool(CLASS_BYTE.search(t)); table=sorted(set(CLASS_TABLE.findall(t)))
        helpers=sorted(set(CLASS_HELPER.findall(t))); stores=len(STORE.findall(t)); inp=len(INPUT_HELPER.findall(t))
        score=10 + (12 if roster else 0) + (10 if cls else 0) + (8 if table else 0) + (7 if helpers else 0) + min(stores,6) + min(inp,4)
        # Text formatter is known read/display path, not a commit target.
        if n=='func_8017FC48': score-=15
        rows.append((score,n,f,sels,roster,cls,table,helpers,stores,inp))
    rows.sort(key=lambda x:(-x[0],x[1]))

    print('Knight of Danika selected-character class-menu trace')
    print('====================================================')
    print('selected_roster_index=D_801939F4')
    print('known_display_formatter=func_8017FC48')
    print('goal=find_manual Change Class list/eligibility/commit path')
    print()
    print('RANKED_SELECTED_PATHS')
    for score,n,f,sels,roster,cls,table,helpers,stores,inp in rows:
        print(f'CAND score={score:02d} {f["p"].relative_to(ROOT)}:{f["s"]}-{f["e"]} function={n} selected={",".join(sels)} roster={int(roster)} class_byte={int(cls)} table={",".join(table) or "-"} helpers={",".join(helpers) or "-"} stores={stores} inputish={inp}')
        print('  CALLERS ' + ','.join(callers.get(n,[])[:30]))
        print('  CALLEES ' + ','.join(f['calls']))
    print()

    print('HIGH_SIGNAL_BODIES')
    for score,n,f,*_ in rows:
        if score < 30: continue
        print(f'--- score={score} {n} {f["p"].relative_to(ROOT)}:{f["s"]}-{f["e"]} ---')
        print('CALLERS ' + ','.join(callers.get(n,[])[:30]))
        print('CALLEES ' + ','.join(f['calls']))
        for line in f['b']: print(line)
        print()

    # Also show one-hop sibling functions called by high-signal selected paths,
    # because menu commit logic is often factored out of the display/state node.
    sib=[]
    for score,n,f,*_ in rows:
        if score < 30: continue
        for c in f['calls']:
            if c in funcs and c not in sib: sib.append(c)
    print('HIGH_SIGNAL_CALLEE_BODIES')
    for n in sib[:40]:
        f=funcs[n]; t=f['t']
        interesting=bool(CLASS_BYTE.search(t) or ROSTER.search(t) or CLASS_TABLE.search(t) or CLASS_HELPER.search(t))
        if not interesting: continue
        print(f'--- {n} {f["p"].relative_to(ROOT)}:{f["s"]}-{f["e"]} ---')
        print('CALLERS ' + ','.join(callers.get(n,[])[:30]))
        print('CALLEES ' + ','.join(f['calls']))
        for line in f['b']: print(line)
        print()

    assert rows, 'no selected-character paths found'
    assert any(n=='func_8017FC48' for _,n,*_ in rows), 'known selected-character formatter missing'
    print(f'selected_path_count={len(rows)}')
    print('selected-character class-menu trace: PASS')

if __name__=='__main__': main()
