#!/usr/bin/env python3
"""Dissect the strongest current world->battle bridge candidate.

func_8017B858 lives in the persistent/game-side code but directly calls battle
functions func_8019AF0C and func_8019B340.  It also touches the 80170xxx/80172xxx
subsystem that is close to known character-record users.  This report dumps the
boundary functions, their callers/callees, globals and nearby dataflow so we can
prove what arguments cross into the battle overlay.
"""
from pathlib import Path
from collections import defaultdict
import re
ROOT=Path(__file__).resolve().parents[1]; ASM=ROOT/'asm'; OUT=ROOT/'danika-battle-entry-bridge.txt'
TARGETS=('func_8017B858','func_8019AF0C','func_8019B340','func_80170814','func_80172144','func_801723B4','func_801707B4','func_80170974')
FUNC_RE=re.compile(r'^\s*glabel\s+([\w.$]+)'); END_RE=re.compile(r'^\s*endlabel\s+([\w.$]+)'); CALL_RE=re.compile(r'\bjal\s+([\w.$]+)'); GLOB_RE=re.compile(r'\b(D_80[0-9A-Fa-f]{6})\b')

def parse():
    funcs={}
    for p in sorted(ASM.rglob('*.s')):
        if '/data/' in p.as_posix(): continue
        ls=p.read_text(encoding='utf-8',errors='replace').splitlines(); st={}
        for i,l in enumerate(ls):
            if m:=FUNC_RE.match(l): st[m.group(1)]=i
            if e:=END_RE.match(l):
                n=e.group(1)
                if n in st:
                    a=st[n]; funcs[n]=(p.relative_to(ROOT),a+1,i+1,ls[a:i+1])
    rev=defaultdict(list); cm={}
    for n,(p,s,e,b) in funcs.items():
        cs=[]
        for off,l in enumerate(b):
            if m:=CALL_RE.search(l):
                c=m.group(1); cs.append(c); rev[c].append((n,p,s+off))
        cm[n]=cs
    return funcs,cm,rev

def main():
    funcs,cm,rev=parse(); r=['Knight of Danika world -> battle entry bridge','===========================================','']
    for n in TARGETS:
        r += [f'## {n}']
        if n not in funcs: r += ['NOT FOUND','']; continue
        p,s,e,b=funcs[n]; gs=sorted(set(g for l in b for g in GLOB_RE.findall(l)))
        r += [f'location={p}:{s}-{e}','callers='+(','.join(f'{x}@{y}:{z}' for x,y,z in rev.get(n,[])) or '-'),'callees='+(','.join(cm[n]) or '-'),'globals='+(','.join(gs) or '-'),'full_body:']
        r += [f'{i:6d}: {l}' for i,l in enumerate(b,start=s)]; r.append('')
    r += ['Boundary callsites inside func_8017B858','-------------------------------------']
    if 'func_8017B858' in funcs:
        p,s,e,b=funcs['func_8017B858']
        for i,l in enumerate(b,start=s):
            if any(t in l for t in ('func_8019AF0C','func_8019B340')):
                idx=i-s; r.append(f'### call line {i}: {l.strip()}')
                for j in range(max(0,idx-30),min(len(b),idx+35)): r.append(f'{s+j:6d}: {b[j]}')
    r += ['','Argument provenance checklist','-----------------------------','For each boundary call, identify the exact source of a0-a3 and stack arguments.','Promote a value as character/class provenance only if its chain reaches known','character state or a function that explicitly receives a D_80193BE0-derived pointer.']
    text='\n'.join(r)+'\n'; OUT.write_text(text,encoding='utf-8'); print(text)
if __name__=='__main__': main()
