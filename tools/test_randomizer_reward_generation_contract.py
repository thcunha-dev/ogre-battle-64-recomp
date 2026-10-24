#!/usr/bin/env python3
"""Release contract for battle-reward shadow generation.

The current reward queue shadow has no independently proven battle-generation
counter. Its safe generation boundary is therefore the game's zeroed reward
queue. Until real gameplay proves that boundary occurs between consecutive
battle reward generations, release QA must keep this assumption explicit rather
than silently treating it as proven.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods/universal-item-randomizer"
SOURCE = (MOD / "src/universal_item_randomizer.c").read_text()
TELEMETRY = (MOD / "QA-TELEMETRY.md").read_text().lower()
TESTING = (MOD / "TESTING.md").read_text().lower()


def main() -> int:
    # Current implementation clears a reward slot shadow only when the live
    # queue slot is zero. Do not let a future refactor accidentally remove that
    # boundary while QA still relies on it.
    assert "if (raw == 0u)" in SOURCE
    assert "s_reward_valid[i] = 0u;" in SOURCE
    assert "s_reward_written[i] = 0u;" in SOURCE

    # There is deliberately no guessed battle-generation address in 0.3.1.
    # A proven generation key may replace this contract later, but until then
    # documentation must require observing the zero boundary in real gameplay.
    for text, name in ((TELEMETRY, "QA-TELEMETRY.md"), (TESTING, "TESTING.md")):
        assert "reward queue" in text, f"{name}: reward queue QA missing"
        assert "zero" in text or "zerad" in text, f"{name}: zero-generation boundary missing"
        assert "two consecutive" in text or "duas batalhas consecutivas" in text, (
            f"{name}: consecutive-battle generation proof missing"
        )
        assert "release" in text or "1.0" in text, f"{name}: release gate wording missing"

    print("universal randomizer reward-generation release contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
