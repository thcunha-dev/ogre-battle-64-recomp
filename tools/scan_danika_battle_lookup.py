#!/usr/bin/env python3
"""Repository-wide reverse-engineering probe for Knight of Danika battle lookup.

This is intentionally an evidence collector, not a patch.  It scans the checked-out
recomp/disassembly for direct references and common MIPS address-materialization
patterns involving the class table anchors used by the Danika restoration.

The report is deterministic and is suitable for CI artifacts.  A zero-hit result is
still useful evidence: it means the table is probably reached indirectly (GP/data
pointer/overlay relocation) and tells us to move the next pass to pointer/data-flow
analysis instead of guessing a graphics pointer.
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
        f"0x{addr:08x}",
        f"0x{addr:08X}",
        f"{addr:08x}",
        f"{addr:08X}",
        f"D_{addr:08X}",
        f"D_{addr:08x}",
    }


def mips_halves(addr: int) -> tuple[set[int], int]:
    # Both common materializations are accepted:
    #   lui r, addr>>16 ; ori r,r,lo
    #   lui r, (addr+0x8000)>>16 ; addiu r,r,signed_lo
    hi_ori = (addr >> 16) & 0xFFFF
    hi_addiu = ((addr + 0x8000) >> 16) & 0xFFFF
    return {hi_ori, hi_addiu}, addr & 0xFFFF


def parse_imm(line: str) -> list[int]:
    vals: list[int] = []
    for token in re.findall(r"(?<![\w])(?:0x[0-9A-Fa-f]+|\$[0-9A-Fa-f]+|[-+]?\d+)(?![\w])", line):
        try:
            if token.startswith("$"):
                vals.append(int(token[1:], 16) & 0xFFFF)
            else:
                vals.append(int(token, 0) & 0xFFFF)
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

    # Exact textual/address-label references.
    for idx, line in enumerate(lines):
        low = line.lower()
        for name, addr in ANCHORS.items():
            if any(spelling.lower() in low for spelling in address_spellings(addr)):
                hits.append(Hit("direct", name, rel, idx + 1, line.strip()))

    # Common MIPS split-address materialization within a short instruction window.
    for name, addr in ANCHORS.items():
        his, lo = mips_halves(addr)
        for idx, line in enumerate(lines):
            lowered = line.lower()
            if "lui" not in lowered:
                continue
            imms = parse_imm(line)
            if not any(imm in his for imm in imms):
                continue
            for j in range(idx + 1, min(len(lines), idx + 1 + MAX_CONTEXT)):
                next_low = lines[j].lower()
                if not any(op in next_low for op in ("addiu", "addi", "ori", "daddiu")):
                    continue
                if lo in parse_imm(lines[j]):
                    text = f"{line.strip()}  ||  {lines[j].strip()}"
                    hits.append(Hit("mips-hi-lo", name, rel, idx + 1, text))

    # Independent stride evidence.  This does not claim a table reference; it is
    # included only to prioritize functions that may perform class_id * 0x48.
    for idx, line in enumerate(lines):
        if re.search(r"(?i)(?:0x|\$)?0*48\b", line) and any(
            op in line.lower() for op in ("mult", "mul", "add", "sll", "li", "ori", "addiu")
        ):
            hits.append(Hit("stride-0x48", "class_stride", rel, idx + 1, line.strip()))

    return hits


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

    out: list[str] = []
    out.append("Knight of Danika battle-lookup reverse-engineering probe")
    out.append("========================================================")
    out.append(f"files_scanned={len(files)}")
    out.append(f"direct_anchor_hits={len(direct)}")
    out.append(f"mips_hi_lo_hits={len(hilo)}")
    out.append(f"stride_0x48_hits={len(stride)}")
    out.append("")
    for name, addr in ANCHORS.items():
        out.append(f"{name}=0x{addr:08X}")
    out.append("")

    def section(title: str, rows: list[Hit], cap: int = 250) -> None:
        out.append(title)
        out.append("-" * len(title))
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

    if not direct and not hilo:
        out.append(
            "INTERPRETATION: no direct/split address materialization found. "
            "Prioritize GP-relative pointers, data tables, relocation tables, and "
            "overlay-side asset selectors in the next pass; do not guess a sprite pointer."
        )
    else:
        out.append(
            "INTERPRETATION: inspect direct/split-address candidates first and prove "
            "class-id + battle-side data flow before patching any graphics resource."
        )

    text = "\n".join(out) + "\n"
    args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
