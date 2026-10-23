# Universal Item Randomizer — end-to-end test protocol

Use a copy of the Rev-A recomp save directory for the first run. The mod is
designed to keep the native save format unchanged, but 1.0 is not declared until
this matrix is verified on a real build.

## Baseline

1. Start the recomp **without** `universal-item-randomizer.nrm` enabled.
2. Load a known-good save and note a few owned item ids/counts.
3. Save once and close the game. Keep a backup of this save directory.

## Test A — deterministic map pickup

1. Enable `Universal Item Randomizer`.
2. Set `SEED = 123456`.
3. Leave `STARTING ITEMS = OFF` and `KEY ITEMS = OFF`.
4. Load the baseline save.
5. Pick up a normal map/ground item.
6. Confirm the popup name/icon is the same item that appears in inventory.
7. Save and close.
8. Reopen with the same seed and load the same save.
9. Existing inventory must be unchanged.
10. Repeat the same original pickup on a clean copy of the baseline save: the
    replacement must be identical.

## Test B — battle reward

1. With seed `123456`, finish a battle that gives an item reward.
2. Confirm reward text/name matches the inventory item.
3. Confirm owned count increments normally and never exceeds 99.
4. For equipment, confirm the item screen does not show a false unusable `1/1`.

## Test C — secondary post-battle add

Exercise a chapter/battle path that reaches Bank-L's 14-entry post-battle item
transfer (`func_80172820`). Confirm:

- the equipment id is deterministic for the seed;
- the full count is added (cap 99);
- the item is immediately equip-eligible when `used < owned`;
- no unrelated inventory record changes.

## Test D — native save compatibility

1. Enable the randomizer, acquire at least one randomized item and save.
2. Close the game.
3. Disable the randomizer completely.
4. Load that exact save.
5. It must load normally; existing items remain ordinary vanilla item ids.
6. Save again with the mod disabled and reopen once more.

## Test E — seed is not save state

1. Load a randomizer-created save with seed `123456`; note existing inventory.
2. Close, change the seed to `654321`, reopen and load the same save.
3. Existing inventory must not change.
4. Only **future** acquisitions should use the new mapping.

## Test F — starting grants

With `STARTING ITEMS = OFF`, start a New Game and verify the game's normal
starting consumables are unchanged.

Then on a separate clean run set `STARTING ITEMS = ON`; starting grants should be
deterministically remapped and remain stable for the same seed.

## Test G — key items

With `KEY ITEMS = OFF`, acquire a class-3/4 quest/key item. Its id must remain
vanilla. Do not test `KEY ITEMS = ON` on an irreplaceable campaign save until the
normal mode has passed the full campaign regression.

## Test H — post-game regression

1. Finish the game with the randomizer enabled.
2. Save/post-game using the same file that was used during the run.
3. Close the game completely.
4. Reopen and load with the randomizer enabled.
5. Close again and load the same save with the randomizer disabled.
6. Both loads must succeed.

This is the acceptance test for the failure mode reported in the older
randomizer.

## Shops

Shop randomization is **not exposed** in 0.2.1. Town shops must remain vanilla
until Bank AB's stock/display/purchase path is mapped end to end. If a normal
0.2.1 test changes shop stock or delivers a different item than displayed, treat
that as a bug.
