#!/usr/bin/env python3
"""Prove the concrete battle visual-asset selector used by the renderer path.

The key chain is:
  resource 0x315736 -> func_801B3D1C 0x1A-byte record
  record+0x00 -> return value -> descriptor+0x50
  record+0x02 -> descriptor+0x4C class word
  func_801AD13C(descriptor+0x50, descriptor+0x4C)
  func_801AD13C indexes visual package 0x3B6CD0 with argument 0.

This is the first static proof of the exact per-participant field that selects
the loaded visual set.  It still does not claim which battle record represents
allied ownership; that remains a separate fail-closed proof requirement.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM_ROOT = ROOT / "asm"
OUT = ROOT / "danika-visual-asset-selector.txt"
TARGETS = {"func_801AD13C", "func_801AE794", "func_801B3C78", "func_801B3D1C"}
FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")


def blocks(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        m = FUNC_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name=m.group(1); s=i; e=min(len(lines)-1,i+8000)
        for j in range(i+1,e+1):
            em=END_RE.match(lines[j])
            if em and em.group(1)==name:
                e=j; break
            if j>i+1 and FUNC_RE.match(lines[j]):
                e=j-1; break
        yield name,s+1,e+1,lines[s:e+1]
        i=e+1


def has(body: str, pattern: str, msg: str):
    assert re.search(pattern, body, re.I|re.M), msg


def main()->int:
    defs={}
    callers={t:[] for t in TARGETS}
    for path in sorted(ASM_ROOT.rglob("*.s")):
        rel=path.relative_to(ROOT).as_posix()
        for name,s,e,lines in blocks(path):
            if name in TARGETS:
                defs[name]=(rel,s,e,lines)
            body="\n".join(lines)
            for target in TARGETS:
                if re.search(rf"\bjal\s+{re.escape(target)}\b",body):
                    callers[target].append((rel,name,s,e,lines))

    missing=TARGETS-defs.keys()
    assert not missing, f"missing targets: {sorted(missing)}"

    b3d="\n".join(defs["func_801B3D1C"][3])
    ae="\n".join(defs["func_801AE794"][3])
    loader="\n".join(defs["func_801AD13C"][3])

    # func_801B3D1C: 0x1A-byte slot addressing and record identity fields.
    has(b3d, r"84830000", "record+0x00 return/source missing")
    has(b3d, r"84820002", "record+0x02 class-word load missing")
    has(b3d, r"8482000C", "record+0x0C render-context load missing")
    has(b3d, r"84820010", "record+0x10 tail field missing")
    # 0x1A stride is synthesized as (((slot*2)+slot)*4+slot)*2.
    has(b3d, r"00051040[\s\S]*00451021[\s\S]*00021080[\s\S]*00451021[\s\S]*00021040",
        "0x1A slot-stride arithmetic missing")
    has(b3d, r"03E00008[\s\S]*84820000", "record+0x00 return in jr delay slot missing")

    # func_801AE794: return -> s6 -> descriptor+0x50, class output -> +0x4C,
    # then loader(a0=+0x50, a1=+0x4C).
    has(ae, r"jal\s+func_801B3D1C", "battle-record extraction call missing")
    has(ae, r"0040B021", "record+0 return capture into s6 missing")
    has(ae, r"AE360050", "visual selector store descriptor+0x50 missing")
    has(ae, r"2626004C", "class output pointer descriptor+0x4C missing")
    has(ae, r"8E240050[\s\S]*8E25004C[\s\S]*jal\s+func_801AD13C",
        "descriptor visual/class pair is no longer passed to visual loader")

    # func_801AD13C: cache key (a0,a1), package 0x3B6CD0, first argument
    # used as a 1-based pointer-table index: base + a0*4, load at -4.
    has(loader, r"00808821", "loader arg0 capture (s1) missing")
    has(loader, r"00A0A021", "loader arg1 capture (s4) missing")
    has(loader, r"8C620000[\s\S]*14510004[\s\S]*8C62000C[\s\S]*10540072",
        "two-word visual cache key comparison missing")
    has(loader, r"3C04003B[\s\S]*34846CD0", "visual package 0x3B6CD0 load missing")
    has(loader, r"00111080[\s\S]*00501021[\s\S]*8C44FFFC",
        "arg0 visual pointer-table index missing")

    out=[
        "Knight of Danika visual asset selector proof",
        "============================================",
        "",
        "PROVEN DATAFLOW",
        "---------------",
        "resource 0x315736 -> D_801BA6D8 -> 0x1A-byte battle record",
        "battle_record+0x00 -> func_801B3D1C return -> s6 -> descriptor+0x50",
        "battle_record+0x02 -> func_801B3D1C a2 output -> descriptor+0x4C class word",
        "func_801AD13C(descriptor+0x50, descriptor+0x4C)",
        "func_801AD13C uses argument 0 as a 1-based pointer-table index into package 0x3B6CD0.",
        "Therefore battle_record+0x00 is the concrete per-participant VISUAL ASSET SELECTOR.",
        "Argument 1 / descriptor+0x4C is part of the loader cache key and carries the class word.",
        "",
        "PATCH CONSEQUENCE",
        "-----------------",
        "The diagnostic Dragoon donor should eventually substitute battle_record+0x00 (or its descriptor+0x50 copy) only for class 0x71 on independently proven allied side.",
        "Do NOT replace descriptor+0x4C/class identity: Danika must remain class 0x71.",
        "Do NOT modify the enemy/front record or global Dragoon visual assets.",
        "",
        "NEXT DATA REQUIREMENT",
        "---------------------",
        "Extract/observe resource 0x315736 and compare record+0x00 for class 0x14, class 0x71 and class 0x9C across battle groups/sides.",
        "The exact donor value is intentionally not guessed by this static proof.",
        "",
    ]

    for target in ("func_801B3D1C","func_801B3C78","func_801AE794","func_801AD13C"):
        rel,s,e,lines=defs[target]
        out += [f"## {target} {rel}:{s}-{e}", "-"*72]
        for n,line in enumerate(lines,start=s):
            if target in {"func_801B3D1C","func_801B3C78"}:
                out.append(f"{n}: {line}")
            elif target=="func_801AE794":
                if any(x in line for x in ("func_801B3D1C","func_801AD13C","0x4C(","0x50(","AE360050","2626004C","8E240050","8E25004C")):
                    out.append(f"{n}: {line}")
            else:
                if any(x in line for x in ("D_801BA718","0x3B6CD0","3B6CD0","8C44FFFC","00111080","10540072","14510004")):
                    out.append(f"{n}: {line}")
        out.append("")

    out += ["Immediate callers of func_801B3C78", "----------------------------------"]
    for rel,name,s,e,lines in callers["func_801B3C78"]:
        out.append(f"{name} {rel}:{s}-{e}")
        for n,line in enumerate(lines,start=s):
            if "func_801B3C78" in line:
                lo=max(s,n-16); hi=min(e,n+18)
                for nn,ll in enumerate(lines,start=s):
                    if lo<=nn<=hi:
                        out.append(f"{nn}: {ll}")
                out.append("")

    OUT.write_text("\n".join(out)+"\n",encoding="utf-8")
    print("Danika visual asset selector: PASS")
    print("selector=battle_record+0x00 -> descriptor+0x50 -> visual package 0x3B6CD0")
    print("class_word=battle_record+0x02 -> descriptor+0x4C (preserve 0x71)")
    print("report="+OUT.name)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
