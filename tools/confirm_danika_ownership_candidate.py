#!/usr/bin/env python3
"""Cross-capture confirmation for Danika ownership bit candidates.

Input files are reports produced by analyze_danika_ownership.py. A candidate is
reported as REPRODUCED only when the exact byte offset, bit mask and ally/enemy
polarity occur in at least two distinct captures. This tool does not modify the
runtime gate and does not promote a candidate into game code automatically.
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

BIT_RE = re.compile(
    r"\bBIT_CANDIDATE\s+off=0x(?P<off>[0-9A-Fa-f]+)\s+"
    r"mask=0x(?P<mask>[0-9A-Fa-f]+)\s+"
    r"ally=(?P<ally>[01])\s+enemy=(?P<enemy>[01])"
)


@dataclass(frozen=True, order=True)
class Candidate:
    offset: int
    mask: int
    ally: int
    enemy: int


def parse_report(text: str) -> set[Candidate]:
    found: set[Candidate] = set()
    for match in BIT_RE.finditer(text):
        candidate = Candidate(
            offset=int(match.group("off"), 16),
            mask=int(match.group("mask"), 16),
            ally=int(match.group("ally")),
            enemy=int(match.group("enemy")),
        )
        if candidate.ally == candidate.enemy:
            continue
        if candidate.mask == 0 or candidate.mask & (candidate.mask - 1):
            continue
        found.add(candidate)
    return found


def confirm(captures: dict[str, set[Candidate]], minimum: int = 2):
    occurrences: dict[Candidate, set[str]] = defaultdict(set)
    for name, candidates in captures.items():
        for candidate in candidates:
            occurrences[candidate].add(name)
    return {
        candidate: names
        for candidate, names in occurrences.items()
        if len(names) >= minimum
    }


def report(captures: dict[str, set[Candidate]], minimum: int = 2) -> str:
    reproduced = confirm(captures, minimum)
    out = [
        "Knight of Danika ownership cross-capture confirmation",
        "====================================================",
        f"captures={len(captures)}",
        f"minimum_distinct_captures={minimum}",
        f"reproduced_candidates={len(reproduced)}",
        "",
    ]

    if len(captures) < minimum:
        out.append("INCOMPLETE: not enough distinct captures to reproduce any candidate.")
    elif not reproduced:
        out.append("NO_PROMOTION: no bit candidate reproduced with identical polarity.")
    else:
        out += ["Reproduced candidates", "---------------------"]
        for candidate, names in sorted(reproduced.items()):
            out.append(
                f"REPRODUCED off=0x{candidate.offset:02X} mask=0x{candidate.mask:02X} "
                f"ally={candidate.ally} enemy={candidate.enemy} "
                f"captures={len(names)} [{','.join(sorted(names))}]"
            )
        out += [
            "",
            "A reproduced bit is still evidence, not automatic runtime permission.",
            "Before encoding it, corroborate its semantics with code/dataflow (preferably",
            "the bank-C battle filters) and then set ownership_proven only at the point",
            "where that runtime predicate has been independently validated.",
        ]

    return "\n".join(out) + "\n"


def self_test() -> None:
    a = parse_report(
        "BIT_CANDIDATE off=0x40 mask=0x80 ally=1 enemy=0\n"
        "BIT_CANDIDATE off=0x44 mask=0x02 ally=0 enemy=1\n"
    )
    b = parse_report(
        "BIT_CANDIDATE off=0x40 mask=0x80 ally=1 enemy=0\n"
        "BIT_CANDIDATE off=0x44 mask=0x02 ally=1 enemy=0\n"
    )
    c = parse_report("BIT_CANDIDATE off=0x40 mask=0x80 ally=1 enemy=0\n")
    reproduced = confirm({"a": a, "b": b, "c": c}, 2)
    key = Candidate(0x40, 0x80, 1, 0)
    assert reproduced[key] == {"a", "b", "c"}
    assert Candidate(0x44, 0x02, 0, 1) not in reproduced
    assert Candidate(0x44, 0x02, 1, 0) not in reproduced
    assert not parse_report("BIT_CANDIDATE off=0x40 mask=0x03 ally=1 enemy=0")
    assert "REPRODUCED off=0x40 mask=0x80" in report({"a": a, "b": b}, 2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="*", type=Path)
    parser.add_argument("--minimum", type=int, default=2)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.minimum < 2:
        parser.error("--minimum must be at least 2")

    if args.self_test:
        self_test()
        print("Danika ownership cross-capture self-test: PASS")
        if not args.reports:
            return 0

    if not args.reports:
        parser.error("provide at least one ownership analyzer report")

    captures = {
        path.name: parse_report(path.read_text(encoding="utf-8", errors="replace"))
        for path in args.reports
    }
    print(report(captures, args.minimum), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
