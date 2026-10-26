#!/usr/bin/env python3
"""Decode DANIKA_BANKC EXP-filter snapshots with the shared MIPS decoder."""
from __future__ import annotations

import argparse
from pathlib import Path

from analyze_danika_bankj_dump import parse as parse_shared, summarize as summarize_shared

FUNCTIONS = (
    (0x801C8B88, "func_801C8B88"),
    (0x801C8BA4, "func_801C8BA4"),
    (0x801C8C5C, "func_801C8C5C"),
    (0x801C8E50, "func_801C8E50"),
    (0x801C8EBC, "func_801C8EBC"),
    (0x801C9008, "func_801C9008(index)->participant"),
)


def parse(text: str):
    # Reuse the byte reconstruction / MIPS decoder verbatim; the wire format is
    # deliberately identical except for the BANKC/BANKJ marker.
    return parse_shared(text.replace("DANIKA_BANKC", "DANIKA_BANKJ"))


def summarize(windows) -> str:
    base = summarize_shared(windows)
    lines = [
        base.rstrip(),
        "",
        "Bank-C EXP eligibility landmarks",
        "--------------------------------",
    ]
    for address, name in FUNCTIONS:
        lines.append(f"0x{address:08X} {name}")
    lines += [
        "",
        "Ownership target",
        "----------------",
        "Bank J's EXP-award scan calls func_801C9008 for each of 20 indices and",
        "then filters the participant through the five predicates above before",
        "using its level/class-derived values. Decode the control flow at these",
        "landmarks and determine whether one predicate explicitly encodes side/team.",
        "Do not promote a predicate merely because it differs between two captures.",
    ]
    return "\n".join(lines) + "\n"


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
