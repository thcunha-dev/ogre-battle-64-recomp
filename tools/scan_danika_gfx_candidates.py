#!/usr/bin/env python3
"""Rank real battle-graphics candidates for playable Knight of Danika.

The previous 0x01DE path was proven to be text formatting.  This scanner starts
fresh and looks for functions that combine class metadata/battle-unit class
access with graphics-loader signals.  It is intentionally conservative: the
report ranks candidates, it does not patch anything or assign semantics that
have not been proved.
"""

from __future__ import annotations

import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
ASM_ROOT = ROOT / "asm"

# Early fields in the verified 0x48-byte class record.  The first three are
# identifier-like because 0x14 and 0x9c match while 0x71 differs.
CLASS_SYMBOLS = {
    "D_80187C62": "+0x00",
    "D_80187C64": "+0x02",
    "D_80187C66": "+0x04",
    "D_80187C68": "+0x06",
    "D_80187C79": "+0x17 alias/key",
}
CLASS_ACCESSORS = {
    "func_8016DFA8",
    "func_8016DFFC",
    "func_8016E050",
    "func_8016E0A4",
    "func_8016E0F8",
    "func_8016E14C",
    "func_8016E52C",
}

# Text path is a known false lead and gets a hard exclusion marker.
TEXT_PATH = {"func_8017FC48", "func_8017FB18"}

FUNC_START_RE = re.compile(r"^\s*(?:glabel|nonmatching)\s+([A-Za-z0-9_.$]+)")
GLABEL_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
IMM_CLASS_RE = re.compile(r"(?:0x)?(?:14|71|9C)\b", re.IGNORECASE)
LOAD_CLASSISH_RE = re.compile(r"\blbu\s+\$[a-z0-9]+,\s*0x(?:11|12|1A)\(")

# Terms are only hints. They increase ranking but never prove semantics.
GFX_TERMS = {
    "texture": 8,
    "sprite": 8,
    "palette": 7,
    "animation": 7,
    "anim": 5,
    "displaylist": 6,
    "display_list": 6,
    "gfx": 5,
    "tlut": 6,
    "vtx": 4,
    "vertex": 4,
    "model": 5,
    "frame": 2,
    "render": 5,
    "draw": 4,
    "dma": 7,
    "decomp": 7,
    "decompress": 7,
    "inflate": 6,
    "mio0": 7,
    "yay0": 7,
    "rsp": 3,
    "rdp": 3,
    "segment": 2,
}

# Typical N64 graphics opcodes/macros, useful even when functions remain unnamed.
ASM_GFX_PATTERNS = {
    "gSP": 5,
    "gDP": 5,
    "gsSP": 5,
    "gsDP": 5,
    "G_IM_FMT": 5,
    "G_IM_SIZ": 5,
    "osPi": 7,
    "PI_DMA": 7,
    "Dma": 7,
}


def asm_files() -> list[Path]:
    return sorted(ASM_ROOT.rglob("*.s"))


