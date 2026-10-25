#!/usr/bin/env python3
"""Rank class fields that may participate in Danika weapon/attack compatibility.

The restoration deliberately uses player Dragoon (0x14) as the compatibility
baseline for a future greatsword-capable allied Knight of Danika (0x71), while
preserving Danika identity and enemy/front graphics.

This tool does NOT label an unknown field as a weapon field merely because its
value differs.  It extracts the three aligned class records, identifies fields
where player Dragoon 0x14 and hidden Dragoon 0x9C agree but Danika 0x71 differs,
and correlates those offsets with the known D_80187Cxx accessor family and its
callers.  The resulting report is evidence for targeted follow-up, not a patch.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "asm/data/5C230.data.s"
CLASS_ASM = ROOT / "asm/40E80.s"
ASM_ROOT = ROOT / "asm"

BASE = 0x80187C34
STRIDE = 0x48
DRAGOON = 0x14
DANIKA = 0x71
HIDDEN_DRAGOON = 0x9C
OUT = ROOT / "danika-weapon-compat-report.txt"

ADDR_RE = re.compile(r"/\*\s*[0-9A-Fa-f]+\s+([0-9A-Fa-f]{8})\s*\*/\s*\.(byte|short|word)\s+(.+?)\s*$")
HEX_RE = re.compile(r"0x([0-9A-Fa-f]+)")
FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
ANCHOR_RE = re.compile(r"\bD_80187C([0-9A-Fa-f]{2})\b")


def parse_data_bytes() -> dict[int, int]:
    mem: dict[int, int] = {}
    for line in DATA.read_text(encoding="utf-8", errors="replace").splitlines():
        m = ADDR_RE.search(line)
        if not m:
            continue
        addr = int(m.group(1), 16)
        kind = m.group(2)
        vals = [int(x, 16) for x in HEX_RE.findall(m.group(3))]
        size = {"byte": 1, "short": 2, "word": 4}[kind]
        for n, val in enumerate(vals):
            a = addr + n * size
            for j in range(size):
                mem[a + j] = (val >> (8 * (size - 1 - j))) & 0xFF
    return mem


def record(mem: dict[int, int], cid: int) -> list[int]:
    start = BASE + cid * STRIDE
    vals = []
    for off in range(STRIDE):
        a = start + off
        if a not in mem:
            raise SystemExit(f"missing class data byte at 0x{a:08X}")
        vals.append(mem[a])
    return vals


def function_blocks(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        m = FUNC_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        start = i
        end = min(len(lines) - 1, i + 800)
        for j in range(i + 1, end + 1):
            em = END_RE.match(lines[j])
            if em and em.group(1) == name:
                end = j
                break
            if j > i + 1 and FUNC_RE.match(lines[j]):
                end = j - 1
                break
        yield name, start + 1, end + 1, "\n".join(lines[start : end + 1])
        i = end + 1


def accessor_offsets():
    """Return accessor function -> true class-record offsets it references."""
    result: dict[str, set[int]] = {}
    for name, _s, _e, text in function_blocks(CLASS_ASM):
        offs: set[int] = set()
        for suffix in ANCHOR_RE.findall(text):
            addr = int("80187C" + suffix, 16)
            if BASE <= addr < BASE + STRIDE:
                offs.add(addr - BASE)
        if offs:
            result[name] = offs
    return result


def caller_map(targets: set[str]):
    out: dict[str, list[tuple[str, str, int]]] = {t: [] for t in targets}
    for path in sorted(ASM_ROOT.rglob("*.s")):
        rel = path.relative_to(ROOT).as_posix()
        for name, start, _end, text in function_blocks(path):
            for callee in CALL_RE.findall(text):
                if callee in out:
                    out[callee].append((rel, name, start))
    return out


def u16_be(rec: list[int], off: int) -> int:
    return (rec[off] << 8) | rec[off + 1]


def main() -> int:
    mem = parse_data_bytes()
    dragoon = record(mem, DRAGOON)
    danika = record(mem, DANIKA)
    hidden = record(mem, HIDDEN_DRAGOON)

    access = accessor_offsets()
    callers = caller_map(set(access))

    byte_candidates = [
        off
        for off in range(STRIDE)
        if dragoon[off] == hidden[off] and danika[off] != dragoon[off]
    ]
    word_candidates = [
        off
        for off in range(0, STRIDE - 1, 2)
        if u16_be(dragoon, off) == u16_be(hidden, off)
        and u16_be(danika, off) != u16_be(dragoon, off)
    ]

    lines: list[str] = []
    lines += [
        "Knight of Danika — Dragoon weapon compatibility evidence",
        "=========================================================",
        f"class_record_base=0x{BASE:08X}",
        f"stride=0x{STRIDE:02X}",
        f"player_dragoon=0x{DRAGOON:02X}",
        f"danika=0x{DANIKA:02X}",
        f"hidden_dragoon=0x{HIDDEN_DRAGOON:02X}",
        "",
        "Policy:",
        "- Dragoon is the compatibility baseline for greatsword pose/animation/equipment paths.",
        "- Danika identity/palette/front graphics remain Danika-specific.",
        "- Matching Dragoon values are candidates only; unknown fields are never copied blindly.",
        "",
        "Byte offsets where player Dragoon == hidden Dragoon != Danika",
        "-----------------------------------------------------------",
    ]
    for off in byte_candidates:
        lines.append(
            f"+0x{off:02X}: dragoon=0x{dragoon[off]:02X} danika=0x{danika[off]:02X} hidden=0x{hidden[off]:02X}"
        )

    lines += ["", "Aligned u16 candidates", "----------------------"]
    for off in word_candidates:
        lines.append(
            f"+0x{off:02X}: dragoon=0x{u16_be(dragoon,off):04X} "
            f"danika=0x{u16_be(danika,off):04X} hidden=0x{u16_be(hidden,off):04X}"
        )

    lines += ["", "Accessor correlation", "--------------------"]
    for func, offs in sorted(access.items()):
        hit = sorted(set(offs) & set(byte_candidates))
        if not hit:
            # A 16-bit accessor may be anchored at the first byte of a word candidate.
            hit = sorted(o for o in offs if o in word_candidates)
        if not hit:
            continue
        cs = callers.get(func, [])
        lines.append(
            f"{func}: offsets=" + ",".join(f"+0x{x:02X}" for x in sorted(offs)) +
            f" candidate_hits=" + ",".join(f"+0x{x:02X}" for x in hit) +
            f" callers={len(cs)}"
        )
        for rel, caller, line in cs[:24]:
            lines.append(f"  {rel}:{line} {caller}")
        if len(cs) > 24:
            lines.append(f"  ... {len(cs)-24} more callers")

    lines += [
        "",
        "Safety contract",
        "---------------",
        "A future greatsword patch may copy/redirect only fields whose semantics are proven by downstream code.",
        "No whole-record replacement of class 0x71 with class 0x14 is permitted.",
        "No global Dragoon resource may be overwritten.",
        "Enemy/front Danika behavior must remain vanilla.",
        "Unsupported or unresolved weapon paths must fail closed rather than dereference guessed data.",
    ]

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert BASE + DRAGOON * STRIDE == 0x801881D4
    assert BASE + DANIKA * STRIDE == 0x80189BFC
    assert BASE + HIDDEN_DRAGOON * STRIDE == 0x8018A814
    assert byte_candidates, "expected at least one Dragoon-shared candidate"
    assert word_candidates, "expected at least one aligned u16 Dragoon-shared candidate"

    print(f"Danika/Dragoon weapon compatibility scan: PASS ({len(byte_candidates)} byte, {len(word_candidates)} u16 candidates)")
    print(f"report={OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
