# Universal Item Randomizer 0.3.1 — end-to-end test protocol

Use a copy of the Rev-A recomp save directory for the first run. The mod is
designed to keep the native save format unchanged, but 1.0 is not declared until
this matrix is verified on a real build.

0.3.1 uses one shared deterministic mapper for every covered acquisition path.
For a given seed, the same original equipment/consumable id must therefore map to
the same replacement whether it came from a pickup, battle reward, secondary
post-battle transfer or shop stock. Unclassified direct Bank-N/Bank-R grant
callers are fail-closed and remain vanilla.

## Baseline

1. Start the recomp **without** `universal-item-randomizer.nrm` enabled.
2. Load a known-good save and note a few owned item ids/counts.
3. Save once and close the game. Keep a backup of this save directory.

## Test A — deterministic map pickup

1. Enable `Universal Item Randomizer`.
2. Set `SEED = 123456`.
3. Leave `STARTING ITEMS = OFF`, `KEY ITEMS = OFF` and `RANDOMIZE SHOPS = OFF`.
4. Load the baseline save.
5. Pick up a normal map/ground item.
6. Confirm the popup name/icon is the same item that appears in inventory.
7. Save and close.
8. Reopen with the same seed and load the same save.
9. Existing inventory must be unchanged.
10. Repeat the same original pickup on a clean copy of the baseline save: the
    replacement must be identical.
11. Move to a different map and acquire another ground item. The second map's
    pickup source must be mapped independently even if its vanilla id happens to
    equal the replacement written in the same slot on the previous map.

## Test B — battle reward

1. With seed `123456`, finish a battle that gives an item reward.
2. Confirm reward text/name matches the inventory item.
3. Confirm owned count increments normally and never exceeds 99.
4. For equipment, confirm the item screen does not show a false unusable `1/1`.

## Test C — secondary post-battle add

Exercise a chapter/battle path that reaches Bank-L's 14-entry post-battle item
transfer (`func_80172820`). Confirm:

- the equipment id is deterministic for the seed;
- if the same original equipment id is obtainable through another covered path,
  both routes give the **same replacement** under the same seed;
- the full count is added and saturates at 99 without wrapping;
- the native-style full used-count rebuild covers both equipment and consumable
  lists immediately after the add;
- the item is immediately equip-eligible when `used < owned`;
- no unrelated inventory id/count changes.

## Test D — native save compatibility

1. Enable the randomizer, acquire at least one randomized item and save.
2. Close the game completely.
3. Disable the randomizer completely.
4. Load that exact save.
5. It must load normally; existing items remain ordinary vanilla item ids.
6. Save again with the mod disabled and close.
7. Reopen once more with the mod still disabled and load the same file.
8. Re-enable the randomizer and load that same file again.

All three transitions — ON→OFF, OFF→OFF after resave, and OFF→ON — must load
without inventory reconstruction being interpreted as a new acquisition.

The `+0x02` used-count column is transient and rebuilt from the roster; only item
id and owned count belong to the native save representation. The randomizer's
repair code may therefore correct `+0x02`, but it must never rewrite id or owned
count during a load-only step.

## Test E — seed is not save state

1. Load a randomizer-created save with seed `123456`; note existing inventory.
2. Close, change the seed to `654321`, reopen and load the same save.
3. Existing inventory must not change.
4. Only **future** acquisitions should use the new mapping.
5. Switch back to `123456`; future copies of the same original item must return
   to the original 123456 replacement.

## Test F — starting grants

`STARTING ITEMS` is intentionally restricted to the one Bank-R straight-line
literal grant block proven by disassembly (`jal` sites in `0x80217068..0x80217244`).
The corresponding return-address window in the mod is `0x80217070..0x8021724B`.
Two other whole-game Bank-R callers (`jal` at `0x80215BEC` and `0x80216D90`) are
**not** included; they remain vanilla until their game semantics are classified.

### Starting items OFF

1. Start a clean New Game with `STARTING ITEMS = OFF`.
2. Verify the game's normal starting consumables are unchanged.
3. Normal pickups/rewards should still randomize, proving setup grants are not
   caught by the normal-source paths.

### Starting items ON + caller-recognition proof

1. Use a separate disposable New Game.
2. Set `STARTING ITEMS = ON`, `LOG = ON` and seed `123456`.
3. During tutorial/map setup, inspect the recomp log.
4. At least one bounded diagnostic must appear:
   `universal-item-randomizer: Bank-R starting grant recognized`
5. Starting consumable grants should then be deterministically remapped and
   remain stable for the same seed.
6. Repeat with the same seed on a clean save and require the same replacements.
7. If the diagnostic never appears, consider `STARTING ITEMS` unsupported for
   release; do not widen the caller range by guesswork.

The diagnostic is capped to the first four recognized starting grants so it
cannot flood the log during the literal batch.

### Unclassified Bank-R callers

With `LOG = ON`, if either caller at `0x80215BEC` or `0x80216D90` is reached, the
bounded diagnostic is:

`universal-item-randomizer: unclassified Bank-R grant left vanilla`

For each occurrence:

