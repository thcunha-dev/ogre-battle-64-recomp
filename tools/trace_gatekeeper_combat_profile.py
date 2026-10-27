#!/usr/bin/env python3
"""Trace Gatekeeper-vs-Dragoon class-record differences used by combat code.

Goal: narrow the safe donor surface for a playable allied Gatekeeper (0x71).
The playable Dragoon (0x14) is a structural donor for rear/player-side combat
presentation only. This report correlates differing class-record offsets with
actual class-table accessors and combat/render callers; it never patches data.

Known transition/alias tail fields +0x41..+0x46 are excluded from visual/weapon
candidate ranking because their semantics were already proven non-visual.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "asm/data/5C230.data.s"
CLASS_ASM = ROOT / "asm/40E80.s"
ASM_ROOT = ROOT / "asm"
OUT = ROOT / "gatekeeper-combat-profile-report.txt"

BASE = 0x80187C34
STRIDE = 0x48
DRAGOON = 0x14
GATEKEEPER = 0x71
HIDDEN_DRAGOON = 0x9C

REJECT = set(range(0x41, 0x47))
COMBAT_PREFIXES = ("801A", "801B", "801C", "801D")

ADDR_RE = re.compile(r"/\*\s*[0-9A-Fa-f]+\s+([0-9A-Fa-f]{8})\s*\*/\s*\.(byte|short|word)\s+(.+?)\s*$")
HEX_RE = re.compile(r"0x([0-9A-Fa-f]+)")
FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
ANCHOR_RE = re.compile(r"\bD_80187C([0-9A-Fa-f]{2})\b")


def parse_data() -> dict[int, int]:
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
            for j in range(size):
                mem[addr + n * size + j] = (val >> (8 * (size - 1 - j))) & 0xFF
    return mem


def rec(mem: dict[int, int], cid: int) -> list[int]:
    start = BASE + cid * STRIDE
    return [mem[start + i] for i in range(STRIDE)]


def functions(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        m = FUNC_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        end = min(len(lines) - 1, i + 1000)
        for j in range(i + 1, end + 1):
            em = END_RE.match(lines[j])
            if em and em.group(1) == name:
                end = j
                break
            if j > i + 1 and FUNC_RE.match(lines[j]):
                end = j - 1
                break
        yield name, i + 1, end + 1, "\n".join(lines[i:end + 1])
        i = end + 1


def accessor_map() -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    for name, _s, _e, text in functions(CLASS_ASM):
        offs = set()
        for suffix in ANCHOR_RE.findall(text):
            addr = int("80187C" + suffix, 16)
            if BASE <= addr < BASE + STRIDE:
                offs.add(addr - BASE)
        if offs:
            out[name] = offs
    return out


def callers(targets: set[str]):
    out = {t: [] for t in targets}
    for path in sorted(ASM_ROOT.rglob("*.s")):
        rel = path.relative_to(ROOT).as_posix()
        for name, start, _end, text in functions(path):
            for callee in CALL_RE.findall(text):
                if callee in out:
                    out[callee].append((rel, name, start))
    return out


def is_combat_func(name: str) -> bool:
    if not name.startswith("func_"):
        return False
    addr = name[5:13]
    return any(addr.startswith(p) for p in COMBAT_PREFIXES)


def main() -> int:
    mem = parse_data()
    d = rec(mem, DRAGOON)
    g = rec(mem, GATEKEEPER)
    h = rec(mem, HIDDEN_DRAGOON)
    access = accessor_map()
    callmap = callers(set(access))

    diffs = [i for i in range(STRIDE) if d[i] != g[i]]
    donor_matches = [i for i in diffs if d[i] == h[i] and i not in REJECT]

    rows = []
    for func, offs in access.items():
        hits = sorted(set(offs) & set(donor_matches))
        if not hits:
            continue
        cs = callmap.get(func, [])
        combat = [(rel, caller, line) for rel, caller, line in cs if is_combat_func(caller)]
        rows.append((func, hits, cs, combat))

    lines = [
        "Gatekeeper playable combat-profile trace",
        "========================================",
        f"base=0x{BASE:08X} stride=0x{STRIDE:02X}",
        f"dragoon=0x{DRAGOON:02X} gatekeeper=0x{GATEKEEPER:02X} hidden_dragoon=0x{HIDDEN_DRAGOON:02X}",
        "",
        "Candidate donor byte offsets (0x14 == 0x9C != 0x71; +0x41..+0x46 excluded)",
        "-------------------------------------------------------------------------",
    ]
    for off in donor_matches:
        lines.append(f"+0x{off:02X}: dragoon=0x{d[off]:02X} gatekeeper=0x{g[off]:02X} hidden=0x{h[off]:02X}")

    lines += ["", "Accessor/caller correlation", "---------------------------"]
    for func, hits, cs, combat in sorted(rows, key=lambda x: (-len(x[3]), x[0])):
        lines.append(
            f"{func}: candidate_hits=" + ",".join(f"+0x{x:02X}" for x in hits) +
            f" callers={len(cs)} combat_callers={len(combat)}"
        )
        for rel, caller, line in combat[:32]:
            lines.append(f"  COMBAT {rel}:{line} {caller}")
        if not combat:
            for rel, caller, line in cs[:8]:
                lines.append(f"  OTHER  {rel}:{line} {caller}")

    lines += [
        "",
        "Interpretation contract",
        "-----------------------",
        "- This report ranks evidence; it does not declare an offset visual/weapon metadata by similarity alone.",
        "- Offsets +0x41..+0x46 remain excluded as proven transition/alias/gameplay tail metadata.",
        "- A future runtime shim may borrow only offsets with a traced combat consumer and understood semantics.",
        "- Gatekeeper class ID 0x71, palette/armor identity and enemy/front behavior stay unchanged.",
    ]

    report = "\n".join(lines) + "\n"
    OUT.write_text(report, encoding="utf-8")
    print(report, end="")

    assert BASE + DRAGOON * STRIDE == 0x801881D4
    assert BASE + GATEKEEPER * STRIDE == 0x80189BFC
    assert donor_matches, "expected at least one non-tail donor candidate"
    assert all(x not in REJECT for x in donor_matches)
    print(f"Gatekeeper combat-profile trace: PASS ({len(donor_matches)} donor candidates, {len(rows)} accessor groups)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
