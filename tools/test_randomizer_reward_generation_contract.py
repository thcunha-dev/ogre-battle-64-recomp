#!/usr/bin/env python3
"""Lifecycle contract for battle-reward queue shadowing.

The reward source is a persisted 20-u16 queue, not a single generation blob.
Multiple queue positions have been observed carrying real rewards, so requiring
the entire block to become zero between battles would be incorrect. Shadow
lifecycle is therefore per-slot: a zero live word invalidates that slot's shadow.
The primary consumed word at 0x801936D8 is statically proven to be cleared by the
game immediately after the grant (bank N 0x801E53F4).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods/universal-item-randomizer"
SOURCE = (MOD / "src/universal_item_randomizer.c").read_text()
TELEMETRY = (MOD / "QA-TELEMETRY.md").read_text().lower()
TESTING = (MOD / "TESTING.md").read_text().lower()


def main() -> int:
    assert "#define REWARD_QUEUE             0x801936D8u" in SOURCE
    assert "#define REWARD_SLOTS             20u" in SOURCE

    # Per-slot invalidation is the safety mechanism. A slot that the game clears
    # to zero cannot retain a replacement shadow into its next use.
    assert "if (raw == 0u)" in SOURCE
    assert "s_reward_valid[i] = 0u;" in SOURCE
    assert "s_reward_written[i] = 0u;" in SOURCE

    # QA/docs must describe the real per-slot lifecycle and the proven native
    # clear of the primary consumed reward. Do not regress to an all-zero-global
    # assumption: other queue positions may legitimately remain populated.
    for text, name in ((TELEMETRY, "QA-TELEMETRY.md"), (TESTING, "TESTING.md")):
        assert "reward queue" in text, f"{name}: reward queue QA missing"
        assert "per-slot" in text or "por slot" in text, f"{name}: per-slot lifecycle missing"
        assert "0x801e53f4" in text, f"{name}: native post-grant clear proof missing"
        assert "0x801936d8" in text, f"{name}: primary reward slot missing"
        assert "all-zero" not in text, f"{name}: stale global-zero assumption present"
        assert "release" in text or "1.0" in text, f"{name}: release QA wording missing"

    print("universal randomizer reward-slot lifecycle contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
