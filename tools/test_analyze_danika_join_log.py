#!/usr/bin/env python3
"""Synthetic regression tests for analyze_danika_join_log.py."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tools" / "analyze_danika_join_log.py"

spec = importlib.util.spec_from_file_location("danika_join_analyzer", TARGET)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def run(text: str):
    lines, rc = mod.analyze(text)
    return "\n".join(lines), rc


supported, rc = run(
    "DANIKA_JOIN i=00 dclass=14 dsel=0000002A pvalid=1 roster=01 rclass=14 classmatch=1\n"
    "DANIKA_JOIN i=01 dclass=71 dsel=00000044 pvalid=1 roster=0F rclass=71 classmatch=1\n"
    "DANIKA_JOIN i=02 dclass=08 dsel=00000011 pvalid=0 roster=FF rclass=FF classmatch=0\n"
)
assert rc == 0, supported
assert "same_index_roster_alignment=SUPPORTED" in supported
assert "roster_backed_danika_candidate i=01 selector=00000044 roster=0F" in supported

rejected, rc = run(
    "DANIKA_JOIN i=00 dclass=14 dsel=0000002A pvalid=1 roster=01 rclass=14 classmatch=1\n"
    "DANIKA_JOIN i=01 dclass=71 dsel=00000044 pvalid=1 roster=0F rclass=14 classmatch=0\n"
)
assert rc == 1, rejected
assert "same_index_roster_alignment=REJECTED" in rejected
assert "mismatch i=01" in rejected

insufficient, rc = run(
    "DANIKA_JOIN i=00 dclass=71 dsel=00000044 pvalid=1 roster=0F rclass=71 classmatch=1\n"
)
assert rc == 2, insufficient
assert "same_index_roster_alignment=INSUFFICIENT" in insufficient

no_data, rc = run("ordinary log line\n")
assert rc == 2, no_data
assert "Danika join analysis: NO_DATA" in no_data

print("Danika descriptor/participant join analyzer tests: PASS")
