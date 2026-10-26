#!/usr/bin/env python3
"""Find the player-roster -> native class-menu bridge for playable Danika.

A real Change Class path must eventually operate on a player character and
consult class metadata. This read-only tracer ranks assembly functions by
roster/global refs, character +0x12 class-byte access, class-table refs/helpers,
and call-graph proximity, then emits the strongest menu-family bodies.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
ASM=ROOT/'asm'
FUNC=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)')
END=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
CALL=re.compile(r'\bjal\s+(func_[0-9A-Fa-f]+)\b')
ROSTER=re.compile(r'\bD_80193(?:BE0|[A-Fa-f0-9]{3})\b')
CLASS_TABLE=re.compile(r'\bD_80187C[A-Fa-f0-9]{2}\b')
CLASS_BYTE=re.compile(r'\b(?:lbu|lb|sb)\s+[^\n]*0x12\(\$[a-z0-9]+\)',re.I)
CLASS_HELPER=re.compile(r'\bfunc_8016(?:D[0-9A-Fa-f]{3}|E[0-9A-Fa-f]{3}|F[0-9A-Fa-f]{3})\b')
FOCUS=[
 'func_80170974','func_80171BB4','func_80171EF8','func_80172A48','func_801730DC',
 'func_8016BA6C','func_8016B774','func_8016B198','func_8016AF90',
 'func_8017FC48','func_801805F0','func_80180814'
]


def blocks(path):
    lines=path.read_text(encoding='utf-8',errors='replace').splitlines(); out=[]; i=0
    while i<len(lines):
        m=FUNC.match(lines[i])
        if not m: i+=1; continue
        name=m.group(1); s=i; e=len(lines)-1
        for j in range(i+1,len(lines)):
            if END.match(lines[j]): e=j; break
            if FUNC.match(lines[j]): e=j-1; break
        out.append((name,s+1,e+1,lines[s:e+1])); i=max(e+1,i+1)
    return out


def main():
    funcs={}; callers={}
    for p in sorted(ASM.rglob('*.s')):
        try: bs=blocks(p)
        except OSError: continue
        for name,s,e,body in bs:
            text='\n'.join(body); calls=CALL.findall(text)
            funcs[name]={
                'path':p,'s':s,'e':e,'body':body,'text':text,'calls':calls,
                'roster':sorted(set(ROSTER.findall(text))),
                'class_syms':sorted(set(CLASS_TABLE.findall(text))),
                'class_byte':bool(CLASS_BYTE.search(text)),
                'helpers':sorted(set(CLASS_HELPER.findall(text))),
            }
            for c in calls: callers.setdefault(c,[]).append(name)

    direct=[]
    for name,f in funcs.items():
        score=0
        if 'D_80193BE0' in f['roster']: score+=12
        elif f['roster']: score+=5
        if f['class_syms']: score+=10
        if f['class_byte']: score+=8
        if f['helpers']: score+=5
        direct.append((score,name,f))
    direct.sort(key=lambda x:(-x[0],x[1]))

    bridges=[]
    for name,f in funcs.items():
        roster_side=bool(f['roster']) or f['class_byte']
        if not roster_side: continue
        for c in f['calls']:
            cf=funcs.get(c)
            if not cf: continue
            if cf['class_syms'] or cf['helpers']:
                bridges.append((name,c,'direct'))
            for c2 in cf['calls']:
                c2f=funcs.get(c2)
                if c2f and (c2f['class_syms'] or c2f['helpers']):
                    bridges.append((name,c2,'two-hop'))

    print('Knight of Danika roster -> native class-menu bridge trace')
    print('========================================================')
    print('player_roster_base=D_80193BE0')
    print('character_class_field=+0x12')
    print('class_table_family=D_80187Cxx')
    print()
    print('BRIDGES')
    seen=set()
    for src,dst,kind in bridges:
        key=(src,dst,kind)
        if key in seen: continue
        seen.add(key)
        sf,df=funcs[src],funcs[dst]
        print(f'BRIDGE {kind} {src} -> {dst} src={sf["path"].relative_to(ROOT)}:{sf["s"]}-{sf["e"]} dst={df["path"].relative_to(ROOT)}:{df["s"]}-{df["e"]}')
    print()

    print('RANKED_DIRECT_CANDIDATES')
    for score,name,f in direct[:80]:
        if score<=0: break
        print(f'CAND score={score:02d} {f["path"].relative_to(ROOT)}:{f["s"]}-{f["e"]} function={name} roster={",".join(f["roster"]) or "-"} class_byte={int(f["class_byte"])} class_syms={",".join(f["class_syms"]) or "-"} helpers={",".join(f["helpers"]) or "-"}')
    print()

    print('FOCUSED_MENU_FAMILY')
    for name in FOCUS:
        f=funcs.get(name)
        if not f:
            print(f'--- {name} MISSING ---')
            continue
        print(f'--- {name} {f["path"].relative_to(ROOT)}:{f["s"]}-{f["e"]} ---')
        print('CALLERS ' + ','.join(callers.get(name,[])[:30]))
        print('CALLEES ' + ','.join(f['calls']))
        print(f'META roster={",".join(f["roster"]) or "-"} class_byte={int(f["class_byte"])} class_syms={",".join(f["class_syms"]) or "-"} helpers={",".join(f["helpers"]) or "-"}')
        for line in f['body']: print(line)
        print()

    assert all(n in funcs for n in FOCUS)
    assert any('D_80193BE0' in f['roster'] for f in funcs.values())
    assert any(f['class_syms'] for f in funcs.values())
    print(f'bridge_count={len(seen)}')
    print('roster-menu bridge trace: PASS')

if __name__=='__main__': main()
