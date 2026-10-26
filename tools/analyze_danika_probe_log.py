#!/usr/bin/env python3
"""Summarize Knight of Danika battle-probe logs without guessing ownership.

Input lines may contain either DANIKA_SNAPSHOT or DANIKA_PROBE records. The
report groups observations by class and selector, highlights Danika/Dragoon,
and shows which record fields vary. It deliberately never labels a side as
allied/enemy: that conclusion must come from a known battle observation.
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

REC_RE = re.compile(
    r"\b(?P<kind>DANIKA_(?:SNAPSHOT|PROBE))\s+"
    r"g=(?P<g>[0-9A-Fa-f]+)\s+slot=(?P<slot>[0-9A-Fa-f]+)\s+"
    r"sel=(?P<sel>[0-9A-Fa-f]+)\s+class=(?P<classword>[0-9A-Fa-f]+)\s+"
    r"id=(?P<id>[0-9A-Fa-f]+)\s+f04=(?P<f04>[0-9A-Fa-f]+)\s+"
    r"f06=(?P<f06>[0-9A-Fa-f]+)\s+f08=(?P<f08>[0-9A-Fa-f]+)\s+"
    r"f0A=(?P<f0a>[0-9A-Fa-f]+)\s+flags=(?P<flags>[0-9A-Fa-f]+)\s+"
    r"f0E=(?P<f0e>[0-9A-Fa-f]+)\s+f10=(?P<f10>[0-9A-Fa-f]+)"
)

NAMES = {0x14: "Dragoon", 0x71: "Knight of Danika", 0x9C: "Hidden Dragoon"}
FIELDS = ("f04", "f06", "f08", "f0a", "flags", "f0e", "f10")


def parse(text: str) -> list[dict[str, int | str]]:
    rows = []
    for line in text.splitlines():
        m = REC_RE.search(line)
        if not m:
            continue
        d: dict[str, int | str] = {"kind": m.group("kind")}
        for key in ("g", "slot", "sel", "classword", "id", *FIELDS):
            d[key] = int(m.group(key), 16)
        rows.append(d)
    return rows


def summarize(rows: list[dict[str, int | str]]) -> str:
    out = []
    snapshots = sum(r["kind"] == "DANIKA_SNAPSHOT" for r in rows)
    changes = len(rows) - snapshots
    out.append("Knight of Danika battle-probe analysis")
    out.append("======================================")
    out.append(f"records={len(rows)} snapshots={snapshots} changes={changes}")
    if not rows:
        out.append("No DANIKA_SNAPSHOT/DANIKA_PROBE records found.")
        return "\n".join(out) + "\n"

    by_class: dict[int, list[dict[str, int | str]]] = defaultdict(list)
    for row in rows:
        by_class[int(row["id"])].append(row)

    out += ["", "Priority classes", "----------------"]
    for cid in (0x14, 0x71, 0x9C):
        group = by_class.get(cid, [])
        name = NAMES[cid]
        if not group:
            out.append(f"0x{cid:02X} {name}: not observed")
            continue
        selectors = sorted({int(r["sel"]) for r in group})
        locations = sorted({(int(r["g"]), int(r["slot"])) for r in group})
        out.append(
            f"0x{cid:02X} {name}: observations={len(group)} "
            f"selectors={','.join(f'0x{x:04X}' for x in selectors)} "
            f"locations={','.join(f'g{g:02X}/s{s:02X}' for g, s in locations)}"
        )

    out += ["", "Field variance by class", "-----------------------"]
    for cid in sorted(by_class):
        group = by_class[cid]
        label = NAMES.get(cid, "class")
        out.append(f"0x{cid:02X} {label}")
        for field in FIELDS:
            vals = sorted({int(r[field]) for r in group})
            rendered = ",".join(f"0x{x:04X}" for x in vals)
            out.append(f"  {field}: {rendered}")

    out += [
        "",
        "Safety interpretation",
        "---------------------",
        "This report does NOT infer allied/enemy ownership.",
        "Correlate a known player-side participant with its g/slot/selector first.",
        "Only then may that independently proven ownership signature unlock the Danika override.",
    ]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    args = ap.parse_args()
    report = summarize(parse(args.log.read_text(encoding="utf-8", errors="replace")))
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
