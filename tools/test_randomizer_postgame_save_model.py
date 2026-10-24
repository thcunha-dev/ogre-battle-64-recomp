#!/usr/bin/env python3
"""Model completed-game/post-ending native-save compatibility.

This does not replace real Rev-A gameplay QA. It locks the persistence policy
that matters most for post-game safety:

* finishing the game never writes randomizer metadata into native save state;
* reopening the post-ending save ON or OFF is an identity load operation;
* saving while OFF and reopening ON preserves all existing ids/counts;
* changing seed after the ending affects future acquisitions only;
* every persisted id remains a vanilla-valid Ogre Battle 64 item id.
"""

from __future__ import annotations

import random

from test_randomizer_persistence_model import (
    EQUIP_IDS,
    KEY_IDS,
    NORMAL_CONSUMABLE_IDS,
    Inventory,
    RandomizerSession,
    assert_save_has_only_native_state,
)


def acquire_campaign_mix(
    rng: random.Random,
    inv: Inventory,
    session: RandomizerSession,
    minimum: int,
    maximum: int,
) -> None:
    for _ in range(rng.randint(minimum, maximum)):
        if rng.random() < 0.62:
            raw = rng.choice(EQUIP_IDS)
            inv.add_equipment(session.equipment(raw), rng.randint(1, 6))
        else:
            raw = rng.choice(NORMAL_CONSUMABLE_IDS + KEY_IDS)
            inv.add_consumable(session.consumable(raw), rng.randint(1, 6))


def one_postgame_sequence(rng: random.Random, sequence_id: int) -> None:
    seed_finish = rng.randrange(1, 2**32)
    seed_post = rng.randrange(1, 2**32)
    if seed_post == seed_finish:
        seed_post ^= 0x6F677265

    on_finish = RandomizerSession(seed_finish, enabled=True, key_items=False)
    off = RandomizerSession(seed_finish, enabled=False, key_items=False)
    on_post = RandomizerSession(seed_post, enabled=True, key_items=False)

    # Model a developed campaign inventory before the ending. The larger prefix
    # deliberately creates many collisions/saturated stacks before persistence.
    inv = Inventory()
    acquire_campaign_mix(rng, inv, on_finish, 80, 220)

    ending_save = inv.save_native()
    assert_save_has_only_native_state(ending_save)

    # Post-ending reopen with the randomizer still ON must be load-only: no
    # existing item may be remapped simply because the session initializes.
    post_on = Inventory.load_native(ending_save)
    assert post_on.save_native() == ending_save, (sequence_id, "postgame ON load mutated save")

    # Save from the post-ending state, then reopen with the mod disabled.
    post_on_save = post_on.save_native()
    post_off = Inventory.load_native(post_on_save)
    assert post_off.save_native() == post_on_save, (sequence_id, "postgame OFF load mutated save")

    # Exercise a few ordinary vanilla acquisitions while OFF. They may merge
    # with existing stacks, but must never transform pre-existing ids/counts.
    before_off_grants = post_off.save_native()
    acquire_campaign_mix(rng, post_off, off, 1, 24)
    for item_id, count in before_off_grants.equipment:
        assert post_off.equipment.get(item_id, 0) >= count
    for item_id, count in before_off_grants.consumables:
        assert post_off.consumables.get(item_id, 0) >= count

    off_save = post_off.save_native()
    assert_save_has_only_native_state(off_save)

    # Re-enable after a complete restart, optionally with a different seed.
    # Existing native state must still load identically; only future grants use
    # the new mapping.
    reopened_on = Inventory.load_native(off_save)
    assert reopened_on.save_native() == off_save, (sequence_id, "OFF -> ON postgame load mutated save")

    existing_before_new_seed = reopened_on.save_native()
    acquire_campaign_mix(rng, reopened_on, on_post, 1, 30)
    for item_id, count in existing_before_new_seed.equipment:
        assert reopened_on.equipment.get(item_id, 0) >= count
    for item_id, count in existing_before_new_seed.consumables:
        assert reopened_on.consumables.get(item_id, 0) >= count

    final_save = reopened_on.save_native()
    assert_save_has_only_native_state(final_save)
    assert Inventory.load_native(final_save).save_native() == final_save

    # Safe-default progression policy remains unchanged after the ending too.
    for key_id in KEY_IDS:
        assert on_finish.consumable(key_id) == key_id
        assert on_post.consumable(key_id) == key_id


def main() -> int:
    rng = random.Random(0x504F5354)  # "POST"
    for sequence_id in range(2000):
        one_postgame_sequence(rng, sequence_id)
    print("universal randomizer postgame save model: PASS (2000 sequences)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
