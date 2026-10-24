#!/usr/bin/env python3
"""Host contract for Rev-A central-grant a1 caller classification."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "tools/audit_randomizer_coupled_a1_abi_rom.py"
SOURCE = ROOT / "mods/universal-item-randomizer/src/universal_item_randomizer.c"

spec = spec_from_file_location("coupled_a1_audit", AUDIT)
assert spec and spec.loader
mod = module_from_spec(spec)
spec.loader.exec_module(mod)


def main() -> int:
    text = SOURCE.read_text()

    assert len(mod.EXPECTED_CALL_OFFSETS) == 46
    assert mod.COUPLED_A1_ONE_OFFSETS == (0x19607C, 0x197220)
    assert mod.COUPLED_A1_ONE_RAS == (0x80215BF4, 0x80216D98)
    assert mod.A1_ZERO_WORD == 0x00002821
    assert mod.A1_ONE_WORD == 0x24050001

    for token in (
        "#define RA_TUTORIAL_SETUP_R      0x80215BF4u",
        "#define RA_UNIT_LOADOUT_R        0x80216D98u",
        "static int caller_is_coupled_unit_grant",
        "caller_ra == RA_TUTORIAL_SETUP_R",
        "caller_ra == RA_UNIT_LOADOUT_R",
        "if (caller_is_coupled_unit_grant(caller_ra)) return 0;",
        "coupled Bank-R unit/setup grant left vanilla",
    ):
        assert token in text, token

    starting = text.split("static int caller_is_starting_grant", 1)[1]
    starting = starting.split("static int caller_is_coupled_unit_grant", 1)[0]
    assert "RA_TUTORIAL_SETUP_R" not in starting
    assert "RA_UNIT_LOADOUT_R" not in starting
    assert "RA_STARTING_R_LO" in starting and "RA_STARTING_R_HI" in starting

    print("coupled a1 caller contract: PASS (both a1=1 Bank-R grants fail-closed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
