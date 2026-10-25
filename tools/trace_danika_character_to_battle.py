#!/usr/bin/env python3
"""Trace known live character records into battle participant structures.

D_80193BE0 is the known 0x38-byte character-record array; +0x12 is class.
This version pre-indexes the call graph so bridge discovery remains fast even
when the assembly grows. Evidence only: no game patch is emitted.
"""
from __future__ import annotations
from pathlib import Path
from collections import defaultdict
import re

ROOT=Path(__file__).resolve().parents[1]
ASM=ROOT/'asm'
OUT=ROOT/'danika-character-to-battle.txt'
SOURCE='D_80193BE0'
FUNC_RE=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)')
END_RE=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
CALL_RE=re.compile(r'\bjal\s+([A-Za-z0-9_.$]+)')
GLOBAL_RE=re.compile(r'\b(D_80[0-9A-Fa-f]{6})\b')
CLASS_READ=re.compile(r'\blbu\s+\$[a-z0-9]+,\s*0x0*12\(\$[a-z0-9]+\)',re.I)
PAIR_READ=re.compile(r'\blbu\s+\$[a-z0-9]+,\s*0x0*11\(\$[a-z0-9]+\)',re.I)
BATTLE_FUNC_RE=re.compile(r'func_801(?:9|A|B)[0-9A-Fa-f]{4}')
BATTLE_GLOBAL_RE=re.compile(r'D_801B[0-9A-Fa-f]{4}')
RESOURCE_FUNCS={'func_8009DAF4','func_8009DBB8','func_8009DD38','func_801AD13C','func_801AD368'}
COPY_FUNCS={'func_80093060'}


def parse():
    funcs={}; callee_map={}; reverse=defaultdict(list)
    for path in sorted(ASM.rglob('*.s')):
        if '/data/' in path.as_posix(): continue
        lines=path.read_text(encoding='utf-8',errors='replace').splitlines(); starts={}
        for i,line in enumerate(lines):
            m=FUNC_RE.match(line)
            if m: starts[m.group(1)]=i
            e=END_RE.match(line)
            if e and e.group(1) in starts:
                n=e.group(1); a=starts[n]; body=lines[a:i+1]
                funcs[n]=(path.relative_to(ROOT),a+1,i+1,body)
    for n,(p,s,e,b) in funcs.items():
        cs=[]
        for off,line in enumerate(b):
            if m:=CALL_RE.search(line):
                c=m.group(1); cs.append(c); reverse[c].append((n,p,s+off))
        callee_map[n]=cs
    return funcs,callee_map,reverse


def globs(body): return sorted(set(g for l in body for g in GLOBAL_RE.findall(l)))


def classify(funcs,callee_map,name):
    if name not in funcs: return (0,[],[],[],[])
    p,s,e,b=funcs[name]; cs=callee_map[name]; gs=globs(b)
    bc=[c for c in cs if BATTLE_FUNC_RE.fullmatch(c)]
    bg=[g for g in gs if BATTLE_GLOBAL_RE.fullmatch(g)]
    rs=[c for c in cs if c in RESOURCE_FUNCS]
    cr=[(s+i,l) for i,l in enumerate(b) if CLASS_READ.search(l)]
    score=6*len(bc)+5*len(bg)+8*len(rs)+8*len(cr)
    return score,bc,bg,rs,cr


