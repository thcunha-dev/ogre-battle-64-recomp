#!/usr/bin/env python3
"""Configuration lifecycle contract for Universal Item Randomizer.

0.3.1 intentionally snapshots randomizer config once per process. QA and docs
must therefore require a full game restart after changing seed/options; live
hot-reload is not part of the supported contract.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods/universal-item-randomizer"
SRC = MOD / "src"


def main() -> int:
    central = (SRC / "universal_item_randomizer.c").read_text()
    mapper = (SRC / "randomizer_map.c").read_text()
    shop = (SRC / "shop_stock.c").read_text()
    testing = (MOD / "TESTING.md").read_text()
    status = (MOD / "STATUS.md").read_text()

    # Config is deliberately cached for the process lifetime.
    assert "if (s_ready) return;" in central
    assert 'recomp_get_config_u32("starting_items")' in central
    assert 'recomp_get_config_u32("log")' in central
    assert "if (s_ready) return;" in mapper
    assert 'recomp_get_config_u32("seed")' in mapper
    assert 'recomp_get_config_u32("key_items")' in mapper
    assert "if (s_config_ready) return;" in shop
    assert 'recomp_get_config_u32("shops")' in shop

    # QA must not imply that changing a config field while the game is running
    # changes the active mapping. Restart wording is part of the release contract.
    for text, name in ((testing, "TESTING.md"), (status, "STATUS.md")):
        lowered = text.lower()
        assert "restart" in lowered or "reopen" in lowered, f"{name}: restart lifecycle missing"

    assert "hot-reload" in status.lower()
    assert "next launch" in status.lower() or "next process" in status.lower()

    print("universal randomizer config lifecycle: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
