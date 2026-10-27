#!/usr/bin/env python3
"""Extract and correlate the two strongest Gatekeeper battle visual loaders.

This is static-analysis only. It dumps func_801AD368 and func_801AE794, finds
which class-table helper functions they call, and recursively reports one caller
layer around those helpers/loaders. The goal is to locate the exact selector or
motion-set decision point that can safely borrow Dragoon 0x14 presentation for
an allied Gatekeeper 0x71 while leaving enemy Danika untouched.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM_ROOT = ROOT / "asm"
OUT = ROOT / "gatekeeper-visual-loader-trace.txt"
TARGETS = {"func_801AD368", "func_801AE794"}

FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
CLASS_HELPER_RE = re.compile(r"func_8016D[0-9A-Fa-f]{3}|func_8016E[0-9A-Fa-f]{3}|func_8016F[0-9A-Fa-f]{3}")
CLASS_SYMBOL_RE = re.compile(r"D_80187C[0-9A-Fa-f]{2}")


def functions(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        m = FUNC_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        end = min(len(lines) - 1, i + 1200)
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


def caller_map(idx):
    out = {}
    for caller, (rel, start, _end, lines) in idx.items():
        text = "\n".join(lines)
        for callee in CALL_RE.findall(text):
            out.setdefault(callee, []).append((rel, caller, start))
    return out


def main() -> int:
    idx = build_index()
    callers = caller_map(idx)
    missing = TARGETS - set(idx)
    assert not missing, f"missing target loaders: {sorted(missing)}"

    lines = [
        "Gatekeeper battle visual-loader trace",
        "====================================",
        "Static analysis only; no runtime mutation.",
        "",
    ]

    all_helpers = set()
    for target in sorted(TARGETS):
        rel, start, end, body = idx[target]
        text = "\n".join(body)
        calls = CALL_RE.findall(text)
        helpers = sorted(set(CLASS_HELPER_RE.findall(text)))
        class_syms = sorted(set(CLASS_SYMBOL_RE.findall(text)))
        all_helpers.update(helpers)

        lines += [
            f"TARGET {target} {rel}:{start}-{end}",
            f"call_count={len(calls)}",
            "calls=" + (",".join(calls) if calls else "none"),
            "class_helpers=" + (",".join(helpers) if helpers else "none"),
            "direct_class_symbols=" + (",".join(class_syms) if class_syms else "none"),
            "callers:",
        ]
        for crel, caller, cline in callers.get(target, [])[:32]:
            lines.append(f"  {crel}:{cline} {caller}")
        if not callers.get(target):
            lines.append("  none")
        lines += ["assembly:"]
        for raw in body:
            lines.append("  " + raw)
        lines.append("")

    lines += ["CLASS HELPER CONTEXT", "--------------------"]
    for helper in sorted(all_helpers):
        lines.append(f"{helper} callers:")
        for rel, caller, line in callers.get(helper, [])[:48]:
            tag = "VISUAL" if caller in TARGETS or caller.startswith("func_801A") else "OTHER"
            lines.append(f"  {tag} {rel}:{line} {caller}")
        if not callers.get(helper):
            lines.append("  none")

    lines += [
        "",
        "Safety rule",
        "-----------",
        "A runtime Gatekeeper shim may redirect only a proven selector/motion/weapon input.",
        "It must not replace class 0x71 globally or alter original enemy Gatekeeper resources.",
    ]

    report = "\n".join(lines) + "\n"
    OUT.write_text(report, encoding="utf-8")
    print(report, end="")
    print(f"Gatekeeper visual-loader trace: PASS targets={len(TARGETS)} helpers={len(all_helpers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
