#!/usr/bin/env python3
"""Correlate class-field accessors with real rendering/display-list code.

This is the next-stage scanner after fixing the true record base to D_80187C34.
It derives the class accessor -> aligned record offset map directly from
asm/40E80.s, then finds every caller across assembly and ranks callers that also
build N64 display lists or touch the global display-list pointer D_800E9BA0.

The report is evidence only. It is designed to identify which class fields can
actually influence battle visuals without guessing from the field values.
"""

from __future__ import annotations

import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
ASM = ROOT / "asm"
CLASS_CODE = ASM / "40E80.s"
TRUE_BASE = 0x80187C34
STRIDE = 0x48

GLABEL_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
CLASS_SYM_RE = re.compile(r"\b(D_80187C([0-9A-Fa-f]{2}))\b")
DL_GLOBAL = "D_800E9BA0"

# Common F3DEX/GBI command high words seen directly in this game's assembly.
# Presence is a strong renderer hint, not semantic proof of the particular asset.
DL_IMM_RE = re.compile(
    r"\b(?:0x)?(?:E700|E300|E200|D700|DA38|DB|DC|DE00|F200|F300|F500|F510|FD|FC|B[0-9A-F]{3})[0-9A-Fa-f]*\b",
    re.IGNORECASE,
)
FLOAT_RE = re.compile(r"\b(?:lwc1|swc1|add\.s|sub\.s|mul\.s|div\.s|cvt\.s|mtc1|mfc1)\b")


def asm_files():
    return sorted(ASM.rglob("*.s"))


def split_functions(path: Path):
    lines=path.read_text(encoding='utf-8',errors='replace').splitlines()
    starts=[]
    for i,line in enumerate(lines):
        m=GLABEL_RE.match(line)
        if m: starts.append((i,m.group(1)))
    for n,(s,name) in enumerate(starts):
        e=starts[n+1][0]-1 if n+1<len(starts) else len(lines)-1
        for j in range(s+1,e+1):
            m=END_RE.match(lines[j])
            if m and m.group(1)==name:
                e=j; break
        yield name,s,e,lines


def derive_accessors():
    accessors={}
    for name,s,e,lines in split_functions(CLASS_CODE):
        # The compact accessor family lives before the larger mutation/stat funcs.
        if not (name.startswith('func_8016D') or name.startswith('func_8016E')):
            continue
        text='\n'.join(lines[s:e+1])
        syms=[]
        for sym,low in CLASS_SYM_RE.findall(text):
            addr=int('80187C'+low,16)
            if TRUE_BASE <= addr < TRUE_BASE+STRIDE:
                syms.append((sym,addr-TRUE_BASE))
        # A compact accessor normally has the alias key + one target field. Keep
        # any function referencing record anchors, but label all unique offsets.
        if syms:
            uniq=sorted(set(syms),key=lambda x:x[1])
            accessors[name]=uniq
    return accessors


def main():
    accessors=derive_accessors()
    hits=[]
    all_defs={}
    for path in asm_files():
        rel=path.relative_to(ROOT).as_posix()
        for name,s,e,lines in split_functions(path):
            all_defs[name]=(rel,s,e,lines)
            text='\n'.join(lines[s:e+1])
            called=[]
            call_lines=[]
            for i in range(s,e+1):
                m=CALL_RE.search(lines[i])
                if m and m.group(1) in accessors:
                    called.append(m.group(1)); call_lines.append(i)
            if not called:
                continue
            dl_refs=text.count(DL_GLOBAL)
            dl_imms=len(DL_IMM_RE.findall(text))
            fp=len(FLOAT_RE.findall(text))
            score=len(called)*10 + min(dl_refs,20)*8 + min(dl_imms,30)*3 + min(fp,30)
            if dl_refs: score += 60
            if dl_imms >= 4: score += 30
            hits.append({
                'score':score,'name':name,'rel':rel,'s':s,'e':e,'lines':lines,
                'called':called,'call_lines':call_lines,'dl_refs':dl_refs,
                'dl_imms':dl_imms,'fp':fp,
            })
    hits.sort(key=lambda h:(-h['score'],h['rel'],h['s']))

    out=[
        'Danika class-accessor / renderer correlation',
        '=============================================',
        f'true_class_record_base=0x{TRUE_BASE:08X}',
        f'stride=0x{STRIDE:02X}',
        f'accessor_functions_derived={len(accessors)}',
        f'caller_functions={len(hits)}',
        '',
        'Derived accessor map',
        '--------------------',
    ]
    for name,fields in sorted(accessors.items(),key=lambda kv:min(x[1] for x in kv[1])):
        out.append(f"{name}: "+', '.join(f'{sym}=record+0x{off:02X}' for sym,off in fields))

    out += ['', 'Ranked accessor callers', '-----------------------']
    for rank,h in enumerate(hits,1):
        out.append(
            f"#{rank:02d} score={h['score']:4d} {h['name']} {h['rel']}:{h['s']+1}-{h['e']+1} "
            f"accessor_calls={len(h['called'])} dl_global_refs={h['dl_refs']} "
            f"dl_opcode_hints={h['dl_imms']} fp_ops={h['fp']}"
        )
        for acc in h['called']:
            fields=accessors[acc]
            out.append('  '+acc+' -> '+', '.join(f'+0x{off:02X}' for _,off in fields))
        out.append('')

    out += ['', 'Renderer-qualified accessor call contexts', '-----------------------------------------']
    qualified=[h for h in hits if h['dl_refs'] or h['dl_imms']>=4]
    out.append(f'qualified_count={len(qualified)}')
    for h in qualified:
        out.append(
            f"### {h['name']} {h['rel']}:{h['s']+1}-{h['e']+1} score={h['score']} "
            f"dl_global={h['dl_refs']} dl_hints={h['dl_imms']}"
        )
        emitted=set()
        for mark in h['call_lines']:
            lo=max(h['s'],mark-30); hi=min(h['e'],mark+55)
            for i in range(lo,hi+1):
                if i in emitted: continue
                emitted.add(i)
                out.append(f"{'>>>' if i==mark else '   '} {i+1:6d}: {h['lines'][i]}")
            out.append('')

    # Group field offsets by renderer callers to identify high-value visual fields.
    field_to_callers=defaultdict(set)
    for h in qualified:
        for acc in h['called']:
            for sym,off in accessors[acc]:
                if off == 0x45: # alias/key is control metadata, not target field
                    continue
                field_to_callers[off].add(h['name'])
    out += ['', 'Aligned class fields used from renderer-qualified callers',
            '---------------------------------------------------------']
    for off,names in sorted(field_to_callers.items()):
        out.append(f'record+0x{off:02X}: callers='+', '.join(sorted(names)))

    out += [
        '',
        'Decision rule',
        '-------------',
        'A field becomes a graphics-override candidate only when its accessor call is',
        'inside a renderer-qualified function AND downstream control/data flow shows it',
        'selects a model/sprite/animation/palette/resource. Display-list proximity alone',
        'is not enough. Allied/enemy side must still be proven before patching.',
        '',
    ]
    text='\n'.join(out)
    (ROOT/'danika-renderer-accessor-report.txt').write_text(text,encoding='utf-8')
    print(text)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
