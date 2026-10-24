#!/usr/bin/env python3
"""Add the Rev-A Bank N grant symbol needed by the universal randomizer.

`N64Recomp --dump-context` for the main game only knows functions from the main
ELF.  `func_ovlN_801DC740` lives in streamed Bank N (record 7), so code mods
that replace it need one extra reference section in `mods/reference/dump.toml`.

This helper is intentionally tiny and idempotent.  It never invents data from a
save or ROM at runtime; it only records the already-audited Rev-A section and
function coordinates used by the generated Bank N unit.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import tomllib

BANK_NAME = ".bankN_record7"
BANK_ROM = 0x00101D00
BANK_VRAM = 0x801AD5C0
BANK_SIZE = 0x00043530
FUNC_NAME = "func_ovlN_801DC740"
FUNC_VRAM = 0x801DC740
FUNC_SIZE = 0x000001F0

BLOCK = f'''\n\n# Universal Item Randomizer: Rev-A Bank N record 7.\n# Main-unit --dump-context cannot see streamed-bank functions.\n[[section]]\nname = "{BANK_NAME}"\nrom = 0x{BANK_ROM:08X}\nvram = 0x{BANK_VRAM:08X}\nsize = 0x{BANK_SIZE:X}\nfunctions = [\n  {{ name = "{FUNC_NAME}", vram = 0x{FUNC_VRAM:08X}, size = 0x{FUNC_SIZE:X} }},\n]\n'''


def validate_existing(doc: dict) -> bool:
    for section in doc.get("section", []):
        funcs = section.get("functions", [])
        for func in funcs:
            if func.get("name") != FUNC_NAME:
                continue
            expected_section = (BANK_ROM, BANK_VRAM, BANK_SIZE)
            actual_section = (
                section.get("rom"),
                section.get("vram"),
                section.get("size"),
            )
            if actual_section != expected_section:
                raise SystemExit(
                    f"{FUNC_NAME}: conflicting section coordinates: "
                    f"got {actual_section!r}, expected {expected_section!r}"
                )
            actual_func = (func.get("vram"), func.get("size"))
            expected_func = (FUNC_VRAM, FUNC_SIZE)
            if actual_func != expected_func:
                raise SystemExit(
                    f"{FUNC_NAME}: conflicting function coordinates: "
                    f"got {actual_func!r}, expected {expected_func!r}"
                )
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "dump",
        nargs="?",
        default="mods/reference/dump.toml",
        help="N64Recomp function reference dump to augment",
    )
    args = parser.parse_args()

    path = Path(args.dump)
    if not path.is_file():
        raise SystemExit(f"reference dump not found: {path}")

    text = path.read_text(encoding="utf-8")
    doc = tomllib.loads(text)
    if validate_existing(doc):
        print(f"==> {FUNC_NAME} already present in {path}")
        return 0

    # A main-unit dump should not already own Bank N's ROM section.  Refuse to
    # silently create a duplicate section if the dump format changes later.
    for section in doc.get("section", []):
        if section.get("rom") == BANK_ROM:
            raise SystemExit(
                f"section ROM 0x{BANK_ROM:08X} already exists without {FUNC_NAME}; "
                "update ensure_randomizer_mod_syms.py instead of duplicating it"
            )

    path.write_text(text.rstrip() + BLOCK, encoding="utf-8")
    # Parse the final file once more so a formatting mistake fails the build.
    final_doc = tomllib.loads(path.read_text(encoding="utf-8"))
    if not validate_existing(final_doc):
        raise SystemExit(f"failed to add {FUNC_NAME} to {path}")
    print(f"==> added {FUNC_NAME} to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
