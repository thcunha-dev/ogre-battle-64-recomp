#!/usr/bin/env python3
"""Trace battle-object class identity fields +0x4B/+0x4F.

Renderer func_801AD6C4 proves that a battle/render object reachable through
s0+0x34 carries two class selectors at offsets 0x4B and 0x4F.  It feeds them to
the class accessor for aligned record+0x04.  That particular use is scale-related,
but these object fields are now strong anchors for finding the real visual asset
selection path.  This scanner finds every reader/writer and ranks contexts with
render/display-list, DMA/resource, or allocation signals.
"""

from __future__ import annotations
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ASM=ROOT/'asm'
GLABEL_RE=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)')
END_RE=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
CALL_RE=re.compile(r'\bjal\s+([A-Za-z0-9_.$]+)')
# Capture load/store, register, offset and base register.
MEM_RE=re.compile(r'\b(lbu|lb|lhu|lh|lw|sb|sh|sw)\s+\$([A-Za-z0-9]+),\s*0x(4B|4F)\(\$([A-Za-z0-9]+)\)',re.I)
DL_RE=re.compile(r'\b(?:D_800E9BA0|0x(?:E700|E300|E200|DA38|DE00|F[0-9A-F]{3})[0-9A-Fa-f]*)\b',re.I)
RESOURCE_RE=re.compile(r'\b(?:DMA|decomp|texture|sprite|anim|palette|model|segment|asset|resource)\b',re.I)


def files(): return sorted(ASM.rglob('*.s'))

def funcs(path):
    lines=path.read_text(encoding='utf-8',errors='replace').splitlines(); starts=[]
    for i,l in enumerate(lines):
        m=GLABEL_RE.match(l)
        if m: starts.append((i,m.group(1)))
    for n,(s,name) in enumerate(starts):
        e=starts[n+1][0]-1 if n+1<len(starts) else len(lines)-1
        for j in range(s+1,e+1):
            m=END_RE.match(lines[j])
            if m and m.group(1)==name: e=j; break
        yield name,s,e,lines

def main():
    hits=[]
    for path in files():
        rel=path.relative_to(ROOT).as_posix()
        for name,s,e,lines in funcs(path):
            mem=[]
            for i in range(s,e+1):
                m=MEM_RE.search(lines[i])
                if m: mem.append((i,m.groups()))
            if not mem: continue
            text='\n'.join(lines[s:e+1])
            offsets={g[2].upper() for _,g in mem}
            reads=sum(1 for _,g in mem if g[0].lower() in {'lbu','lb','lhu','lh','lw'})
            writes=len(mem)-reads
            same_base_pairs=0
            bases={}
            for _,g in mem:
                bases.setdefault(g[3].lower(),set()).add(g[2].upper())
            same_base_pairs=sum(1 for offs in bases.values() if {'4B','4F'}<=offs)
            dl=len(DL_RE.findall(text)); res=len(RESOURCE_RE.findall(text)); calls=CALL_RE.findall(text)
            score=reads*8+writes*5+same_base_pairs*30+min(dl,50)*3+min(res,20)*4+min(len(calls),30)
            if {'4B','4F'}<=offsets: score+=40
            hits.append(dict(score=score,name=name,s=s,e=e,lines=lines,rel=rel,mem=mem,reads=reads,writes=writes,pairs=same_base_pairs,dl=dl,res=res,calls=calls,bases=bases))
    hits.sort(key=lambda h:(-h['score'],h['rel'],h['s']))
    out=['Danika battle-object class field trace','======================================',
         'anchors=object+0x4B and object+0x4F (proven class selectors in func_801AD6C4)','',
         f'functions_with_anchor_access={len(hits)}','', 'Ranked functions','----------------']
    for rank,h in enumerate(hits,1):
        out.append(f"#{rank:02d} score={h['score']:4d} {h['name']} {h['rel']}:{h['s']+1}-{h['e']+1} reads={h['reads']} writes={h['writes']} same_base_pairs={h['pairs']} dl_hints={h['dl']} resource_terms={h['res']} calls={len(h['calls'])}")
        out.append('  jal_targets='+', '.join(sorted(set(h['calls']))[:30]))
        for base,offs in sorted(h['bases'].items()): out.append(f"  base=${base}: offsets={','.join(sorted(offs))}")
        out.append('')
    out += ['Detailed anchor contexts','------------------------']
    for h in hits:
        out.append(f"### {h['name']} {h['rel']}:{h['s']+1}-{h['e']+1} score={h['score']}")
        emitted=set()
        for mark,_ in h['mem']:
            lo=max(h['s'],mark-28); hi=min(h['e'],mark+45)
            for i in range(lo,hi+1):
                if i in emitted: continue
                emitted.add(i)
                out.append(f"{'>>>' if i==mark else '   '} {i+1:6d}: {h['lines'][i]}")
            out.append('')
    out += ['', 'Interpretation guardrail','------------------------',
            'Reads of +0x4B/+0x4F are high-value because a real renderer already proves',
            'they carry class selectors. A function is not an asset selector merely for',
            'reading them: downstream data must feed a ROM/DMA/decompression/model/sprite/',
            'animation/palette lookup, and allied/enemy orientation must still be proven.','']
    text='\n'.join(out); (ROOT/'danika-battle-object-class-report.txt').write_text(text,encoding='utf-8'); print(text)
    return 0
if __name__=='__main__': raise SystemExit(main())
