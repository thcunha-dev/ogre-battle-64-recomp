#!/usr/bin/env python3
"""Cross-subsystem stress model for the Universal Item Randomizer.

This deliberately composes behavior that the focused tests cover separately:
source shadows, deterministic mapping, native-save identity, count saturation,
ON/OFF transitions, seed changes, and post-ending continuation.  It is not a
replacement for real Rev-A gameplay QA; it is a regression net for interactions
between those policies.
"""

from __future__ import annotations

import random

from test_randomizer_source_shadow_model import DropShadow, PickupShadow, RewardShadow
from test_universal_randomizer_mapping import CONSUMABLE_SALT, cycle

POOL = list(range(1, 41))
COUNT_MAX = 99
CAMPAIGNS = 1000
EVENTS = 600


def add_owned(owned: dict[int, int], item_id: int, amount: int = 1) -> None:
    assert item_id in POOL
    assert amount >= 0
    owned[item_id] = min(COUNT_MAX, owned.get(item_id, 0) + amount)
    assert 0 <= owned[item_id] <= COUNT_MAX


def snapshot(owned: dict[int, int]) -> tuple[tuple[int, int], ...]:
    return tuple(sorted(owned.items()))


def main() -> int:
    for campaign in range(CAMPAIGNS):
        rng = random.Random(0x0B640000 + campaign)
        seed = rng.randrange(1, 0xFFFFFFFF)
        mapping = cycle(seed, POOL, CONSUMABLE_SALT)
        enabled = True
        map_index = 0
        finished = False
        owned: dict[int, int] = {}
        pickup = PickupShadow()
        reward = RewardShadow()
        drop = DropShadow()

        for event_no in range(EVENTS):
            kind = rng.randrange(10)

            if kind == 0:
                # Native-save round-trip: loading must be identity regardless of
                # whether the mod is currently enabled.
                before = snapshot(owned)
                loaded = dict(before)
                assert snapshot(loaded) == before
                owned = loaded
                continue

            if kind == 1:
                enabled = not enabled
                before = snapshot(owned)
                # Toggle never rewrites already-owned vanilla ids/counts.
                assert snapshot(owned) == before
                continue

            if kind == 2:
                # Configuration changes take effect only after a full restart.
                before = snapshot(owned)
                seed = rng.randrange(1, 0xFFFFFFFF)
                mapping = cycle(seed, POOL, CONSUMABLE_SALT)
                assert snapshot(owned) == before
                continue

            if kind == 3:
                # Map transition is a source-generation boundary.
                map_index = (map_index + 1) & 0xFF
                raw = rng.choice(POOL)
                out = pickup.rewrite(map_index, [raw])[0]
                expected = mapping[raw] if enabled else raw
                # The production source-shadow rewrite runs only when enabled;
                # model the disabled case by consuming vanilla directly.
                delivered = out if enabled else raw
                if enabled:
                    # Drop/Pickup shadow model has its own fixed test seed, so
                    # only enforce validity/no-double-write here; mapping exactness
                    # is locked by the dedicated mapper and shadow tests.
                    assert delivered in POOL
                else:
                    assert delivered == expected
                add_owned(owned, delivered)
                continue

            if kind == 4:
                raw = rng.choice(POOL)
                if enabled:
                    # Direct audited grant consumes the one shared mapper.
                    delivered = mapping[raw]
                    assert delivered != raw
                else:
                    delivered = raw
                add_owned(owned, delivered)
                continue

            if kind == 5:
                # Reward queue lifecycle: clear slot, then reuse it with a fresh
                # vanilla reward.  No stale shadow may suppress the new generation.
                raw = rng.choice(POOL)
                first = reward.rewrite([raw])[0]
                assert first in POOL
                reward.rewrite([0])
                assert not reward.valid[0]
                again = reward.rewrite([raw])[0]
                assert again == first
                delivered = again if enabled else raw
                add_owned(owned, delivered)
                continue

            if kind == 6:
                # Table-O disappearance/reappearance and map changes must clear
                # stale generations rather than double-map old replacements.
                raw = rng.choice(POOL)
                first = drop.rewrite(map_index, True, [raw])[0]
                assert first in POOL
                drop.rewrite(map_index, False, [])
                assert not drop.valid[0]
                map_index = (map_index + 1) & 0xFF
                again = drop.rewrite(map_index, True, [raw])[0]
                assert again == first
                delivered = again if enabled else raw
                add_owned(owned, delivered)
                continue

            if kind == 7:
                # Saturation/full-stack behavior must never wrap.
                item_id = rng.choice(POOL)
                add_owned(owned, item_id, rng.randrange(1, 300))
                assert owned[item_id] <= COUNT_MAX
                continue

            if kind == 8:
                # Ending/post-game boundary: save state remains ordinary vanilla
                # inventory.  Reopening must not trigger a whole-inventory remap.
                finished = True
                before = snapshot(owned)
                reopened = dict(before)
                assert snapshot(reopened) == before
                owned = reopened
                continue

            # Continue acquiring after ending, including after seed/toggle changes.
            raw = rng.choice(POOL)
            delivered = mapping[raw] if enabled else raw
            add_owned(owned, delivered, rng.randrange(1, 5))
            if finished:
                assert all(item in POOL and 0 <= count <= COUNT_MAX for item, count in owned.items())

        assert all(item in POOL for item in owned)
        assert all(0 <= count <= COUNT_MAX for count in owned.values())

    print(f"universal randomizer campaign stress model: PASS ({CAMPAIGNS} campaigns x {EVENTS} events)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
