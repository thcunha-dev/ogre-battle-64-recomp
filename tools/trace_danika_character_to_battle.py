#!/usr/bin/env python3
"""Trace known live character records into battle participant structures.

This deliberately avoids searching arbitrary +0x12 offsets.  D_80193BE0 is a
known character-record array (0x38-byte stride) whose +0x12 byte is the class.
The goal is to find functions that derive pointers into that array, consume the
class byte, and then cross toward battle/overlay state or copy character data
into another structure.  The destination of such a copy becomes the strongest
candidate for the real battle-participant class field.

This tool is evidence-only; it never patches the game.
"""
from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ASM = ROOT / "asm"
OUT = ROOT / "danika-character-to-battle.txt"
SOURCE = "D_80193BE0"

FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
GLOBAL_RE = re.compile(r"\b(D_80[0-9A-Fa-f]{6})\b")
CLASS_READ = re.compile(r"\blbu\s+\$([a-z0-9]+),\s*0x0*12\(\$([a-z0-9]+)\)", re.I)
PAIR_READ = re.compile(r"\blbu\s+\$([a-z0-9]+),\s*0x0*11\(\$([a-z0-9]+)\)", re.I)
STRIDE38 = re.compile(r"0x38|56\b", re.I)

# Functions/globals in the battle overlay tend to live in these ranges/names.
BATTLE_FUNC_RE = re.compile(r"func_801(?:9|A|B)[0-9A-Fa-f]{4}")
BATTLE_GLOBAL_RE = re.compile(r"D_801B[0-9A-Fa-f]{4}")
RESOURCE_FUNCS = {
    "func_8009DAF4", "func_8009DBB8", "func_8009DD38",
    "func_801AD13C", "func_801AD368",
}
COPY_FUNCS = {"func_80093060"}  # proven memcpy


def parse_funcs():
    funcs = {}
    for path in sorted(ASM.rglob("*.s")):
        if "/data/" in path.as_posix():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        starts = {}
        for i, line in enumerate(lines):
            m = FUNC_RE.match(line)
            if m:
                starts[m.group(1)] = i
            e = END_RE.match(line)
            if e and e.group(1) in starts:
                name = e.group(1); a = starts[name]
                funcs[name] = (path.relative_to(ROOT), a + 1, i + 1, lines[a:i+1])
    return funcs


def calls(body):
    return [m.group(1) for line in body if (m := CALL_RE.search(line))]


def globals_(body):
    return sorted(set(g for line in body for g in GLOBAL_RE.findall(line)))


def callers(funcs, target):
    pat = re.compile(rf"\bjal\s+{re.escape(target)}\b")
    out = []
    for name, (path, start, end, body) in funcs.items():
        for off, line in enumerate(body):
            if pat.search(line):
                out.append((name, path, start + off))
    return out


def direct_source_refs(funcs):
    rows = []
    for name, (path, start, end, body) in funcs.items():
        ref_lines = [(start+i, line) for i, line in enumerate(body) if SOURCE in line]
        if not ref_lines:
            continue
        cs = calls(body); gs = globals_(body)
        battle_calls = [c for c in cs if BATTLE_FUNC_RE.fullmatch(c)]
        battle_globals = [g for g in gs if BATTLE_GLOBAL_RE.fullmatch(g)]
        resource = [c for c in cs if c in RESOURCE_FUNCS]
        copies = [c for c in cs if c in COPY_FUNCS]
        class_reads = [(start+i, line) for i,line in enumerate(body) if CLASS_READ.search(line)]
        pair_reads = [(start+i, line) for i,line in enumerate(body) if PAIR_READ.search(line)]
        stride_hits = sum(1 for line in body if STRIDE38.search(line))
        score = 12*len(class_reads) + 5*len(pair_reads) + 5*len(battle_calls) + 4*len(battle_globals) + 4*len(resource) + 3*len(copies) + min(stride_hits, 5)
        rows.append((score,name,path,start,end,body,ref_lines,class_reads,pair_reads,battle_calls,battle_globals,resource,copies,gs,cs))
    return sorted(rows, key=lambda r:(-r[0], r[1]))


def expand_neighborhood(funcs, seeds, depth=3):
    graph = {}
    frontier = set(seeds)
    seen = set(seeds)
    for d in range(1, depth+1):
        nxt = set()
        for target in sorted(frontier):
            outs = []
            if target in funcs:
                for c in calls(funcs[target][3]):
                    if c in funcs:
                        outs.append(("callee", c))
                        if c not in seen: nxt.add(c)
            for c,_,_ in callers(funcs,target):
                outs.append(("caller", c))
                if c not in seen: nxt.add(c)
            graph[(d,target)] = outs
        seen.update(nxt); frontier = nxt
    return graph, seen


