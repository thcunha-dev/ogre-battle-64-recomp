#!/usr/bin/env python3
"""Run every Universal Item Randomizer Rev-A ROM audit with one command.

Usage:
    python3 verify_randomizer_rev_a_rom.py "/path/to/Ogre Battle 64 Rev 1.z64"

The ROM is never copied or modified. Each auditor independently validates the
known Rev-A SHA-1 before checking its own structural contract.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
AUDITORS = (
    "audit_randomizer_grant_abi_rom.py",
    "audit_randomizer_post_battle_abi_rom.py",
    "audit_randomizer_coupled_a1_abi_rom.py",
    "audit_randomizer_starting_block_abi_rom.py",
)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_randomizer_rev_a_rom.py <Rev-A .z64>")

    rom = Path(sys.argv[1]).expanduser().resolve()
    if not rom.is_file():
        raise SystemExit(f"ROM not found: {rom}")

    for name in AUDITORS:
        auditor = ROOT / name
        if not auditor.is_file():
            raise SystemExit(f"missing ROM auditor: {name}")
        print(f"==> {name}", flush=True)
        subprocess.run([sys.executable, str(auditor), str(rom)], check=True)

    print(f"Universal Item Randomizer Rev-A ROM verification: PASS ({len(AUDITORS)} audits)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
