#!/usr/bin/env python3
"""Analyze DANIKA_JOIN evidence without guessing ownership.

A descriptor/participant same-index mapping is accepted only when every live
participant that has a valid persistent-roster record agrees with the renderer
class at the same slot. One mismatch rejects the mapping. A roster-backed Danika
row is reported as an allied-ownership candidate, never silently promoted into a
patch decision.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PAT = re.compile(
    r"DANIKA_JOIN i=([0-9A-Fa-f]{2}) dclass=([0-9A-Fa-f]{2}) "
    r"dsel=([0-9A-Fa-f]{8}) pvalid=([01]) roster=([0-9A-Fa-f]{2}) "
    r"rclass=([0-9A-Fa-f]{2}) classmatch=([01])"
)


def analyze(text: str) -> tuple[list[str], int]:
    rows = []
    for m in PAT.finditer(text):
        i, dc, sel, pv, roster, rc, cm = (int(x, 16) for x in m.groups())
        rows.append((i, dc, sel, pv, roster, rc, cm))

    if not rows:
        return ["Danika join analysis: NO_DATA"], 2

    backed = [r for r in rows if r[3] and r[4] < 100 and r[5] != 0xFF]
    mismatches = [r for r in backed if r[1] != r[5] or not r[6]]
    danika = [r for r in backed if r[1] == 0x71 and r[5] == 0x71 and r[6]]

    out = [
        f"rows={len(rows)} live_roster_backed={len(backed)} mismatches={len(mismatches)}",
    ]
    if mismatches:
        out.append("same_index_roster_alignment=REJECTED")
        for r in mismatches:
            out.append(
                f"mismatch i={r[0]:02X} dclass={r[1]:02X} roster={r[4]:02X} rclass={r[5]:02X}"
            )
        return out, 1

    if len(backed) < 2:
        out.append("same_index_roster_alignment=INSUFFICIENT")
        return out, 2

    out.append("same_index_roster_alignment=SUPPORTED")
    if danika:
        for r in danika:
            out.append(
                f"roster_backed_danika_candidate i={r[0]:02X} selector={r[2]:08X} roster={r[4]:02X}"
            )
    else:
        out.append("roster_backed_danika_candidate=NONE")
    out.append(
        "safety=alignment evidence only; activate override only after persistent roster is accepted as player ownership and selector donor is independently proven"
    )
    return out, 0


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} <runtime.log>", file=sys.stderr)
        return 2
    text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    lines, rc = analyze(text)
    print("\n".join(lines))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
