#!/usr/bin/env python3
"""Host-side model of source-shadow behaviour for Universal Item Randomizer.

The game reuses RAM for map pickup/drop/reward sources.  The mod therefore keeps
short-lived shadows so values it wrote are not transformed a second time.  This
model exercises the dangerous cases that are hard to cover with static source
checks alone:

* same frame/source value must not be double-mapped;
* changing map index invalidates pickup shadows even if the new vanilla value
  happens to equal the replacement written on the previous map;
* shrinking/reloading pickup lists clears stale slots;
* reward queue zero clears its shadow and a later identical raw reward maps again;
* disappearing/reappearing drop tables reset their shadow generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from test_universal_randomizer_mapping import CONSUMABLE_SALT, cycle

POOL = list(range(1, 41))
MAP = cycle(0x0B640301, POOL, CONSUMABLE_SALT)


def mapped(raw: int) -> int:
    if raw == 0:
        return 0
    return MAP[raw]


@dataclass
class PickupShadow:
    written: list[int] = field(default_factory=lambda: [0] * 64)
    valid: list[bool] = field(default_factory=lambda: [False] * 64)
    map_index: int | None = None

    def rewrite(self, map_index: int, values: list[int]) -> list[int]:
        if self.map_index != map_index:
            self.valid = [False] * 64
            self.map_index = map_index

        out: list[int] = []
        for i in range(64):
            if i >= len(values):
                self.valid[i] = False
                continue
            raw = values[i]
            if self.valid[i] and raw == self.written[i]:
                out.append(raw)
                continue
            replacement = mapped(raw)
            self.written[i] = replacement
            self.valid[i] = True
            out.append(replacement)
        return out


@dataclass
class RewardShadow:
    written: list[int] = field(default_factory=lambda: [0] * 20)
    valid: list[bool] = field(default_factory=lambda: [False] * 20)

    def rewrite(self, values: list[int]) -> list[int]:
        out = list(values)
        for i in range(20):
            raw = out[i] if i < len(out) else 0
            if raw == 0:
                self.valid[i] = False
                self.written[i] = 0
                continue
            if self.valid[i] and raw == self.written[i]:
                continue
            replacement = mapped(raw)
            self.written[i] = replacement
            self.valid[i] = True
            out[i] = replacement
        return out


@dataclass
class DropShadow:
    written: list[int] = field(default_factory=lambda: [0] * (35 * 3))
    valid: list[bool] = field(default_factory=lambda: [False] * (35 * 3))
    present: bool = False

    def rewrite(self, present: bool, values: list[int]) -> list[int]:
        if not present:
            if self.present:
                self.valid = [False] * (35 * 3)
            self.present = False
            return list(values)

        self.present = True
        out = list(values)
        for i, raw in enumerate(out):
            if self.valid[i] and raw == self.written[i]:
                continue
            replacement = mapped(raw)
            self.written[i] = replacement
            self.valid[i] = True
            out[i] = replacement
        return out


def find_collision_case() -> tuple[int, int]:
    # Find previous raw A whose replacement X can legitimately be raw on a new
    # map. Every permutation target is a valid vanilla id, so such a case exists.
    for raw_a in POOL:
        x = mapped(raw_a)
        if x in POOL and x != raw_a:
            return raw_a, x
    raise AssertionError("no collision case")


def test_pickup_map_generation() -> None:
    shadow = PickupShadow()
    raw_a, next_map_raw = find_collision_case()

    first = shadow.rewrite(7, [raw_a])
    assert first == [mapped(raw_a)]
    # Same already-written source on the same map is stable, not map(map(A)).
    assert shadow.rewrite(7, first) == first

    # Critical regression case: new map's VANILLA raw id equals the replacement
    # written on the old map.  Map-index change must force a fresh mapping.
    second = shadow.rewrite(8, [next_map_raw])
    assert second == [mapped(next_map_raw)]
    assert second != [next_map_raw], "new-map raw value was mistaken for old shadow"

    # Shrink clears stale slot; growing again must map new raw data.
    shadow.rewrite(8, [])
    assert not shadow.valid[0]
    third = shadow.rewrite(8, [raw_a])
    assert third == [mapped(raw_a)]


def test_reward_zero_generation() -> None:
    shadow = RewardShadow()
    raw = 5
    first = shadow.rewrite([raw])
    assert first[0] == mapped(raw)
    assert shadow.rewrite(first)[0] == first[0]

    # Queue consumption/clear invalidates the memo.
    shadow.rewrite([0])
    assert not shadow.valid[0]
    again = shadow.rewrite([raw])
    assert again[0] == mapped(raw)


def test_drop_presence_generation() -> None:
    shadow = DropShadow()
    raw_a, next_raw = find_collision_case()
    first = shadow.rewrite(True, [raw_a])
    assert first == [mapped(raw_a)]
    assert shadow.rewrite(True, first) == first

    # Bank/map unload removes the table; reappearance starts a new generation.
    shadow.rewrite(False, [])
    assert not shadow.valid[0]
    second = shadow.rewrite(True, [next_raw])
    assert second == [mapped(next_raw)]
    assert second != [next_raw]


def main() -> int:
    test_pickup_map_generation()
    test_reward_zero_generation()
    test_drop_presence_generation()
    print("universal randomizer source-shadow model: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
