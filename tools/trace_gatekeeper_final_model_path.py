#!/usr/bin/env python3
"""Trace the final Ogre Battle 64 battle model/resource path for Gatekeeper work.

Static-analysis only.  The earlier visual-shell experiment proved that changing
battle_record+0x00 selectors while keeping class 0x14 does not replace the final
Dragoon body.  This script therefore traces the next layer: model/resource
loaders, descriptor construction, descriptor consumers, and all nearby writes
of the selector/class fields used by the renderer.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM = ROOT / "asm"
OUT = ROOT / "gatekeeper-final-model-path.txt"

TARGETS = {
    "func_801AD13C",  # resource/model load/cache
    "func_801AD368",  # dynamic loader caller path
    "func_801AD6C4",  # renderer-side class/effect consumer
    "func_801AE794",  # descriptor construction
    "func_801B3D1C",  # group/slot selector accessor
    "func_801B3868",  # renderer caller context
}

FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
SYMBOL_RE = re.compile(r"\bD_801B(?:A690|A6D8|A718|A72D|9540)\b|\bD_80187C[0-9A-Fa-f]{2}\b")
OFFSET_RE = re.compile(r"(?<![0-9A-Fa-f])0x(?:34|48|4B|4C|4F|00|02|0C)\b")


def iter_functions(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        m = FUNC_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        j = i + 1
        while j < len(lines):
            if END_RE.match(lines[j]) or FUNC_RE.match(lines[j]):
                break
            j += 1
        yield name, i + 1, j, lines[i:j]
        i = max(j, i + 1)


def build_index():
    idx = {}
    for path in sorted(ASM.rglob("*.s")):
        rel = path.relative_to(ROOT).as_posix()
        for name, start, end, body in iter_functions(path):
            idx[name] = (rel, start, end, body)
    return idx


def callers_for(idx):
    callers = {}
    for caller, (rel, start, _end, body) in idx.items():
        for callee in CALL_RE.findall("\n".join(body)):
            callers.setdefault(callee, []).append((rel, caller, start))
    return callers


def tagged_lines(body):
    out = []
    for n, raw in enumerate(body, 1):
        tags = []
        if CALL_RE.search(raw):
            tags.append("CALL")
        syms = SYMBOL_RE.findall(raw)
        if syms:
            tags.append("SYM:" + ",".join(syms))
        offs = OFFSET_RE.findall(raw)
        if offs:
            tags.append("OFF:" + ",".join(offs))
        if any(op in raw for op in (" sb ", " sh ", " sw ", " lbu ", " lb ", " lhu ", " lh ", " lw ")):
            tags.append("MEM")
        if tags:
            out.append((n, "+".join(tags), raw))
    return out


def main() -> int:
    idx = build_index()
    callers = callers_for(idx)
    missing = sorted(TARGETS - set(idx))
    assert not missing, f"missing target functions: {missing}"

    lines = [
        "Gatekeeper final battle-model path trace",
        "========================================",
        "Static analysis only; no runtime writes.",
        "Purpose: locate the model/resource decision that remains after battle_record selector overrides proved visually ineffective.",
        "",
    ]

    discovered_calls = set()
    for target in sorted(TARGETS):
        rel, start, end, body = idx[target]
        text = "\n".join(body)
        calls = CALL_RE.findall(text)
        discovered_calls.update(calls)
        lines += [
            f"TARGET {target} {rel}:{start}-{end}",
            "calls=" + (",".join(calls) if calls else "none"),
            "symbols=" + (",".join(sorted(set(SYMBOL_RE.findall(text)))) or "none"),
            "callers:",
        ]
        for crel, caller, cline in callers.get(target, [])[:64]:
            lines.append(f"  {crel}:{cline} {caller}")
        if not callers.get(target):
            lines.append("  none")
        lines.append("tagged assembly:")
        for reln, tags, raw in tagged_lines(body):
            lines.append(f"  +{reln:03d} [{tags}] {raw}")
        lines.append("full assembly:")
        lines.extend("  " + x for x in body)
        lines.append("")

    # Add one recursive layer for direct callees and callers, concentrating on
    # functions in the battle overlay where the final resource decision may sit.
    neighborhood = set()
    for name in TARGETS:
        neighborhood.update(CALL_RE.findall("\n".join(idx[name][3])))
        neighborhood.update(caller for _rel, caller, _line in callers.get(name, []))
    neighborhood -= TARGETS

    lines += ["NEIGHBORHOOD", "------------"]
    for name in sorted(neighborhood):
        if name not in idx:
            continue
        rel, start, end, body = idx[name]
        text = "\n".join(body)
        interesting = bool(SYMBOL_RE.search(text) or OFFSET_RE.search(text) or name.startswith("func_801A") or name.startswith("func_801B"))
        if not interesting:
            continue
        lines += [
            f"FUNC {name} {rel}:{start}-{end}",
            "calls=" + (",".join(CALL_RE.findall(text)) or "none"),
            "symbols=" + (",".join(sorted(set(SYMBOL_RE.findall(text)))) or "none"),
            "callers=" + (",".join(c for _r, c, _l in callers.get(name, [])[:24]) or "none"),
        ]
        for reln, tags, raw in tagged_lines(body):
            lines.append(f"  +{reln:03d} [{tags}] {raw}")
        lines.append("")

    # Find every function that directly references the key descriptor/resource globals.
    lines += ["GLOBAL REFERENCE INDEX", "----------------------"]
    for sym in ("D_801BA690", "D_801BA6D8", "D_801BA718", "D_801BA72D"):
        refs = []
        for name, (rel, start, _end, body) in idx.items():
            if any(sym in raw for raw in body):
                refs.append((rel, start, name))
        lines.append(f"{sym} refs={len(refs)}")
        for rel, start, name in refs[:128]:
            lines.append(f"  {rel}:{start} {name}")

    lines += [
        "",
        "Interpretation rule",
        "-------------------",
        "Do not patch battle_record+0x00 again unless a traced consumer proves it feeds the final body model.",
        "Prefer the earliest proven resource/model input that can be redirected while class/motion/equipment remain Dragoon 0x14.",
        "Do not alter enemy Gatekeeper resources globally.",
    ]

    report = "\n".join(lines) + "\n"
    OUT.write_text(report, encoding="utf-8")
    print(report, end="")
    print(f"Gatekeeper final-model trace: PASS targets={len(TARGETS)} neighborhood={len(neighborhood)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