def classify_neighbor(funcs, name):
    if name not in funcs: return (0, [], [], [])
    path,start,end,body=funcs[name]
    cs=calls(body); gs=globals_(body)
    battle_calls=[c for c in cs if BATTLE_FUNC_RE.fullmatch(c)]
    battle_globals=[g for g in gs if BATTLE_GLOBAL_RE.fullmatch(g)]
    resource=[c for c in cs if c in RESOURCE_FUNCS]
    class_reads=[(start+i,line) for i,line in enumerate(body) if CLASS_READ.search(line)]
    score=6*len(battle_calls)+5*len(battle_globals)+8*len(resource)+8*len(class_reads)
    return score,battle_calls,battle_globals,resource


def main():
    funcs=parse_funcs()
    rows=direct_source_refs(funcs)
    seeds=[r[1] for r in rows]
    graph, neighborhood=expand_neighborhood(funcs,seeds,3)

    report=[
        "Knight of Danika live-character -> battle bridge trace",
        "======================================================",
        "",
        f"known_character_array={SOURCE}",
        "record_stride=0x38",
        "known_class_offset=+0x12",
        "related_class/history_offset=+0x11",
        "",
        f"direct_functions_referencing_source={len(rows)}",
        "",
    ]

    for r in rows:
        score,name,path,start,end,body,refs,cr,pr,bc,bg,res,copies,gs,cs=r
        report += [f"## score={score} {name} {path}:{start}-{end}"]
        report.append("source_refs="+'; '.join(f'{ln}:{line.strip()}' for ln,line in refs))
        report.append("class_reads="+(' ; '.join(f'{ln}:{line.strip()}' for ln,line in cr) if cr else '-'))
        report.append("plus11_reads="+(' ; '.join(f'{ln}:{line.strip()}' for ln,line in pr) if pr else '-'))
        report.append("battle_calls="+(','.join(bc) if bc else '-'))
        report.append("battle_globals="+(','.join(bg) if bg else '-'))
        report.append("resource_calls="+(','.join(res) if res else '-'))
        report.append("copy_calls="+(','.join(copies) if copies else '-'))
        report.append("callees="+(','.join(cs) if cs else '-'))
        report.append("callers="+(','.join(f'{n}@{p}:{ln}' for n,p,ln in callers(funcs,name)) or '-'))
        # Full body for high-value direct provenance. These functions are usually compact.
        report.append("full_body:")
        for i,line in enumerate(body,start=start): report.append(f"{i:6d}: {line}")
        report.append("")

    report += ["Three-hop bridge candidates", "---------------------------"]
    ranked=[]
    for name in neighborhood:
        if name in seeds: continue
        score,bc,bg,res=classify_neighbor(funcs,name)
        if score:
            ranked.append((score,name,bc,bg,res))
    ranked.sort(key=lambda x:(-x[0],x[1]))
    for score,name,bc,bg,res in ranked:
        path,start,end,body=funcs[name]
        report.append(f"score={score:3d} {name} {path}:{start}-{end} battle_calls={','.join(bc) or '-'} battle_globals={','.join(bg) or '-'} resource={','.join(res) or '-'}")
    report.append("")

    report += ["Call graph from direct source users", "-----------------------------------"]
    for (depth,target),edges in sorted(graph.items()):
        report.append(f"depth={depth} target={target}")
        for kind,node in edges: report.append(f"  {kind}: {node}")
    report.append("")

    # Specifically inventory stores near class reads in source-proven functions.
    report += ["Class-read local dataflow windows", "---------------------------------"]
    for r in rows:
        _,name,path,start,end,body,refs,cr,*_=r
        for ln,line in cr:
            idx=ln-start
            report.append(f"### {name} {path}:{ln}")
            for j in range(max(0,idx-20),min(len(body),idx+70)):
                report.append(f"{start+j:6d}: {body[j]}")
    report.append("")

    report += [
        "Acceptance criterion",
        "--------------------",
        "The next field is promoted to 'battle participant class' only if a value",
        "proven to originate from D_80193BE0+record+0x12 is copied/stored into a",
        "battle-owned structure and later consumed by battle setup/render/resource",
        "code. Arbitrary +0x12 offsets remain excluded.",
    ]

    text='\n'.join(report)+'\n'
    OUT.write_text(text,encoding='utf-8')
    print(text)

if __name__=='__main__':
    main()
