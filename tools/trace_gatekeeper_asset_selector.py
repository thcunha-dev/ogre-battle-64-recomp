#!/usr/bin/env python3
"""Trace the suspected battle asset selector D_801BA72D.

The visual loader func_801AE794 repeatedly passes D_801BA72D as arg0 into
func_801B3C78/func_801B3D1C. This tool dumps:
  * every function that reads/writes D_801BA72D;
  * the complete bodies of func_801B3998, func_801B3C78, func_801B3D1C;
  * callers of those helper functions;
  * nearby constants/class IDs in selector writer functions.

Static analysis only; no runtime mutation.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM_ROOT = ROOT / "asm"
OUT = ROOT / "gatekeeper-asset-selector-trace.txt"
SELECTOR = "D_801BA72D"
HELPERS = {"func_801B3998", "func_801B3C78", "func_801B3D1C"}

FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
STORE_SELECTOR_RE = re.compile(r"\b(sb|sh|sw)\b.*%lo\(D_801BA72D\)")
LOAD_SELECTOR_RE = re.compile(r"\b(lbu|lb|lhu|lh|lw)\b.*%lo\(D_801BA72D\)")
CLASS_ID_RE = re.compile(r"(?:addiu|ori)\s+\$[a-z0-9]+,\s*\$zero,\s*(0x[0-9A-Fa-f]+|-?\d+)")


def functions(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        m = FUNC_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        end = min(len(lines) - 1, i + 1400)
        for j in range(i + 1, end + 1):
            em = END_RE.match(lines[j])
            if em and em.group(1) == name:
                end = j
                break
            if j > i + 1 and FUNC_RE.match(lines[j]):
                end = j - 1
                break
        yield name, i + 1, end + 1, lines[i:end + 1]
        i = end + 1


def build_index():
    idx = {}
    for path in sorted(ASM_ROOT.rglob("*.s")):
        rel = path.relative_to(ROOT).as_posix()
        for name, start, end, lines in functions(path):
            idx[name] = (rel, start, end, lines)
    return idx


def main() -> int:
    idx = build_index()
    callers = {h: [] for h in HELPERS}
    selector_refs = []

    for name, (rel, start, end, body) in idx.items():
        text = "\n".join(body)
        for callee in CALL_RE.findall(text):
            if callee in callers:
                callers[callee].append((rel, name, start))
        if SELECTOR in text:
            writes = any(STORE_SELECTOR_RE.search(line) for line in body)
            reads = any(LOAD_SELECTOR_RE.search(line) for line in body)
            constants = []
            for line in body:
                constants.extend(CLASS_ID_RE.findall(line))
            selector_refs.append((rel, name, start, end, writes, reads, constants, body))

    missing = HELPERS - set(idx)
    assert not missing, f"missing helper functions: {sorted(missing)}"
    assert selector_refs, "no references to D_801BA72D found"

    lines = [
        "Gatekeeper suspected battle-asset selector trace",
        "================================================",
        f"selector={SELECTOR}",
        "Static analysis only; no runtime mutation.",
        "",
        "SELECTOR REFERENCES",
        "-------------------",
    ]

    for rel, name, start, end, writes, reads, constants, body in selector_refs:
        mode = ("W" if writes else "-") + ("R" if reads else "-")
        lines.append(f"{mode} {name} {rel}:{start}-{end}")
        if constants:
            lines.append("  immediates=" + ",".join(constants[:64]))
        for raw in body:
            if SELECTOR in raw or STORE_SELECTOR_RE.search(raw) or LOAD_SELECTOR_RE.search(raw):
                lines.append("  " + raw)
        lines.append("")

    lines += ["HELPER BODIES", "-------------"]
    for helper in sorted(HELPERS):
        rel, start, end, body = idx[helper]
        lines.append(f"HELPER {helper} {rel}:{start}-{end}")
        lines.append("callers:")
        for crel, caller, cline in callers.get(helper, [])[:64]:
            lines.append(f"  {crel}:{cline} {caller}")
        if not callers.get(helper):
            lines.append("  none")
        lines.append("assembly:")
        for raw in body:
            lines.append("  " + raw)
        lines.append("")

    lines += [
        "Interpretation contract",
        "-----------------------",
        "- D_801BA72D is only a candidate selector until its writer semantics are proven.",
        "- A future allied Gatekeeper override must be scoped by proven player ownership.",
        "- Enemy Gatekeeper and class identity 0x71 must remain untouched.",
    ]

    report = "\n".join(lines) + "\n"
    OUT.write_text(report, encoding="utf-8")
    print(report, end="")
    print(f"Gatekeeper asset-selector trace: PASS refs={len(selector_refs)} helpers={len(HELPERS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