def split_functions(path: Path) -> list[tuple[str, int, int, list[str]]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    starts: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = GLABEL_RE.match(line)
        if m:
            starts.append((i, m.group(1)))
    out = []
    for n, (start, name) in enumerate(starts):
        end = starts[n + 1][0] - 1 if n + 1 < len(starts) else len(lines) - 1
        # Prefer explicit endlabel when available.
        for j in range(start + 1, min(end + 1, len(lines))):
            m = END_RE.match(lines[j])
            if m and m.group(1) == name:
                end = j
                break
        out.append((name, start, end, lines[start:end + 1]))
    return out


def discover_named_loader_functions() -> set[str]:
    """Find symbol/function names whose spelling itself suggests graphics/load work."""
    names: set[str] = set()
    term_re = re.compile("|".join(re.escape(k) for k in sorted(GFX_TERMS, key=len, reverse=True)), re.I)
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in {".s", ".c", ".h", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in re.finditer(r"\b(?:func_[0-9A-Fa-f]+|[A-Za-z_][A-Za-z0-9_]*)\b", text):
            token = m.group(0)
            if term_re.search(token):
                names.add(token)
    return names


def main() -> int:
    loader_names = discover_named_loader_functions()
    functions = []
    callers: dict[str, list[tuple[str, str, int]]] = defaultdict(list)

    for path in asm_files():
        rel = path.relative_to(ROOT).as_posix()
        for name, start, end, body in split_functions(path):
            text = "\n".join(body)
            score = 0
            reasons: list[str] = []
            class_refs: list[str] = []
            calls: list[str] = []

            for sym, off in CLASS_SYMBOLS.items():
                count = text.count(sym)
                if count:
                    weight = 14 if sym != "D_80187C79" else 4
                    score += weight * count
                    class_refs.append(f"{sym}({off})x{count}")
                    reasons.append(f"class-field {sym} {off} x{count}")

            for acc in CLASS_ACCESSORS:
                count = len(re.findall(rf"\bjal\s+{re.escape(acc)}\b", text))
                if count:
                    score += 10 * count
                    reasons.append(f"calls class accessor {acc} x{count}")

            # Raw unit-structure class-like loads are weaker but useful for ranking.
            classish = len(LOAD_CLASSISH_RE.findall(text))
            if classish:
                score += min(classish, 8) * 2
                reasons.append(f"unit-field lbu(+11/+12/+1A) x{classish}")

            for line in body:
                m = CALL_RE.search(line)
                if m:
                    target = m.group(1)
                    calls.append(target)
                    callers[target].append((name, rel, start + body.index(line) + 1))
                    if target in loader_names:
                        score += 6
                        reasons.append(f"calls loader-like symbol {target}")

            lower = text.lower()
            for term, weight in GFX_TERMS.items():
                count = lower.count(term.lower())
                if count:
                    score += min(count, 4) * weight
                    reasons.append(f"term {term} x{count}")
            for pat, weight in ASM_GFX_PATTERNS.items():
                count = text.count(pat)
                if count:
                    score += min(count, 4) * weight
                    reasons.append(f"asm gfx/load pattern {pat} x{count}")

            # Explicit class constants are very noisy; small score only when the
            # function already has another class/graphics signal.
            class_imms = len(IMM_CLASS_RE.findall(text))
            if class_imms and score:
                score += min(class_imms, 6)
                reasons.append(f"0x14/0x71/0x9c-like immediates x{class_imms}")

            excluded = name in TEXT_PATH
            if excluded:
                score -= 1000
                reasons.append("KNOWN TEXT FORMATTER PATH — EXCLUDED")

            if score > 0 or class_refs:
                functions.append({
                    "score": score,
                    "name": name,
                    "file": rel,
                    "start": start + 1,
                    "end": end + 1,
                    "body": body,
                    "reasons": reasons,
                    "class_refs": class_refs,
                    "calls": calls,
                    "excluded": excluded,
                })

    functions.sort(key=lambda x: (-x["score"], x["file"], x["start"]))

    out = [
        "Knight of Danika real graphics-path candidate scan",
        "=================================================",
        "Known false lead excluded: func_8017FC48 / 0x01DE text-resource path",
        f"asm_files={len(asm_files())}",
        f"loader_like_symbol_names={len(loader_names)}",
        f"ranked_functions={len(functions)}",
        "",
        "Top ranked functions",
        "--------------------",
    ]

    for rank, item in enumerate(functions[:80], 1):
        out.append(
            f"#{rank:02d} score={item['score']:4d} {item['name']} "
            f"{item['file']}:{item['start']}-{item['end']}"
        )
        if item["class_refs"]:
            out.append("  class_refs=" + ", ".join(item["class_refs"]))
        for reason in item["reasons"][:16]:
            out.append("  + " + reason)
        if len(item["reasons"]) > 16:
            out.append(f"  ... {len(item['reasons']) - 16} more reasons")
        out.append("")

    # Dedicated census of every function directly touching the identifier-like fields.
    direct = [f for f in functions if any(s in "\n".join(f["body"]) for s in ("D_80187C62", "D_80187C64", "D_80187C66", "D_80187C68"))]
    out += [
        "Direct consumers of early class-record fields",
        "--------------------------------------------",
        f"count={len(direct)}",
    ]
    for item in direct:
        out.append(f"### {item['name']} {item['file']}:{item['start']}-{item['end']} score={item['score']}")
        # Print all class-table references plus +/- 8 lines around them.
        body = item["body"]
        marks = [i for i, line in enumerate(body) if any(sym in line for sym in CLASS_SYMBOLS)]
        emitted = set()
        for mark in marks:
            lo, hi = max(0, mark - 8), min(len(body), mark + 9)
            for i in range(lo, hi):
                key = (i, body[i])
                if key in emitted:
                    continue
                emitted.add(key)
                prefix = ">>>" if i == mark else "   "
                out.append(f"{prefix} {item['start'] + i:6d}: {body[i]}")
        out.append("")

    # Candidate battle-unit readers: class-ish struct loads + calls. These often
    # reveal the setup path even if graphics tables themselves are anonymous.
    unit_readers = []
    for path in asm_files():
        rel = path.relative_to(ROOT).as_posix()
        for name, start, end, body in split_functions(path):
            text = "\n".join(body)
            n = len(LOAD_CLASSISH_RE.findall(text))
            if not n or name in TEXT_PATH:
                continue
            calls = CALL_RE.findall(text)
            if calls:
                unit_readers.append((n, len(calls), name, rel, start + 1, end + 1, body, calls))
    unit_readers.sort(key=lambda x: (-x[0], -x[1], x[3], x[4]))
    out += [
        "Battle/unit-structure reader candidates",
        "--------------------------------------",
        "(ranked by loads from +0x11/+0x12/+0x1A and call density; triage only)",
    ]
    for n, ncalls, name, rel, start, end, body, calls in unit_readers[:50]:
        out.append(f"{name} {rel}:{start}-{end}: classish_loads={n} calls={ncalls}")
        out.append("  jal_targets=" + ", ".join(sorted(set(calls))[:20]))
    out.append("")

    out += [
        "Loader-like symbol hints found in repository",
        "-------------------------------------------",
    ]
    for name in sorted(loader_names)[:300]:
        out.append(name)
    out += [
        "",
        "Interpretation",
        "--------------",
        "This report is a ranking aid, not proof. A graphics override must wait until a",
        "candidate can be shown to consume class/battle-side state and feed an actual",
        "graphics/model/animation load or renderer. The known text formatter path is",
        "explicitly excluded from consideration.",
        "",
    ]

    report = ROOT / "danika-gfx-candidate-report.txt"
    report.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
