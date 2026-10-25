#!/usr/bin/env python3
"""Deep-trace the strongest non-text Knight of Danika graphics-path candidates.

The broad scanner identified a small set of unit/class readers worth inspecting.
This tool emits complete bodies, callers, callees, and nearby data/global usage for
those candidates so we can prove or reject them without guessing from addresses.
"""

from __future__ import annotations

import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
ASM = ROOT / "asm"

# Strongest non-text candidates from the first broad scan.  8016EBC4 and
# 8016F13C sit next to the proven class accessor family and read unit class-like
# fields. The 1CE040 functions are high-density unit readers from a different
# subsystem and are included to avoid tunnel vision.
FOCUS = [
    "func_8016EBC4",
    "func_8016F13C",
    "func_8019F928",
    "func_801B28F8",
    "func_8019FC68",
    "func_801AD6C4",
]

# First-hop callees of the strongest two functions, plus helpers shared by the
# 1CE040 candidates. Their bodies/callers can reveal whether this is UI/text,
# save/state, battle setup, renderer preparation, decompression, or asset IO.
FIRST_HOP = {
    "func_8009C7CC",
    "func_8016F904", "func_8016F940", "func_8016F960", "func_8016F97C",
    "func_8016F998", "func_8016F9B8", "func_8016F9D8",
    "func_8016F634",
    "func_80093380", "func_8009C970", "func_8019B198",
    "func_80092A90", "func_800988A0", "func_80098AA0", "func_8009DF48",
    "func_80197B90", "func_80197BE4", "func_80197C94", "func_8019ABC4",
    "func_8019B074", "func_801AD558", "func_801B3920", "func_801B3E14",
    "func_801B3F2C", "func_8016DE3C",
}

START_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
GLOBAL_RE = re.compile(r"\b(D_[0-9A-Fa-f]{8})\b")
ADDR_RE = re.compile(r"/\*\s+[0-9A-Fa-f]+\s+([0-9A-Fa-f]{8})\s+[0-9A-Fa-f]{8}\s*\*/")
CLASS_LOAD_RE = re.compile(r"\b(?:lbu|lb|lhu|lh)\s+\$[A-Za-z0-9]+,\s*0x(?:11|12|1A)\(")


def files():
    return sorted(ASM.rglob("*.s"))


def split(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    starts = []
    for i, line in enumerate(lines):
        m = START_RE.match(line)
        if m:
            starts.append((i, m.group(1)))
    for n, (s, name) in enumerate(starts):
        e = starts[n+1][0]-1 if n+1 < len(starts) else len(lines)-1
        for j in range(s+1, e+1):
            m = END_RE.match(lines[j])
            if m and m.group(1) == name:
                e = j
                break
        yield name, s, e, lines


def index_functions():
    defs = {}
    callers = defaultdict(list)
    for path in files():
        rel = path.relative_to(ROOT).as_posix()
        for name, s, e, lines in split(path):
            defs[name] = (rel, s, e, lines)
            for i in range(s, e+1):
                m = CALL_RE.search(lines[i])
                if m:
                    callers[m.group(1)].append((name, rel, i))
    return defs, callers


def emit_body(out, title, entry, marks=None, limit=None):
    rel, s, e, lines = entry
    out += [f"### {title} {rel}:{s+1}-{e+1}"]
    marks = marks or set()
    lo, hi = s, e
    if limit and e-s+1 > limit:
        # Complete head/tail plus all marked regions for very large functions.
        ranges = [(s, min(e, s+120)), (max(s, e-120), e)]
        for m in sorted(marks):
            ranges.append((max(s, m-30), min(e, m+45)))
        merged=[]
        for a,b in sorted(ranges):
            if merged and a <= merged[-1][1]+1:
                merged[-1]=(merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a,b))
        prev=None
        for a,b in merged:
            if prev is not None and a > prev+1:
                out.append("   ...")
            for i in range(a,b+1):
                out.append(f"{'>>>' if i in marks else '   '} {i+1:6d}: {lines[i]}")
            prev=b
    else:
        for i in range(lo, hi+1):
            out.append(f"{'>>>' if i in marks else '   '} {i+1:6d}: {lines[i]}")
    out.append("")


def summarize(name, entry, callers):
    rel,s,e,lines=entry
    body="\n".join(lines[s:e+1])
    calls=CALL_RE.findall(body)
    globals_=GLOBAL_RE.findall(body)
    class_lines=[i for i in range(s,e+1) if CLASS_LOAD_RE.search(lines[i])]
    return {
        "name":name,"rel":rel,"s":s,"e":e,
        "calls":calls,"globals":globals_,"class_lines":class_lines,
        "incoming":callers.get(name,[]),
    }


