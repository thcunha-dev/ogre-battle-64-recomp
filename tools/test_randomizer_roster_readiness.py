#!/usr/bin/env python3
"""Partial-roster readiness contract for transient +0x02 repair.

The native-style use-count rebuild must not run while only one half of the
roster has been reconstructed during load/map setup. Both character and unit
rosters must be populated. Until then the repair invalidates its inventory-id
shadow so the first fully ready frame performs a complete rebuild.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "mods/universal-item-randomizer/src/use_repair.c").read_text()


def ready(chars: int, units: int) -> bool:
    return chars != 0 and units != 0


def tick(chars: int, units: int, shadow_ready: bool, ids_changed: bool) -> tuple[bool, bool]:
    """Return (new_shadow_ready, rebuilt) for the C control-flow model."""
    if not ready(chars, units):
        return False, False
    if not shadow_ready or ids_changed:
        return True, True
    return True, False


def main() -> int:
    # Static source contract: readiness is AND, not OR, and both force/tick
    # paths fail closed by clearing shadow readiness while the roster is partial.
    assert "return roster_chars() != 0u && roster_units() != 0u;" in SOURCE
    assert SOURCE.count("if (!roster_populated())") == 2
    assert SOURCE.count("s_shadow_ready = 0u;") >= 2

    force = SOURCE.split("void universal_item_randomizer_force_use_repair", 1)[1]
    force = force.split("void universal_item_randomizer_use_repair_tick_impl", 1)[0]
    assert "if (!roster_populated())" in force
    assert "s_shadow_ready = 0u;" in force
    assert "full_repair_and_snapshot();" in force

    frame = SOURCE.split("void universal_item_randomizer_use_repair_tick_impl", 1)[1]
    assert "if (!roster_populated())" in frame
    assert "s_shadow_ready = 0u;" in frame
    assert "if (!s_shadow_ready || ids_changed())" in frame

    # Partial-load states must never rebuild.
    for chars, units in ((0, 0), (1, 0), (25, 0), (0, 1), (0, 30)):
        new_shadow, rebuilt = tick(chars, units, True, True)
        assert not new_shadow
        assert not rebuilt

    # The first frame after both halves become available must rebuild even when
    # inventory ids happen to equal a stale previous shadow, because partial
    # state forcibly cleared the readiness flag.
    shadow, rebuilt = tick(1, 0, True, False)
    assert not shadow and not rebuilt
    shadow, rebuilt = tick(1, 1, shadow, False)
    assert shadow and rebuilt

    # Once ready and snapshotted, stable inventory should not be rewritten each
    # frame; a later id change triggers exactly another rebuild.
    shadow, rebuilt = tick(10, 8, True, False)
    assert shadow and not rebuilt
    shadow, rebuilt = tick(10, 8, shadow, True)
    assert shadow and rebuilt

    print("universal randomizer partial-roster readiness: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
