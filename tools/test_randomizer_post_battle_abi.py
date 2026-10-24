#!/usr/bin/env python3
"""Host contract for the Rev-A func_80172820 return ABI."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "tools/audit_randomizer_post_battle_abi_rom.py"
SOURCE = ROOT / "mods/universal-item-randomizer/src/post_battle_add.c"

spec = spec_from_file_location("post_battle_abi_audit", AUDIT)
assert spec and spec.loader
mod = module_from_spec(spec)
spec.loader.exec_module(mod)


def main() -> int:
    text = SOURCE.read_text()

    assert "RECOMP_PATCH\nvoid func_80172820(unsigned int original_id, unsigned int amount)" in text
    assert mod.JAL_WORD == 0x0C05CA08
    assert mod.EXPECTED_CALL_OFFSET == 0x002A4ED8
    assert mod.EXPECTED_CALL_VRAM == 0x802356F8
    assert mod.EXPECTED_DELAY_WORD == 0x30A500FF
    assert mod.EXPECTED_POST_WORD == 0x26220001

    # The immediate post-delay instruction writes register 2 ($v0).
    post = mod.EXPECTED_POST_WORD
    rt = (post >> 16) & 0x1F
    assert rt == 2

    # Synthetic cart scan: no hidden second caller may be accepted.
    rom = bytearray(0x2A4F00)
    rom[mod.EXPECTED_CALL_OFFSET:mod.EXPECTED_CALL_OFFSET + 4] = mod.JAL_WORD.to_bytes(4, "big")
    assert mod.find_calls(bytes(rom)) == (mod.EXPECTED_CALL_OFFSET,)
    rom[0x100:0x104] = mod.JAL_WORD.to_bytes(4, "big")
    assert mod.find_calls(bytes(rom)) == (0x100, mod.EXPECTED_CALL_OFFSET)

    print("post-battle add ABI contract: PASS (1 Rev-A caller, void return locked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
