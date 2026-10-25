#!/usr/bin/env python3
"""Trace class/side-sensitive resource selection feeding the battle renderer.

The playable-Danika gate is already fail-closed: identity is descriptor+0x4F
(class 0x71), while allied side must come from independently proven battle
participant state.  This probe searches the real renderer and its immediate
producer/callback path for the *smallest downstream selector* whose inputs are
class-derived and whose result reaches graphics/animation resource handling.

It deliberately does not patch anything.  A candidate is useful only when the
report shows all of:
  1. class provenance from descriptor+0x4F or a verified class accessor;
  2. a concrete table/pointer/resource decision downstream;
  3. a hook narrow enough to preserve enemy/front Danika unchanged.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM_ROOT = ROOT / "asm"
OUT = ROOT / "danika-allied-resource-path.txt"
TARGETS = {
    "func_801AD6C4",  # real display-list renderer
    "func_801B3868",  # callback wrapper
    "func_801AE794",  # battle-object/callback construction
}
FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
REG_RE = re.compile(r"\$([A-Za-z0-9]+)")
SYM_RE = re.compile(r"\b(?:D|jtbl)_[0-9A-Fa-f]{8}\b")
CLASS_LOAD_RE = re.compile(r"\blbu\s+\$([A-Za-z0-9]+),\s*0x4F\(\$([A-Za-z0-9]+)\)", re.I)
CLASS_ALT_RE = re.compile(r"\blbu\s+\$([A-Za-z0-9]+),\s*0x4B\(\$([A-Za-z0-9]+)\)", re.I)
MEM_RE = re.compile(r"\b(lw|lh|lhu|lb|lbu|lwc1)\s+\$([A-Za-z0-9]+),\s*([^\n]+?)\(\$([A-Za-z0-9]+)\)", re.I)
BR_RE = re.compile(r"\b(beq|bne|beqz|bnez|beql|bnel|slti|sltiu|slt|sltu)\b")
SHIFT_RE = re.compile(r"\b(sll|srl|sra)\b")

PROP_OPS = {
    "move","addu","addiu","subu","or","ori","and","andi","xor","xori",
    "sll","srl","sra","slt","sltu","slti","sltiu","mul","mult","multu",
}
LOAD_OPS = {"lw","lh","lhu","lb","lbu","lwc1"}


def opcode(line: str) -> str:
    text = line.split("*/", 1)[-1].strip() if "*/" in line else line.strip()
    if not text or text.endswith(":"):
        return ""
    return text.split()[0].lower()


def blocks(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        m = FUNC_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1); s = i; e = min(len(lines)-1, i+6000)
        for j in range(i+1, e+1):
            em = END_RE.match(lines[j])
            if em and em.group(1) == name:
                e = j; break
            if j > i+1 and FUNC_RE.match(lines[j]):
                e = j-1; break
        yield name, s+1, e+1, lines[s:e+1]
        i = e+1


def main() -> int:
    defs = {}
    callers = {t: [] for t in TARGETS}
    for path in sorted(ASM_ROOT.rglob("*.s")):
        rel = path.relative_to(ROOT).as_posix()
        for name, s, e, lines in blocks(path):
            if name in TARGETS:
                defs[name] = (rel, s, e, lines)
            for n, line in enumerate(lines, start=s):
                cm = CALL_RE.search(line)
                if cm and cm.group(1) in TARGETS:
                    callers[cm.group(1)].append((rel, name, s, e, n, lines))

    missing = TARGETS - defs.keys()
    assert not missing, f"missing target functions: {sorted(missing)}"

    out = [
        "Knight of Danika allied resource-path trace",
        "===========================================",
        "Identity contract: descriptor+0x4F is the verified renderer class byte.",
        "Side contract: ally/enemy is independent participant state; renderer layout flags are not substitutes.",
        "Patch policy: class 0x71 + proven allied side only; enemy/unknown remain vanilla.",
        "",
    ]

    rel, s, e, lines = defs["func_801AD6C4"]
    tainted = set()
    events = []
    class_seed_count = 0
    for n, line in enumerate(lines, start=s):
        op = opcode(line)
        regs = [x.lower() for x in REG_RE.findall(line)]
        seed = CLASS_LOAD_RE.search(line)
        alt = CLASS_ALT_RE.search(line)
        if seed:
            tainted.add(seed.group(1).lower())
            class_seed_count += 1
            events.append((n, "CLASS_SEED", line.strip(), sorted(tainted)))
        elif alt:
            events.append((n, "ALT_DESCRIPTOR_BYTE", line.strip(), sorted(tainted)))

        cm = CALL_RE.search(line)
        syms = SYM_RE.findall(line)
        mem = MEM_RE.search(line)
        src_tainted = any(r in tainted for r in regs)
        interesting = src_tainted or cm or syms or (mem and mem.group(4).lower() in tainted)
        if interesting and not seed:
            tags = []
            if src_tainted: tags.append("CLASS_TAINT")
            if cm: tags.append("CALL=" + cm.group(1))
            if syms: tags.append("SYMS=" + ",".join(sorted(set(syms))))
            if mem and mem.group(4).lower() in tainted: tags.append("TAINTED_ADDRESS_LOAD")
            if BR_RE.search(line): tags.append("BRANCH/COMPARE")
            if SHIFT_RE.search(line): tags.append("INDEX_SHIFT")
            events.append((n, ";".join(tags), line.strip(), sorted(tainted)))

        if regs:
            dest = regs[0]
            if op in PROP_OPS:
                srcs = regs[1:]
                if any(r in tainted for r in srcs):
                    tainted.add(dest)
                elif dest in tainted:
                    tainted.remove(dest)
            elif op in LOAD_OPS:
                base_tainted = any(r in tainted for r in regs[1:])
                if base_tainted:
                    tainted.add(dest)
                elif dest in tainted:
                    tainted.remove(dest)
            elif op == "lui" and dest in tainted:
                tainted.remove(dest)

        if cm:
            arg_tainted = any(r in tainted for r in ("a0","a1","a2","a3"))
            if arg_tainted:
                tainted.add("v0")
                events.append((n, "CLASS_TAINTED_CALL_RETURN=v0", line.strip(), sorted(tainted)))
            else:
                tainted.discard("v0")
                tainted.discard("v1")

    assert class_seed_count, "renderer identity seed descriptor+0x4F not found"
    out += [
        f"Renderer: func_801AD6C4 {rel}:{s}-{e}",
        "---------------------------------------------",
        f"descriptor+0x4F class seeds={class_seed_count}",
        f"taint/resource events={len(events)}",
    ]
    for n, tag, line, taint in events:
        out.append(f"{n}: [{tag}] {line}  # taint={','.join(taint)}")

    for target in ("func_801B3868", "func_801AE794"):
        rel, s, e, lines = defs[target]
        out += ["", f"Full {target} {rel}:{s}-{e}", "-" * 72]
        for n, line in enumerate(lines, start=s):
            marks = []
            cm = CALL_RE.search(line)
            if cm: marks.append("call=" + cm.group(1))
            syms = SYM_RE.findall(line)
            if syms: marks.append("symbols=" + ",".join(sorted(set(syms))))
            out.append(f"{n}: {line}" + ("  # " + "; ".join(marks) if marks else ""))

    out += ["", "Immediate callers", "-----------------"]
    for target in sorted(TARGETS):
        out.append(f"## {target}: callers={len(callers[target])}")
        for rel, name, fs, fe, calln, flines in callers[target]:
            out.append(f"### {name} {rel}:{fs}-{fe} call@{calln}")
            lo=max(fs,calln-24); hi=min(fe,calln+28)
            for n,line in enumerate(flines,start=fs):
                if lo <= n <= hi:
                    out.append(f"{'>>>' if n==calln else '   '} {n}: {line}")

    out += [
        "",
        "Acceptance rule for the next patch",
        "----------------------------------",
        "A runtime override may be implemented only at a selector/helper where the report proves class-derived input reaches a resource/animation decision.",
        "The override must call danika_should_use_player_override(class_id, side) before substituting any Dragoon donor selector.",
        "Enemy Danika, unknown side, non-0x71 classes, and global Dragoon resources must remain untouched.",
    ]
    OUT.write_text("\n".join(out)+"\n", encoding="utf-8")

    # CI-visible shortlist. This deliberately prints only events where class
    # taint reaches control flow, a table/address load, a symbol, or a call.
    # That makes the next hook decision reviewable without downloading artifacts.
    high_signal = []
    for event in events:
        n, tag, line, taint = event
        if "CLASS_SEED" in tag:
            high_signal.append(event)
            continue
        if "CLASS_TAINT" in tag and any(key in tag for key in (
            "CALL=", "SYMS=", "TAINTED_ADDRESS_LOAD", "BRANCH/COMPARE", "INDEX_SHIFT"
        )):
            high_signal.append(event)
        elif "CLASS_TAINTED_CALL_RETURN" in tag:
            high_signal.append(event)

    print(f"Danika allied resource path: PASS (class_seeds={class_seed_count}, events={len(events)}, high_signal={len(high_signal)})")
    print("HIGH_SIGNAL_BEGIN")
    for n, tag, line, taint in high_signal[:120]:
        print(f"{n}: [{tag}] {line} # taint={','.join(taint)}")
    if len(high_signal) > 120:
        print(f"... {len(high_signal)-120} additional high-signal events in {OUT.name}")
    print("HIGH_SIGNAL_END")
    print("report=" + OUT.name)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
