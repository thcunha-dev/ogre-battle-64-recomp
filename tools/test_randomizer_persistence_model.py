#!/usr/bin/env python3
"""Host-side persistence model for Universal Item Randomizer.

This is not an emulator. It deliberately models only the invariants that matter
for native-save compatibility:

* native save persists vanilla item ids + owned counts only;
* load restores those exact ids/counts and never applies the mapper;
* enabling/disabling/changing seed affects future acquisitions only;
* existing randomized vanilla-valid ids remain readable with the mod disabled;
* post-battle additions saturate at 99;
* key items remain identity unless the explicit key-items option is enabled.

Thousands of deterministic pseudo-random sequences are exercised so regressions
in policy are caught before in-game QA.
"""

from __future__ import annotations

from dataclasses import dataclass
import random

from test_universal_randomizer_mapping import (
    CONSUMABLE_SALT,
    EQUIP_SALT,
    KEY_SALT,
    cycle,
)

COUNT_MAX = 99
EQUIP_IDS = tuple(range(1, 278))
NORMAL_CONSUMABLE_IDS = tuple(range(1, 33))
KEY_IDS = tuple(range(33, 41))


@dataclass(frozen=True)
class NativeSave:
    equipment: tuple[tuple[int, int], ...]
    consumables: tuple[tuple[int, int], ...]


class Inventory:
    def __init__(self) -> None:
        self.equipment: dict[int, int] = {}
        self.consumables: dict[int, int] = {}

    @staticmethod
    def _add(table: dict[int, int], item_id: int, amount: int = 1) -> None:
        assert amount >= 0
        if amount == 0:
            return
        table[item_id] = min(COUNT_MAX, table.get(item_id, 0) + amount)

    def add_equipment(self, item_id: int, amount: int = 1) -> None:
        assert item_id in EQUIP_IDS
        self._add(self.equipment, item_id, amount)

    def add_consumable(self, item_id: int, amount: int = 1) -> None:
        assert item_id in NORMAL_CONSUMABLE_IDS or item_id in KEY_IDS
        self._add(self.consumables, item_id, amount)

    def save_native(self) -> NativeSave:
        # Native-save model intentionally contains no seed/config/mapping state.
        return NativeSave(
            equipment=tuple(sorted(self.equipment.items())),
            consumables=tuple(sorted(self.consumables.items())),
        )

    @classmethod
    def load_native(cls, save: NativeSave) -> "Inventory":
        inv = cls()
        inv.equipment = dict(save.equipment)
        inv.consumables = dict(save.consumables)
        return inv


class RandomizerSession:
    def __init__(self, seed: int, enabled: bool = True, key_items: bool = False) -> None:
        self.enabled = enabled
        self.key_items = key_items
        self.equipment_map = cycle(seed, list(EQUIP_IDS), EQUIP_SALT)
        self.normal_map = cycle(seed, list(NORMAL_CONSUMABLE_IDS), CONSUMABLE_SALT)
        self.key_map = cycle(seed, list(KEY_IDS), KEY_SALT)

    def equipment(self, item_id: int) -> int:
        if not self.enabled:
            return item_id
        return self.equipment_map[item_id]

    def consumable(self, item_id: int) -> int:
        if not self.enabled:
            return item_id
        if item_id in KEY_IDS:
            return self.key_map[item_id] if self.key_items else item_id
        return self.normal_map[item_id]


def assert_save_has_only_native_state(save: NativeSave) -> None:
    assert set(save.__dataclass_fields__) == {"equipment", "consumables"}
    for item_id, count in save.equipment:
        assert item_id in EQUIP_IDS
        assert 1 <= count <= COUNT_MAX
    for item_id, count in save.consumables:
        assert item_id in NORMAL_CONSUMABLE_IDS or item_id in KEY_IDS
        assert 1 <= count <= COUNT_MAX


