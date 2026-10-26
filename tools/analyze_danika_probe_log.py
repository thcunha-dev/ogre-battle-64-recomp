#!/usr/bin/env python3
"""Summarize Knight of Danika battle-probe logs without guessing ownership.

The probe now emits two independent streams:
  * DANIKA_SNAPSHOT / DANIKA_PROBE: renderer-facing visual records;
  * DANIKA_PART_SNAPSHOT / DANIKA_PART: live battle participants linked to the
    persistent character roster through the verified +0xF6 roster index.

A unique class on both streams may be reported as a 1:1 bridge candidate.  This
is useful for recovering a player Dragoon selector, but it is deliberately NOT
promoted to a generic allied/enemy discriminator.
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

PART_RE = re.compile(
    r"\b(?P<kind>DANIKA_PART(?:_SNAPSHOT)?)\s+"
    r"i=(?P<i>[0-9A-Fa-f]+)\s+roster=(?P<roster>[0-9A-Fa-f]+)\s+"
    r"rclass=(?P<rclass>[0-9A-Fa-f]+)\s+lvl=(?P<lvl>[0-9A-Fa-f]+)\s+"
    r"exp=(?P<exp>[0-9A-Fa-f]+)\s+head=(?P<head>[0-9A-Fa-f]+)\s+"
    r"tail=(?P<tail>[0-9A-Fa-f]+)"
)

NAMES = {0x14: "Dragoon", 0x71: "Knight of Danika", 0x9C: "Hidden Dragoon"}
FIELDS = ("f04", "f06", "f08", "f0a", "flags", "f0e", "f10")
Location = tuple[int, int]


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


def parse_participants(text: str) -> list[dict[str, int | str]]:
    rows = []
    for line in text.splitlines():
        m = PART_RE.search(line)
        if not m:
            continue
        d: dict[str, int | str] = {"kind": m.group("kind")}
        for key in ("i", "roster", "rclass", "lvl", "exp"):
            d[key] = int(m.group(key), 16)
        d["head"] = m.group("head").upper()
        d["tail"] = m.group("tail").upper()
        rows.append(d)
    return rows


def parse_location(value: str) -> Location:
    try:
        g_text, slot_text = value.split(":", 1)
        return int(g_text, 16), int(slot_text, 16)
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError(
            f"invalid location {value!r}; expected hexadecimal G:SLOT, e.g. 03:01"
        ) from exc


def rows_at(rows: list[dict[str, int | str]], locations: set[Location]):
    return [r for r in rows if (int(r["g"]), int(r["slot"])) in locations]


def candidate_discriminators(
    ally_rows: list[dict[str, int | str]],
    enemy_rows: list[dict[str, int | str]],
) -> list[tuple[int, str, set[int], set[int]]]:
    """Return class-scoped fields with disjoint values in labeled sides."""
    ally_classes = {int(r["id"]) for r in ally_rows}
    enemy_classes = {int(r["id"]) for r in enemy_rows}
    shared = sorted(ally_classes & enemy_classes)
    result = []
    for cid in shared:
        arows = [r for r in ally_rows if int(r["id"]) == cid]
        erows = [r for r in enemy_rows if int(r["id"]) == cid]
        for field in FIELDS:
            av = {int(r[field]) for r in arows}
            ev = {int(r[field]) for r in erows}
            if av and ev and av.isdisjoint(ev):
                result.append((cid, field, av, ev))
    return result


def unique_class_bridges(
    rows: list[dict[str, int | str]],
    participants: list[dict[str, int | str]],
) -> list[tuple[int, int, int, Location, int]]:
    """Return conservative 1:1 persistent-roster -> visual class correlations.

    A bridge requires exactly one live participant index backed by a valid
    persistent-roster class and exactly one visual G:SLOT plus selector for that
    same class over the entire capture.  It is a correlation aid, not ownership
    semantics.
    """
    part_by_class: dict[int, set[tuple[int, int]]] = defaultdict(set)
    visual_by_class: dict[int, set[tuple[int, int, int]]] = defaultdict(set)

    for p in participants:
        cid = int(p["rclass"])
        roster = int(p["roster"])
        if cid in (0x00, 0xFF) or roster >= 100:
            continue
        part_by_class[cid].add((int(p["i"]), roster))

    for r in rows:
        visual_by_class[int(r["id"])].add(
            (int(r["g"]), int(r["slot"]), int(r["sel"]))
        )

    out = []
    for cid in sorted(part_by_class.keys() & visual_by_class.keys()):
        parts = part_by_class[cid]
        visuals = visual_by_class[cid]
        if len(parts) != 1 or len(visuals) != 1:
            continue
        (index, roster), = parts
        (g, slot, selector), = visuals
        out.append((cid, index, roster, (g, slot), selector))
    return out


def fmt_values(values: set[int]) -> str:
    return ",".join(f"0x{x:04X}" for x in sorted(values))


def summarize(
    rows: list[dict[str, int | str]],
    ally_locations: set[Location] | None = None,
    enemy_locations: set[Location] | None = None,
    participants: list[dict[str, int | str]] | None = None,
) -> str:
    ally_locations = ally_locations or set()
    enemy_locations = enemy_locations or set()
    participants = participants or []
    out = []
    snapshots = sum(r["kind"] == "DANIKA_SNAPSHOT" for r in rows)
    changes = len(rows) - snapshots
    part_snapshots = sum(r["kind"] == "DANIKA_PART_SNAPSHOT" for r in participants)
    part_changes = len(participants) - part_snapshots
    out.append("Knight of Danika battle-probe analysis")
    out.append("======================================")
    out.append(f"records={len(rows)} snapshots={snapshots} changes={changes}")
    out.append(
        f"participants={len(participants)} snapshots={part_snapshots} changes={part_changes}"
    )
    if not rows and not participants:
        out.append("No DANIKA_SNAPSHOT/DANIKA_PROBE or DANIKA_PART records found.")
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

    if rows:
        out += ["", "Field variance by class", "-----------------------"]
        for cid in sorted(by_class):
            group = by_class[cid]
            label = NAMES.get(cid, "class")
            out.append(f"0x{cid:02X} {label}")
            for field in FIELDS:
                vals = sorted({int(r[field]) for r in group})
                rendered = ",".join(f"0x{x:04X}" for x in vals)
                out.append(f"  {field}: {rendered}")

    if participants:
        out += ["", "Persistent-roster participant evidence", "--------------------------------------"]
        latest_by_index: dict[int, dict[str, int | str]] = {}
        for p in participants:
            latest_by_index[int(p["i"])] = p
        for index in sorted(latest_by_index):
            p = latest_by_index[index]
            roster = int(p["roster"])
            cid = int(p["rclass"])
            label = NAMES.get(cid, "class") if cid not in (0x00, 0xFF) else "unresolved"
            backed = roster < 100 and cid not in (0x00, 0xFF)
            out.append(
                f"participant=0x{index:02X} roster=0x{roster:02X} "
                f"rclass=0x{cid:02X} {label} roster_backed={'yes' if backed else 'no'} "
                f"tail={p['tail']}"
            )

        bridges = unique_class_bridges(rows, participants)
        out += ["", "Unique-class cross-structure bridges", "------------------------------------"]
        if not bridges:
            out.append("No unambiguous 1:1 roster-class -> visual-record bridge in this capture.")
        else:
            for cid, index, roster, (g, slot), selector in bridges:
                label = NAMES.get(cid, "class")
                out.append(
                    f"BRIDGE_CANDIDATE class=0x{cid:02X} {label} "
                    f"participant=0x{index:02X} roster=0x{roster:02X} "
                    f"visual=g{g:02X}/s{slot:02X} selector=0x{selector:04X}"
                )
            dragoon = {sel for cid, _, _, _, sel in bridges if cid == 0x14}
            out.append(
                "candidate_roster_backed_dragoon_selectors="
                + (fmt_values(dragoon) if dragoon else "<none>")
            )
            out.append(
                "A bridge proves a capture-local identity correlation only; it does not by itself "
                "prove a global allied/enemy field."
            )

    if ally_locations or enemy_locations:
        allies = rows_at(rows, ally_locations)
        enemies = rows_at(rows, enemy_locations)
        out += ["", "Labeled runtime evidence", "------------------------"]
        out.append(f"ally_locations={len(ally_locations)} matching_records={len(allies)}")
        out.append(f"enemy_locations={len(enemy_locations)} matching_records={len(enemies)}")

        ally_dragoon = {int(r["sel"]) for r in allies if int(r["id"]) == 0x14}
        enemy_danika = {int(r["sel"]) for r in enemies if int(r["id"]) == 0x71}
        out.append(
            "known_allied_dragoon_selectors="
            + (fmt_values(ally_dragoon) if ally_dragoon else "<none>")
        )
        out.append(
            "known_enemy_danika_selectors="
            + (fmt_values(enemy_danika) if enemy_danika else "<none>")
        )

        candidates = candidate_discriminators(allies, enemies)
        out += ["", "Same-class ownership candidates", "-------------------------------"]
        if not candidates:
            out.append(
                "No same-class ally/enemy field discriminator was established by these labels."
            )
            out.append(
                "Do not infer ownership from cross-class differences or record position alone."
            )
        else:
            for cid, field, av, ev in candidates:
                label = NAMES.get(cid, "class")
                out.append(
                    f"CANDIDATE class=0x{cid:02X} {label} field={field} "
                    f"ally={fmt_values(av)} enemy={fmt_values(ev)}"
                )
            out.append(
                "Candidates are correlations from this capture, not yet a global ownership proof."
            )

    out += [
        "",
        "Safety interpretation",
        "---------------------",
        "A persistent-roster link is identity evidence, not automatically an allied/enemy flag.",
        "Unlabeled visual records never imply allied/enemy ownership.",
        "Even labeled candidates must be reproduced before unlocking the Danika override.",
        "Only independently proven ownership may activate the allied visual-selector substitution.",
    ]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument(
        "--ally", action="append", default=[], type=parse_location, metavar="G:SLOT",
        help="known player/allied record location from visible gameplay; repeatable",
    )
    ap.add_argument(
        "--enemy", action="append", default=[], type=parse_location, metavar="G:SLOT",
        help="known enemy record location from visible gameplay; repeatable",
    )
    args = ap.parse_args()
    text = args.log.read_text(encoding="utf-8", errors="replace")
    report = summarize(
        parse(text),
        set(args.ally),
        set(args.enemy),
        parse_participants(text),
    )
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
