#!/usr/bin/env python3
"""Fail-closed ownership analysis for Knight of Danika battle captures.

This tool never guesses which side a participant belongs to. The operator labels
known participant indices from visible gameplay with --ally-participant and
--enemy-participant. The report then checks whether the persistent-roster index
space observed by the two labels is cleanly separable.

A clean result is evidence for a roster-range ownership rule, not permission to
patch by itself. Reproduce it in more than one battle before enabling the
playable-Danika presentation override.
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

DANIKA_CLASS_ID = 0x71
DRAGOON_CLASS_ID = 0x14
PERSISTENT_ROSTER_STRIDE = 0x38

PART_RE = re.compile(
    r"\b(?P<kind>DANIKA_PART(?:_SNAPSHOT)?)\s+"
    r"i=(?P<i>[0-9A-Fa-f]+)\s+roster=(?P<roster>[0-9A-Fa-f]+)\s+"
    r"rclass=(?P<rclass>[0-9A-Fa-f]+)\s+lvl=(?P<lvl>[0-9A-Fa-f]+)\s+"
    r"exp=(?P<exp>[0-9A-Fa-f]+)\s+head=(?P<head>[0-9A-Fa-f]+)\s+"
    r"tail=(?P<tail>[0-9A-Fa-f]+)"
)


@dataclass(frozen=True)
class Participant:
    index: int
    roster: int
    class_id: int
    level: int
    exp: int
    head: str
    tail: str


def parse_hex(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError:
        try:
            return int(value, 16)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"invalid integer/hex value: {value}") from exc


def parse_participants(text: str) -> list[Participant]:
    latest: dict[int, Participant] = {}
    for line in text.splitlines():
        match = PART_RE.search(line)
        if not match:
            continue
        p = Participant(
            index=int(match.group("i"), 16),
            roster=int(match.group("roster"), 16),
            class_id=int(match.group("rclass"), 16),
            level=int(match.group("lvl"), 16),
            exp=int(match.group("exp"), 16),
            head=match.group("head").upper(),
            tail=match.group("tail").upper(),
        )
        latest[p.index] = p
    return [latest[i] for i in sorted(latest)]


def labeled_rows(
    participants: list[Participant], indices: set[int]
) -> list[Participant]:
    return [p for p in participants if p.index in indices]


def contiguous_range(values: set[int]) -> tuple[int, int] | None:
    if not values:
        return None
    lo, hi = min(values), max(values)
    if values != set(range(lo, hi + 1)):
        return None
    return lo, hi


def disjoint_roster_evidence(
    allies: list[Participant], enemies: list[Participant]
) -> tuple[bool, tuple[int, int] | None, tuple[int, int] | None]:
    ally_values = {p.roster for p in allies}
    enemy_values = {p.roster for p in enemies}
    ally_range = contiguous_range(ally_values)
    enemy_range = contiguous_range(enemy_values)
    clean = bool(
        ally_values
        and enemy_values
        and ally_values.isdisjoint(enemy_values)
        and ally_range is not None
        and enemy_range is not None
        and (ally_range[1] < enemy_range[0] or enemy_range[1] < ally_range[0])
    )
    return clean, ally_range, enemy_range


def ownership_for_index(
    index: int, ally_indices: set[int], enemy_indices: set[int]
) -> str:
    if index in ally_indices and index in enemy_indices:
        return "CONFLICT"
    if index in ally_indices:
        return "ALLY"
    if index in enemy_indices:
        return "ENEMY"
    return "UNKNOWN"


def override_eligible(class_id: int, ownership: str) -> bool:
    return class_id == DANIKA_CLASS_ID and ownership == "ALLY"


def fmt_range(value: tuple[int, int] | None) -> str:
    if value is None:
        return "<not-contiguous>"
    return f"0x{value[0]:02X}..0x{value[1]:02X}"


def report(
    participants: list[Participant],
    ally_indices: set[int],
    enemy_indices: set[int],
) -> str:
    out = [
        "Knight of Danika ownership capture analysis",
        "===========================================",
        f"participants={len(participants)}",
        f"persistent_roster_stride=0x{PERSISTENT_ROSTER_STRIDE:X}",
    ]

    conflicts = ally_indices & enemy_indices
    missing = (ally_indices | enemy_indices) - {p.index for p in participants}
    allies = labeled_rows(participants, ally_indices - conflicts)
    enemies = labeled_rows(participants, enemy_indices - conflicts)
    clean, ally_range, enemy_range = disjoint_roster_evidence(allies, enemies)

    if conflicts:
        out.append("label_conflicts=" + ",".join(f"0x{x:02X}" for x in sorted(conflicts)))
    if missing:
        out.append("missing_labeled_indices=" + ",".join(f"0x{x:02X}" for x in sorted(missing)))

    out += [
        f"labeled_allies={len(allies)} roster_range={fmt_range(ally_range)}",
        f"labeled_enemies={len(enemies)} roster_range={fmt_range(enemy_range)}",
        f"roster_ranges_cleanly_separable={'yes' if clean else 'no'}",
        "",
        "Participants",
        "------------",
    ]

    for p in participants:
        ownership = ownership_for_index(p.index, ally_indices, enemy_indices)
        eligible = override_eligible(p.class_id, ownership)
        label = "Dragoon" if p.class_id == DRAGOON_CLASS_ID else (
            "Knight of Danika" if p.class_id == DANIKA_CLASS_ID else "class"
        )
        out.append(
            f"i=0x{p.index:02X} ownership={ownership:<8} roster=0x{p.roster:02X} "
            f"class=0x{p.class_id:02X} {label} "
            f"danika_override_eligible={'yes' if eligible else 'no'}"
        )

    out += ["", "Interpretation", "--------------"]
    if conflicts:
        out.append("FAIL: conflicting side labels exist. Ownership remains UNKNOWN for patching.")
    elif missing:
        out.append("FAIL: one or more labeled participants were absent from the capture.")
    elif len(allies) < 2 or len(enemies) < 2:
        out.append("INCOMPLETE: require at least two known allies and two known enemies.")
    elif not clean:
        out.append("INCOMPLETE: labeled roster indices do not prove a clean side range.")
    else:
        out.append("EVIDENCE: this capture has clean, disjoint contiguous roster ranges.")
        out.append("Reproduce in another battle before encoding the range as ownership logic.")

    out.append(
        "Fail-closed rule remains: only class 0x71 + positively proven ALLY may borrow "
        "Dragoon 0x14 presentation."
    )
    return "\n".join(out) + "\n"


def self_test() -> None:
    sample = [
        Participant(0, 0, DRAGOON_CLASS_ID, 1, 0, "", ""),
        Participant(1, 1, 0x10, 1, 0, "", ""),
        Participant(2, 8, DANIKA_CLASS_ID, 1, 0, "", ""),
        Participant(3, 9, 0x11, 1, 0, "", ""),
    ]
    clean, arange, erange = disjoint_roster_evidence(sample[:2], sample[2:])
    assert clean
    assert arange == (0, 1)
    assert erange == (8, 9)
    assert override_eligible(DANIKA_CLASS_ID, "ALLY")
    assert not override_eligible(DANIKA_CLASS_ID, "ENEMY")
    assert not override_eligible(DANIKA_CLASS_ID, "UNKNOWN")
    assert not override_eligible(DRAGOON_CLASS_ID, "ALLY")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", nargs="?", type=Path)
    parser.add_argument(
        "--ally-participant", action="append", default=[], type=parse_hex, metavar="INDEX",
        help="known allied participant index from visible gameplay; repeatable",
    )
    parser.add_argument(
        "--enemy-participant", action="append", default=[], type=parse_hex, metavar="INDEX",
        help="known enemy participant index from visible gameplay; repeatable",
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        print("Danika ownership analyzer self-test: PASS")
        if args.log is None:
            return 0

    if args.log is None:
        parser.error("log is required unless --self-test is used")

    text = args.log.read_text(encoding="utf-8", errors="replace")
    print(
        report(
            parse_participants(text),
            set(args.ally_participant),
            set(args.enemy_participant),
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
