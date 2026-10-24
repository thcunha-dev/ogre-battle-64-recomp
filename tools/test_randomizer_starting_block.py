#!/usr/bin/env python3
"""Host contract for the only STARTING ITEMS opt-in block."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "tools/audit_randomizer_starting_block_abi_rom.py"
SOURCE = ROOT / "mods/universal-item-randomizer/src/universal_item_randomizer.c"

spec = spec_from_file_location("starting_block_audit", AUDIT)
assert spec and spec.loader
mod = module_from_spec(spec)
spec.loader.exec_module(mod)


def main() -> int:
    text = SOURCE.read_text()

    assert len(mod.SAFE_CALL_OFFSETS) == 40
    assert mod.SAFE_CALL_OFFSETS[0] == 0x1974F8
    assert mod.SAFE_CALL_OFFSETS[-1] == 0x1976D4
    assert mod.RA_LO == 0x80217070
    assert mod.RA_HI_EXCLUSIVE == 0x8021724C
    assert mod.A1_ZERO_WORD == 0x00002821

    for token in (
        "#define RA_STARTING_R_LO         0x80217070u",
        "#define RA_STARTING_R_HI         0x8021724Cu",
        "return caller_ra >= RA_STARTING_R_LO && caller_ra < RA_STARTING_R_HI;",
        "if (caller_is_starting_grant(caller_ra)) return s_starting_items_enabled != 0u;",
    ):
        assert token in text, token

    # The two coupled a1=1 RAs must sit strictly outside this opt-in range.
    assert not (mod.RA_LO <= 0x80215BF4 < mod.RA_HI_EXCLUSIVE)
    assert not (mod.RA_LO <= 0x80216D98 < mod.RA_HI_EXCLUSIVE)

    print("safe starting block contract: PASS (40 literal a1=0 grants only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