def main():
    funcs,callee_map,reverse=parse(); rows=[]
    for n,(p,s,e,b) in funcs.items():
        refs=[(s+i,l) for i,l in enumerate(b) if SOURCE in l]
        if not refs: continue
        gs=globs(b); cs=callee_map[n]
        cr=[(s+i,l) for i,l in enumerate(b) if CLASS_READ.search(l)]
        pr=[(s+i,l) for i,l in enumerate(b) if PAIR_READ.search(l)]
        bc=[c for c in cs if BATTLE_FUNC_RE.fullmatch(c)]
        bg=[g for g in gs if BATTLE_GLOBAL_RE.fullmatch(g)]
        rs=[c for c in cs if c in RESOURCE_FUNCS]; cp=[c for c in cs if c in COPY_FUNCS]
        score=12*len(cr)+5*len(pr)+5*len(bc)+4*len(bg)+4*len(rs)+3*len(cp)
        rows.append((score,n,p,s,e,b,refs,cr,pr,bc,bg,rs,cp,cs))
    rows.sort(key=lambda x:(-x[0],x[1])); seeds={r[1] for r in rows}

    graph=[]; seen=set(seeds); frontier=set(seeds)
    for depth in range(1,4):
        nxt=set()
        for n in sorted(frontier):
            edges=[]
            for c in callee_map.get(n,[]):
                if c in funcs:
                    edges.append(('callee',c));
                    if c not in seen: nxt.add(c)
            for caller,_,_ in reverse.get(n,[]):
                edges.append(('caller',caller));
                if caller not in seen: nxt.add(caller)
            graph.append((depth,n,edges))
        seen.update(nxt); frontier=nxt

    report=['Knight of Danika live-character -> battle bridge trace','======================================================','',f'known_character_array={SOURCE}','record_stride=0x38','known_class_offset=+0x12','related_class/history_offset=+0x11','',f'direct_functions_referencing_source={len(rows)}','']
    for r in rows:
        score,n,p,s,e,b,refs,cr,pr,bc,bg,rs,cp,cs=r
        report += [f'## score={score} {n} {p}:{s}-{e}',
                   'source_refs='+'; '.join(f'{ln}:{l.strip()}' for ln,l in refs),
                   'class_reads='+(' ; '.join(f'{ln}:{l.strip()}' for ln,l in cr) if cr else '-'),
                   'plus11_reads='+(' ; '.join(f'{ln}:{l.strip()}' for ln,l in pr) if pr else '-'),
                   'battle_calls='+(','.join(bc) or '-'),'battle_globals='+(','.join(bg) or '-'),
                   'resource_calls='+(','.join(rs) or '-'),'copy_calls='+(','.join(cp) or '-'),
                   'callees='+(','.join(cs) or '-'),
                   'callers='+(','.join(f'{x}@{y}:{z}' for x,y,z in reverse.get(n,[])) or '-'),'full_body:']
        report += [f'{i:6d}: {l}' for i,l in enumerate(b,start=s)]; report.append('')

    report += ['Three-hop bridge candidates','---------------------------']
    ranked=[]
    for n in seen-seeds:
        score,bc,bg,rs,cr=classify(funcs,callee_map,n)
        if score: ranked.append((score,n,bc,bg,rs,cr))
    ranked.sort(key=lambda x:(-x[0],x[1]))
    for score,n,bc,bg,rs,cr in ranked:
        p,s,e,_=funcs[n]
        report.append(f'score={score:3d} {n} {p}:{s}-{e} battle_calls={",".join(bc) or "-"} battle_globals={",".join(bg) or "-"} resource={",".join(rs) or "-"} class_reads={len(cr)}')
    report += ['','Call graph from direct source users','-----------------------------------']
    for depth,n,edges in graph:
        report.append(f'depth={depth} target={n}')
        report += [f'  {k}: {v}' for k,v in edges]

    report += ['','Class-read local dataflow windows','---------------------------------']
    for r in rows:
        _,n,p,s,e,b,_,cr,*_=r
        for ln,_ in cr:
            idx=ln-s; report.append(f'### {n} {p}:{ln}')
            for j in range(max(0,idx-20),min(len(b),idx+70)): report.append(f'{s+j:6d}: {b[j]}')
    report += ['','Acceptance criterion','--------------------','Promote a field to battle-participant class only when a value proven to originate','from D_80193BE0+record+0x12 is stored/copied into battle-owned state and later','consumed by battle setup/render/resource code. Arbitrary +0x12 hits remain excluded.']
    text='\n'.join(report)+'\n'; OUT.write_text(text,encoding='utf-8'); print(text)

if __name__=='__main__': main()
