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


def documents_restart_lifecycle(text: str) -> bool:
    lowered = text.lower()
    restart = "restart" in lowered or "reopen" in lowered or "reabr" in lowered
    explicit_policy = (
        "hot-reload" in lowered
        or "hot reload" in lowered
        or "restart-required" in lowered
        or "restart required" in lowered
        or "snapshots config" in lowered
        or "snapshots randomizer configuration" in lowered
    )
    next_process = (
        "next launch" in lowered
        or "next process" in lowered
        or "full restart" in lowered
        or "fully restart" in lowered
        or "close the game completely" in lowered
    )
    return restart and (explicit_policy or next_process)


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

    # QA/docs must communicate the process-lifetime config contract, but do not
    # depend on one exact English phrase. This avoids false failures when status
    # wording is shortened without changing the supported lifecycle.
    assert documents_restart_lifecycle(testing), "TESTING.md: restart lifecycle missing"
    assert documents_restart_lifecycle(status), "STATUS.md: restart lifecycle missing"

    print("universal randomizer config lifecycle: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