1. record the scene/event and the original granted item;
2. repeat with the same seed and `STARTING ITEMS` toggled OFF/ON;
3. the granted item must remain identical in both runs;
4. only after its role is proven may that caller receive a dedicated acquisition
   classification/source rewrite.

This is the preferred route for discovering cutscene/NPC/quest gifts without
turning the central fallback into an unsafe catch-all.

### Class-default equipment remains vanilla

The same map loader equips four class-derived defaults per created unit through
`func_ovlN_801DD430`. These are deliberately **not** covered by `STARTING ITEMS`.
The game later rebuilds used counts from the class-derived equipment table itself;
randomizing only the owned-list grant would separate the class reference from the
owned id and can create false `used/owned` state. Leave class-default equipment
vanilla until a design can change the source/reference and owned list together.

## Test G — key items

With `KEY ITEMS = OFF`, acquire a class-3/4 quest/key item. Its id must remain
vanilla. Do not test `KEY ITEMS = ON` on an irreplaceable campaign save until the
normal mode has passed the full campaign regression.

When testing `KEY ITEMS = ON` on a disposable save, a key item may only map to
another member of the audited class-3/4 key-item pool; it must never map into
ordinary consumables, equipment, or an unknown class. Classes outside 0..4 are
fail-closed and remain identity-mapped.

## Test H — post-game regression

1. Finish the game with the randomizer enabled.
2. Save/post-game using the same file that was used during the run.
3. Close the game completely.
4. Reopen and load with the randomizer enabled.
5. Close again and load the same save with the randomizer disabled.
6. Save with the mod disabled, close, then enable the mod and load once more.
7. All loads must succeed and owned inventory counts must be identical across
   the load-only steps.

This is the acceptance test for the failure mode reported in the older
randomizer.

## Test I — shops (0.3.1)

The Rev-A ROM audit identified the real town shop as Bank AB. Its stock builder
allocates a 0x200-byte, zero-terminated raw `u16 item_word` list and stores the
pointer at `0x80219F40`. The list begins with the vanilla consumable signature
`1,2,3,4,5,6,8`; Bank AB later derives its sorted equipment/consumable caches,
name/detail panel, price and purchased id from that source.

The unique call that constructs this source is at Bank-N ROM `0x10BC40`
(`jal 0x80219600`). After it returns, the caller only sets a transition flag at
`0x801F367D`, restores its frame and returns. This gives the main frame hook a
window to map the raw stock before the shop's next update builds/uses the caches.

### Shops OFF

1. Keep `RANDOMIZE SHOPS = OFF` and use seed `123456`.
2. Open a normal town shop.
3. Stock, names and prices must remain vanilla.
4. Buy one item and verify the exact displayed item/count is added.

### Shops ON

1. On a clean save/copy, enable `RANDOMIZE SHOPS` with seed `123456`.
2. Open the same shop.
3. Confirm its visible stock is changed deterministically.
4. Select at least one equipment item and one consumable:
   - list name/icon must match detail name;
   - displayed price must correspond to the replacement item;
   - purchase must add exactly that displayed replacement item;
   - quantity/count must be correct.
5. If an original shop item is also obtainable from a pickup/reward, confirm it
   maps to the same replacement under seed `123456`.
6. Exit and reopen the same shop with the same seed: stock must map identically.
7. Reopen with seed `654321`: future shop stock may change, but existing owned
   inventory must not.
8. Save after a randomized shop purchase, disable the mod, reopen and load the
   same save. The save must remain valid and the purchased item remains a normal
   vanilla item id.

If the shop briefly shows vanilla stock before changing, or if a displayed item
and purchased item ever differ, treat that as a timing bug and disable the shop
option until the post-builder timing is moved to a bank return hook/replacement.

## Test J — unclassified direct grants stay vanilla

0.3.1 deliberately does **not** randomize an unknown direct
`func_ovlN_801DC740` caller merely because another option is on. Shops have their
own Bank-AB source path, and `STARTING ITEMS` uses only its proven literal block.

During campaign QA, whenever an item grant is observed that is not a known
pickup/reward/starting/shop route:

1. record the scene and original item;
2. test it with shops OFF/ON and starting items OFF/ON using the same seed;
3. the grant must be identical in every run unless that caller has been
   explicitly classified and added as a supported randomizer source;
4. never broaden the central fallback to randomize all unknown callers; classify
   the route first so setup/script state cannot be caught by accident.

## Acceptance criteria for 0.3.1

The build can advance beyond test status only when all of these are true:

- map pickup popup and inventory agree across map transitions;
- battle reward UI and inventory agree;
- post-battle count/equipped-use bookkeeping is correct and never wraps;
- same seed maps the same original id identically across every covered route;
- key items and starting items remain vanilla with their options off;
- `STARTING ITEMS=ON` produces the narrow Bank-R recognition diagnostic before
  it is considered supported;
- the two other Bank-R grant callers remain vanilla until explicitly classified;
- class-default equipment remains vanilla until its source/reference coupling is
  implemented safely;
- shops are internally consistent when enabled and fully vanilla when disabled;
- changing seed never rewrites existing inventory;
- save ON→OFF→ON works;
- finish/post-game→close→reopen works with the same save;
- no unclassified direct grant is randomized accidentally.
