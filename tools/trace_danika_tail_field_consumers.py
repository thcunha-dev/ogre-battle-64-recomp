#!/usr/bin/env python3
"""Trace consumers of class record tail fields +0x41..+0x46.

These fields are high-priority because playable Dragoon 0x14 and hidden Dragoon
0x9C agree on +0x41..+0x44 (= 02 06 05 11) while Knight of Danika 0x71 has
zeros there; hidden Dragoon additionally aliases playable Dragoon through
+0x45 == 0x14.

The tool inventories every direct symbol consumer across asm/, records callers
and callees, and highlights adjacency to graphics/resource loader functions.
No field semantics are assumed.
"""
from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ASM_ROOT = ROOT / "asm"
OUT = ROOT / "danika-tail-field-consumers.txt"

FIELDS = {
    "D_80187C75": 0x41,
    "D_80187C76": 0x42,
    "D_80187C77": 0x43,
    "D_80187C78": 0x44,
    "D_80187C79": 0x45,
    "D_80187C7A": 0x46,
}

LOADER_HINTS = {
    "func_8009DAF4", "func_8009DBB8", "func_8009DD38",
    "func_80070F30", "func_800712C4", "func_80093060", "func_80093380",
    "func_801AD13C", "func_801AD368",
}

FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")


def parse_functions():
    funcs = {}
    for path in sorted(ASM_ROOT.rglob("*.s")):
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
                name = e.group(1)
                a = starts[name]
                funcs[name] = (path.relative_to(ROOT), a + 1, i + 1, lines[a:i+1])
    return funcs


def calls(body):
    out=[]
    for line in body:
        m=CALL_RE.search(line)
        if m: out.append(m.group(1))
    return out


def callers(funcs, target):
    out=[]
    pat=re.compile(rf"\bjal\s+{re.escape(target)}\b")
    for name,(path,start,end,body) in funcs.items():
        for off,line in enumerate(body):
            if pat.search(line):
                out.append((name,path,start+off))
    return out


def refs_in(body):
    return [sym for sym in FIELDS if any(sym in line for line in body)]


def main():
    funcs=parse_functions()
    report=[
        "Knight of Danika class tail-field consumer trace",
        "===============================================",
        "",
        "Observed class-tail values",
        "--------------------------",
        "field  Dragoon14 Danika71 HiddenDragoon9C",
        "+41    02        00       02",
        "+42    06        00       06",
        "+43    05        00       05",
        "+44    11        00       11",
        "+45    00        00       14",
        "+46    FF        03       04",
        "",
        "No semantics are inferred merely from these values.",
        "",
    ]

    consumers=[]
    for name,(path,start,end,body) in funcs.items():
        refs=refs_in(body)
        if refs:
            cs=calls(body)
            consumers.append((name,path,start,end,refs,cs,body))

    report += ["Consumer summary", "----------------"]
    report.append(f"functions={len(consumers)}")
    for name,path,start,end,refs,cs,body in consumers:
        near=[c for c in cs if c in LOADER_HINTS]
        report.append(
            f"{name} {path}:{start}-{end} refs=" +
            ",".join(f"{s}(+0x{FIELDS[s]:02X})" for s in refs) +
            f" calls={','.join(cs) if cs else '-'} loader_like={','.join(near) if near else '-'}"
        )
    report.append("")

    for sym,off in FIELDS.items():
        report += [f"## {sym} / record+0x{off:02X}", ""]
        matched=[x for x in consumers if sym in x[4]]
        report.append(f"direct_consumer_count={len(matched)}")
        for name,path,start,end,refs,cs,body in matched:
            report.append(f"### {name} {path}:{start}-{end}")
            report.append("callers=" + (",".join(f"{n}@{p}:{ln}" for n,p,ln in callers(funcs,name)) or "-"))
            report.append("callees=" + (",".join(cs) or "-"))
            for i,line in enumerate(body,start=start):
                if sym in line:
                    a=max(start,i-12); b=min(end,i+12)
                    report.append(f"reference_line={i}")
                    for j in range(a,b+1):
                        report.append(f"{j:6d}: {body[j-start]}")
            report.append("")

    report += ["Two-hop loader adjacency", "------------------------"]
    direct_names={x[0] for x in consumers}
    neighborhood=set(direct_names)
    for name in list(direct_names):
        for caller,_,_ in callers(funcs,name): neighborhood.add(caller)
        if name in funcs:
            neighborhood.update(calls(funcs[name][3]))
    hits=0
    for name in sorted(neighborhood):
        if name not in funcs: continue
        path,start,end,body=funcs[name]
        cs=calls(body)
        near=[c for c in cs if c in LOADER_HINTS]
        refs=refs_in(body)
        if near:
            hits+=1
            report.append(f"{name} {path}:{start}-{end} refs={','.join(refs) or '-'} -> {','.join(near)}")
    report.append(f"loader_adjacency_hits={hits}")
    report.append("")
    report += [
        "Safety rule",
        "-----------",
        "Do not copy Dragoon tail fields into Danika until each consumed field is",
        "classified. Mixed gameplay/UI/graphics semantics require a narrower hook.",
    ]

    text="\n".join(report)+"\n"
    OUT.write_text(text,encoding="utf-8")
    print(text)

if __name__ == "__main__":
    main()
