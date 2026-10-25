#!/usr/bin/env python3
"""Repository-wide reverse-engineering probe for Knight of Danika battle lookup.

This is an evidence collector, not a graphics patch. It scans the checked-out
recomp/disassembly for direct references and common MIPS address-materialization
patterns involving the class-table anchors used by the Danika restoration, then
prints bounded function context for executable references.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

CLASS_BASE = 0x80187C62
CLASS_STRIDE = 0x48
ANCHORS = {
    "class_table_base": CLASS_BASE,
    "dragoon_0x14": CLASS_BASE + 0x14 * CLASS_STRIDE,
    "danika_0x71": CLASS_BASE + 0x71 * CLASS_STRIDE,
    "hidden_dragoon_0x9c": CLASS_BASE + 0x9C * CLASS_STRIDE,
}

TEXT_ROOTS = ("asm", "config", "include", "mods", "patches")
TEXT_SUFFIXES = {".s", ".S", ".c", ".h", ".toml", ".json", ".yaml", ".yml", ".txt", ".md"}
MAX_CONTEXT = 5
FUNCTION_CONTEXT_BEFORE = 35
FUNCTION_CONTEXT_AFTER = 55


@dataclass(frozen=True)
class Hit:
    kind: str
    anchor: str
    path: str
    line: int
    text: str


def iter_text_files(root: Path) -> Iterable[Path]:
    for rel in TEXT_ROOTS:
        base = root / rel
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                yield path


def address_spellings(addr: int) -> set[str]:
    return {
        f"0x{addr:08x}", f"0x{addr:08X}", f"{addr:08x}", f"{addr:08X}",
        f"D_{addr:08X}", f"D_{addr:08x}",
    }


def mips_halves(addr: int) -> tuple[set[int], int]:
    hi_ori = (addr >> 16) & 0xFFFF
    hi_addiu = ((addr + 0x8000) >> 16) & 0xFFFF
    return {hi_ori, hi_addiu}, addr & 0xFFFF


def parse_imm(line: str) -> list[int]:
    vals: list[int] = []
    for token in re.findall(r"(?<![\w])(?:0x[0-9A-Fa-f]+|\$[0-9A-Fa-f]+|[-+]?\d+)(?![\w])", line):
        try:
            vals.append((int(token[1:], 16) if token.startswith("$") else int(token, 0)) & 0xFFFF)
        except ValueError:
            pass
    return vals


def scan_file(root: Path, path: Path) -> list[Hit]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    rel = path.relative_to(root).as_posix()
    hits: list[Hit] = []

    for idx, line in enumerate(lines):
        low = line.lower()
        for name, addr in ANCHORS.items():
            if any(spelling.lower() in low for spelling in address_spellings(addr)):
                hits.append(Hit("direct", name, rel, idx + 1, line.strip()))

    for name, addr in ANCHORS.items():
        his, lo = mips_halves(addr)
        for idx, line in enumerate(lines):
            if "lui" not in line.lower() or not any(imm in his for imm in parse_imm(line)):
                continue
            for j in range(idx + 1, min(len(lines), idx + 1 + MAX_CONTEXT)):
                next_low = lines[j].lower()
                if any(op in next_low for op in ("addiu", "addi", "ori", "daddiu")) and lo in parse_imm(lines[j]):
                    hits.append(Hit("mips-hi-lo", name, rel, idx + 1,
                                    f"{line.strip()}  ||  {lines[j].strip()}"))

    # Keep this conservative: require an actual immediate operand 0x48/$48/72,
    # not merely an instruction address ending in 48.
    stride_pat = re.compile(r"(?i)(?:,|\s)(?:0x48|\$48|72)(?:\s|$)")
    for idx, line in enumerate(lines):
        if stride_pat.search(line) and any(op in line.lower() for op in ("mult", "mul", "add", "sll", "li", "ori", "addiu")):
            hits.append(Hit("stride-0x48", "class_stride", rel, idx + 1, line.strip()))

    return hits


def nearest_function(lines: list[str], one_based_line: int) -> tuple[int, str]:
    idx = max(0, one_based_line - 1)
    for j in range(idx, max(-1, idx - 600), -1):
        m = re.match(r"\s*(?:glabel|dlabel|nonmatching)\s+([A-Za-z0-9_.$]+)", lines[j])
        if m:
            return j, m.group(1)
    return max(0, idx - FUNCTION_CONTEXT_BEFORE), "<unknown>"


def executable_contexts(root: Path, direct: list[Hit]) -> list[str]:
    blocks: list[str] = []
    seen: set[tuple[str, str]] = set()
    for hit in direct:
        if not hit.path.startswith("asm/") or "/data/" in hit.path:
            continue
        path = root / hit.path
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        fn_start, fn_name = nearest_function(lines, hit.line)
        key = (hit.path, fn_name)
        if key in seen:
            continue
        seen.add(key)
        hit_idx = hit.line - 1
        start = max(fn_start, hit_idx - FUNCTION_CONTEXT_BEFORE)
        end = min(len(lines), hit_idx + FUNCTION_CONTEXT_AFTER + 1)
        blocks.append(f"### {hit.path}:{hit.line} function={fn_name}")
        for i in range(start, end):
            marker = ">>>" if i == hit_idx else "   "
            blocks.append(f"{marker} {i + 1:6d}: {lines[i]}")
        blocks.append("")
    return blocks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--output", type=Path, default=Path("danika-battle-lookup-report.txt"))
    args = ap.parse_args()
    root = args.root.resolve()

    files = sorted(set(iter_text_files(root)))
    hits: list[Hit] = []
    for path in files:
        hits.extend(scan_file(root, path))

    direct = [h for h in hits if h.kind == "direct"]
    hilo = [h for h in hits if h.kind == "mips-hi-lo"]
    stride = [h for h in hits if h.kind == "stride-0x48"]

    out: list[str] = [
        "Knight of Danika battle-lookup reverse-engineering probe",
        "========================================================",
        f"files_scanned={len(files)}",
        f"direct_anchor_hits={len(direct)}",
        f"mips_hi_lo_hits={len(hilo)}",
        f"stride_0x48_hits={len(stride)}",
        "",
    ]
    for name, addr in ANCHORS.items():
        out.append(f"{name}=0x{addr:08X}")
    out.append("")

    def section(title: str, rows: list[Hit], cap: int = 250) -> None:
        out.extend((title, "-" * len(title)))
        if not rows:
            out.append("(none)")
        else:
            for hit in rows[:cap]:
                out.append(f"{hit.anchor}\t{hit.path}:{hit.line}\t{hit.text}")
            if len(rows) > cap:
                out.append(f"... {len(rows) - cap} additional hits omitted")
        out.append("")

    section("Direct anchor references", direct)
    section("MIPS split-address candidates", hilo)
    section("0x48 stride candidates (triage only)", stride)

    contexts = executable_contexts(root, direct)
    out.extend(("Executable direct-reference contexts", "------------------------------------"))
    out.extend(contexts or ["(none)", ""])

    if not direct and not hilo:
        out.append("INTERPRETATION: no direct/split address materialization found; prioritize GP-relative pointers, relocation/data tables, and overlay asset selectors. Do not guess a sprite pointer.")
    else:
        out.append("INTERPRETATION: inspect executable contexts first and prove class-id + battle-side data flow before patching graphics resources.")

    text = "\n".join(out) + "\n"
    args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
