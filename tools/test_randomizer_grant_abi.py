#!/usr/bin/env python3
"""Host contract for the Rev-A central grant ABI audit."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "tools/audit_randomizer_grant_abi_rom.py"
SOURCE = ROOT / "mods/universal-item-randomizer/src/universal_item_randomizer.c"

spec = spec_from_file_location("grant_abi_audit", AUDIT)
assert spec and spec.loader
mod = module_from_spec(spec)
spec.loader.exec_module(mod)


def word_bytes(*words: int) -> bytes:
    return b"".join(w.to_bytes(4, "big") for w in words)


def main() -> int:
    text = SOURCE.read_text()

    # The replacement deliberately does not promise a return value.
    assert "RECOMP_PATCH\nvoid func_ovlN_801DC740(unsigned int item_word, unsigned int ignored)" in text

    # Rev-A whole-cart facts captured by the ROM-assisted auditor.
    assert mod.JAL_WORD == 0x0C0771D0
    assert len(mod.EXPECTED_CALL_OFFSETS) == 46
    assert mod.EXPECTED_CALL_OFFSETS[:4] == (0x1025E8, 0x1028C8, 0x110074, 0x139B1C)
    assert mod.EXPECTED_CALL_OFFSETS[4] == 0x19607C
    assert mod.EXPECTED_CALL_OFFSETS[-1] == 0x1976D4
    assert len(set(mod.EXPECTED_CALL_OFFSETS)) == 46

    # Exercise decoder semantics used by the optional real-ROM scan.
    reads, writes, kind = mod.decode_rw(0x00421021)  # addu v0,v0,v0
    assert 2 in reads and 2 in writes and kind == "normal"

    reads, writes, kind = mod.decode_rw(0x3C02801F)  # lui v0,0x801f
    assert 2 not in reads and 2 in writes

    reads, writes, kind = mod.decode_rw(0x10400001)  # beq v0,zero,+1
    assert 2 in reads and kind == "branch"

    # Minimal synthetic path: immediate overwrite is safe.
    rom = bytearray(0x110000)
    off = 0x1025E8
    rom[off:off + 4] = mod.JAL_WORD.to_bytes(4, "big")
    rom[off + 4:off + 8] = (0).to_bytes(4, "big")
    rom[off + 8:off + 12] = (0x3C02801F).to_bytes(4, "big")
    safe, _ = mod.v0_safe_after_call(bytes(rom), off)
    assert safe

    # Minimal synthetic path: reading v0 before a clobber must fail closed.
    rom[off + 8:off + 12] = (0x10400001).to_bytes(4, "big")
    safe, reason = mod.v0_safe_after_call(bytes(rom), off)
    assert not safe and "reads v0" in reason

    print("central grant ABI contract: PASS (46 Rev-A callers, void return locked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