def one_sequence(rng: random.Random, sequence_id: int) -> None:
    seed_a = rng.randrange(1, 2**32)
    seed_b = rng.randrange(1, 2**32)
    if seed_b == seed_a:
        seed_b ^= 0xA5A5A5A5

    on_a = RandomizerSession(seed_a, enabled=True, key_items=False)
    off = RandomizerSession(seed_a, enabled=False, key_items=False)
    on_b = RandomizerSession(seed_b, enabled=True, key_items=False)

    inv = Inventory()

    # Acquire a mixed prefix with the randomizer enabled.
    for _ in range(rng.randint(8, 80)):
        if rng.random() < 0.6:
            raw = rng.choice(EQUIP_IDS)
            inv.add_equipment(on_a.equipment(raw), rng.randint(1, 8))
        else:
            raw = rng.choice(NORMAL_CONSUMABLE_IDS + KEY_IDS)
            inv.add_consumable(on_a.consumable(raw), rng.randint(1, 8))

    save_a = inv.save_native()
    assert_save_has_only_native_state(save_a)

    # OFF load must be byte-for-byte-equivalent at the modeled native state.
    inv_off = Inventory.load_native(save_a)
    assert inv_off.save_native() == save_a, (sequence_id, "OFF load mutated save")

    # Acquire future vanilla items with the mod disabled. Existing ids stay put.
    existing_before_off_grant = inv_off.save_native()
    for _ in range(rng.randint(1, 20)):
        if rng.random() < 0.5:
            raw = rng.choice(EQUIP_IDS)
            inv_off.add_equipment(off.equipment(raw), rng.randint(1, 5))
        else:
            raw = rng.choice(NORMAL_CONSUMABLE_IDS + KEY_IDS)
            inv_off.add_consumable(off.consumable(raw), rng.randint(1, 5))
    # Prefix state was not transformed merely because the mod is off.
    for item_id, count in existing_before_off_grant.equipment:
        assert inv_off.equipment.get(item_id, 0) >= count
    for item_id, count in existing_before_off_grant.consumables:
        assert inv_off.consumables.get(item_id, 0) >= count

    save_off = inv_off.save_native()
    assert_save_has_only_native_state(save_off)

    # Re-enable with a different seed: load remains exact; only future grants use B.
    inv_b = Inventory.load_native(save_off)
    assert inv_b.save_native() == save_off, (sequence_id, "seed change rerandomized load")

    snapshot_before_b_grants = inv_b.save_native()
    for _ in range(rng.randint(1, 30)):
        raw = rng.choice(EQUIP_IDS)
        mapped = on_b.equipment(raw)
        inv_b.add_equipment(mapped, rng.randint(1, 250))
        assert inv_b.equipment[mapped] <= COUNT_MAX

    for item_id, count in snapshot_before_b_grants.equipment:
        assert inv_b.equipment.get(item_id, 0) >= count
    for item_id, count in snapshot_before_b_grants.consumables:
        assert inv_b.consumables.get(item_id, 0) >= count

    # Key-items OFF is progression-safe by construction.
    for key_id in KEY_IDS:
        assert on_a.consumable(key_id) == key_id
        assert on_b.consumable(key_id) == key_id

    final_save = inv_b.save_native()
    assert_save_has_only_native_state(final_save)
    assert Inventory.load_native(final_save).save_native() == final_save


def key_item_opt_in_test() -> None:
    session = RandomizerSession(0x12345678, enabled=True, key_items=True)
    mapped = {key_id: session.consumable(key_id) for key_id in KEY_IDS}
    assert set(mapped) == set(KEY_IDS)
    assert set(mapped.values()) == set(KEY_IDS)
    assert all(k != v for k, v in mapped.items())
    # Opt-in key mapping is isolated from normal consumables.
    assert all(v in NORMAL_CONSUMABLE_IDS for v in session.normal_map.values())


def main() -> int:
    rng = random.Random(0x0B640301)
    for sequence_id in range(5000):
        one_sequence(rng, sequence_id)
    key_item_opt_in_test()
    print("universal randomizer persistence model: PASS (5000 sequences)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
