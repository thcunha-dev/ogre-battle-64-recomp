#!/usr/bin/env python3
"""Find class-driven tables outside the 0x48-byte class record.

Current evidence classifies record+0x41..+0x44 as level/class-history metadata,
not combatant graphics. This probe searches every asm function for a class byte
read from the known character structure (+0x12, with +0x11 as related class
history), then inventories non-class-table globals indexed/used nearby.

Candidates are ranked higher when the same function or its direct callers also
invoke real resource/decompression/display helpers. The scan is intentionally
broad and produces evidence, not a patch.
"""
from __future__ import annotations
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
ASM=ROOT/'asm'
OUT=ROOT/'danika-external-class-visual-tables.txt'
FUNC_RE=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)')
END_RE=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
CALL_RE=re.compile(r'\bjal\s+([A-Za-z0-9_.$]+)')
CLASS_READ_RE=re.compile(r'\blbu\s+\$([a-z0-9]+),\s*0x(?:0?12)\(\$([a-z0-9]+)\)',re.I)
RELATED_READ_RE=re.compile(r'\blbu\s+\$([a-z0-9]+),\s*0x(?:0?11)\(\$([a-z0-9]+)\)',re.I)
GLOBAL_RE=re.compile(r'\b(D_80[0-9A-Fa-f]{6})\b')

RESOURCE_FUNCS={
 'func_8009DAF4','func_8009DBB8','func_8009DD38','func_80070F30','func_800712C4',
 'func_80093060','func_801AD13C','func_801AD368'
}
MEMORY_ONLY={'func_80093380'}
CLASS_PREFIXES=('D_80187C',)


def parse_funcs():
    funcs={}
    for path in sorted(ASM.rglob('*.s')):
        if '/data/' in path.as_posix(): continue
        lines=path.read_text(encoding='utf-8',errors='replace').splitlines()
        starts={}
        for i,line in enumerate(lines):
            m=FUNC_RE.match(line)
            if m: starts[m.group(1)]=i
            e=END_RE.match(line)
            if e and e.group(1) in starts:
                name=e.group(1); a=starts[name]
                funcs[name]=(path.relative_to(ROOT),a+1,i+1,lines[a:i+1])
    return funcs


def calls(body):
    return [m.group(1) for line in body if (m:=CALL_RE.search(line))]


def globals_(body):
    return sorted(set(g for line in body for g in GLOBAL_RE.findall(line)))


def callers(funcs,target):
    pat=re.compile(rf'\bjal\s+{re.escape(target)}\b')
    out=[]
    for name,(path,start,end,body) in funcs.items():
        for off,line in enumerate(body):
            if pat.search(line): out.append((name,path,start+off))
    return out


def main():
    funcs=parse_funcs()
    rows=[]
    for name,(path,start,end,body) in funcs.items():
        class_lines=[]; related=[]
        for off,line in enumerate(body):
            if CLASS_READ_RE.search(line): class_lines.append((start+off,line))
            if RELATED_READ_RE.search(line): related.append((start+off,line))
        if not class_lines: continue
        cs=calls(body); gs=globals_(body)
        external=[g for g in gs if not g.startswith(CLASS_PREFIXES)]
        direct_resource=[c for c in cs if c in RESOURCE_FUNCS]
        caller_info=callers(funcs,name)
        caller_resource=[]
        for cn,cp,cl in caller_info:
            if cn not in funcs: continue
            ccs=calls(funcs[cn][3])
            hits=[c for c in ccs if c in RESOURCE_FUNCS]
            if hits: caller_resource.append((cn,hits))
        score=0
        score += 8*len(direct_resource)
        score += 4*len(caller_resource)
        score += min(len(external),12)
        score += 2 if related else 0
        score -= 2*sum(1 for c in cs if c in MEMORY_ONLY)
        rows.append((score,name,path,start,end,class_lines,related,external,cs,direct_resource,caller_info,caller_resource,body))
    rows.sort(key=lambda x:(-x[0],x[1]))

    report=[
      'Knight of Danika external class-table / visual candidate scan',
      '=============================================================',
      '',
      'Premise: class record +0x41..+0x44 is progression/history metadata;',
      'the normal combatant presentation is therefore expected in a separate',
      'table/path keyed by the live character class byte.',
      '',
      f'functions_with_unit_plus_0x12_class_read={len(rows)}',
      ''
    ]
    for r in rows:
        score,name,path,start,end,class_lines,related,external,cs,direct_resource,caller_info,caller_resource,body=r
        report += [f'## score={score} {name} {path}:{start}-{end}']
        report.append('class_reads='+'; '.join(f'{ln}:{txt.strip()}' for ln,txt in class_lines))
        report.append('related_plus11='+'; '.join(f'{ln}:{txt.strip()}' for ln,txt in related) if related else 'related_plus11=-')
        report.append('external_globals='+(','.join(external) if external else '-'))
        report.append('direct_resource_calls='+(','.join(direct_resource) if direct_resource else '-'))
        report.append('callees='+(','.join(cs) if cs else '-'))
        report.append('callers='+(','.join(f'{n}@{p}:{ln}' for n,p,ln in caller_info) if caller_info else '-'))
        report.append('caller_resource_adjacency='+(';'.join(f'{n}:{",".join(h)}' for n,h in caller_resource) if caller_resource else '-'))
        # Include local context around every class read so register use can be followed manually.
        for ln,_ in class_lines:
            idx=ln-start; a=max(0,idx-18); b=min(len(body),idx+50)
            report.append(f'context_around_{ln}:')
            for j in range(a,b): report.append(f'{start+j:6d}: {body[j]}')
        report.append('')

    report += [
      'Guardrail',
      '---------',
      'A candidate is actionable only after the class byte is proven to index an',
      'asset/animation resource and allied ownership is independently available.',
      'func_80093380 is memset/zero-fill and is not treated as a resource loader.'
    ]
    text='\n'.join(report)+'\n'
    OUT.write_text(text,encoding='utf-8')
    print(text)

if __name__=='__main__': main()