def main():
    defs, callers = index_functions()
    out=[
        "Knight of Danika focused graphics-pipeline trace",
        "================================================",
        "Known text path func_8017FC48 is excluded.",
        "",
        "Focus census",
        "------------",
    ]

    first_hop_seen=set()
    for name in FOCUS:
        if name not in defs:
            out.append(f"{name}: definition not found")
            continue
        info=summarize(name,defs[name],callers)
        out.append(
            f"{name}: {info['rel']}:{info['s']+1}-{info['e']+1} "
            f"incoming={len(info['incoming'])} calls={len(info['calls'])} "
            f"unique_calls={len(set(info['calls']))} globals={len(set(info['globals']))} "
            f"classish_loads={len(info['class_lines'])}"
        )
        out.append("  callees="+", ".join(sorted(set(info['calls']))))
        out.append("  globals="+", ".join(sorted(set(info['globals']))[:80]))
        for c in info['calls']:
            first_hop_seen.add(c)
    out.append("")

    out += ["Focus function bodies", "---------------------"]
    for name in FOCUS:
        if name not in defs: continue
        info=summarize(name,defs[name],callers)
        marks=set(info['class_lines'])
        # Mark calls as well, so large functions retain all important neighborhoods.
        rel,s,e,lines=defs[name]
        for i in range(s,e+1):
            if CALL_RE.search(lines[i]): marks.add(i)
        emit_body(out,name,defs[name],marks,limit=650)

    out += ["Incoming callers for focus functions", "------------------------------------"]
    for name in FOCUS:
        out.append(f"### {name} incoming={len(callers.get(name,[]))}")
        for caller,rel,i in callers.get(name,[]):
            out.append(f"  {caller} {rel}:{i+1}")
        out.append("")

    # Include definitions for every first-hop callee from the strongest two focus
    # functions, plus the curated helper set above. This often proves subsystem
    # semantics immediately (string, memory, battle, IO, renderer, etc.).
    wanted=set(FIRST_HOP)
    for name in FOCUS[:2]:
        if name in defs:
            info=summarize(name,defs[name],callers)
            wanted.update(info['calls'])

    out += ["First-hop helper definitions", "----------------------------"]
    for name in sorted(wanted):
        if name not in defs:
            out.append(f"### {name}: definition not found in asm")
            continue
        info=summarize(name,defs[name],callers)
        out.append(
            f"HELPER {name}: {info['rel']}:{info['s']+1}-{info['e']+1} "
            f"incoming={len(info['incoming'])} calls={len(info['calls'])} globals={len(set(info['globals']))}"
        )
        marks=set(info['class_lines'])
        rel,s,e,lines=defs[name]
        for i in range(s,e+1):
            if CALL_RE.search(lines[i]): marks.add(i)
        emit_body(out,name,defs[name],marks,limit=260)

    # Cross-reference globals used by the top two functions. Repeated use in a
    # battle renderer/loader neighborhood can identify state/side/orientation.
    top_globals=set()
    for name in FOCUS[:2]:
        if name in defs:
            top_globals.update(summarize(name,defs[name],callers)['globals'])
    out += ["Cross-references to globals used by top two candidates", "-------------------------------------------------"]
    if top_globals:
        for g in sorted(top_globals):
            refs=[]
            for path in files():
                lines=path.read_text(encoding="utf-8",errors="replace").splitlines()
                for i,line in enumerate(lines):
                    if g in line:
                        refs.append((path.relative_to(ROOT).as_posix(),i+1,line.strip()))
            out.append(f"{g}: refs={len(refs)}")
            for rel,ln,text in refs[:30]:
                out.append(f"  {rel}:{ln}: {text}")
            if len(refs)>30: out.append(f"  ... {len(refs)-30} more")
    else:
        out.append("(none)")
    out += [
        "",
        "Decision rule",
        "-------------",
        "A candidate graduates to a patch target only if its data flow proves both:",
        "(1) class/unit identity including class 0x71, and (2) actual battle visual",
        "resource loading/render setup with a side/orientation distinction. Text/UI,",
        "save, controller, roster-only, or generic framebuffer paths are rejected.",
        "",
    ]
    text="\n".join(out)
    (ROOT/"danika-gfx-pipeline-trace.txt").write_text(text,encoding="utf-8")
    print(text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
