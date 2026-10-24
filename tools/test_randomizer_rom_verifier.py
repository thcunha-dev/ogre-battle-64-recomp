#!/usr/bin/env python3
"""Static contract for the one-command Rev-A ROM verifier."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "tools/verify_randomizer_rev_a_rom.py"

spec = spec_from_file_location("rev_a_wrapper", WRAPPER)
assert spec and spec.loader
mod = module_from_spec(spec)
spec.loader.exec_module(mod)

EXPECTED = (
    "audit_randomizer_grant_abi_rom.py",
    "audit_randomizer_post_battle_abi_rom.py",
    "audit_randomizer_coupled_a1_abi_rom.py",
    "audit_randomizer_starting_block_abi_rom.py",
)


def main() -> int:
    text = WRAPPER.read_text()
    assert mod.AUDITORS == EXPECTED
    assert len(set(mod.AUDITORS)) == 4
    for name in EXPECTED:
        assert (ROOT / "tools" / name).is_file(), name
        assert name in text
    assert "subprocess.run([sys.executable, str(auditor), str(rom)], check=True)" in text
    assert "ROM is never copied or modified" in text
    print("one-command Rev-A ROM verifier contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
