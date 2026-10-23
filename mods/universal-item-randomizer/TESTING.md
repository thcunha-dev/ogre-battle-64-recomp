# Universal Item Randomizer 0.3.1 — end-to-end test protocol

Use a copy of the Rev-A recomp save directory for the first run. The mod is
designed to keep the native save format unchanged, but 1.0 is not declared until
this matrix is verified on a real build.

0.3.1 uses one shared deterministic mapper for every covered acquisition path.
For a given seed, the same original equipment/consumable id must map to the same
replacement whether it came from a pickup, battle reward, secondary post-battle
transfer, shop stock or an enabled starting/setup grant. Unclassified direct
grant callers are fail-closed and remain vanilla.

## Baseline

1. Start the recomp **without** `universal-item-randomizer.nrm` enabled.
2. Load a known-good save and note several owned item ids/counts.
3. Save once and close the game. Keep a backup of this save directory.

## Test A — deterministic map pickup

1. Enable `Universal Item Randomizer` and set `SEED = 123456`.
2. Leave `STARTING ITEMS = OFF`, `KEY ITEMS = OFF` and `RANDOMIZE SHOPS = OFF`.
3. Load the baseline save and pick up a normal map/ground item.
4. Popup name/icon must match the inventory item.
5. Save, close, reopen with the same seed: existing inventory must be unchanged.
6. Repeat the same original pickup from a clean baseline copy: replacement must match.
7. Move to another map and test another ground item. A new map must be mapped as a
   new source generation even if a vanilla id equals the previous map's replacement.

## Test B — battle reward

1. Finish a battle that gives an item reward with seed `123456`.
2. Reward text/name must match inventory.
3. Owned count increments normally and never exceeds 99.
4. Equipment must not acquire a false unusable `1/1` state.

## Test C — secondary post-battle add

Exercise a path that reaches Bank-L's 14-entry transfer through `func_80172820`.
Confirm that the same original equipment maps identically across all covered
routes, full count is added and saturates at 99 without wrap, and the native-style
full `+0x02` rebuild covers both equipment and consumable lists immediately.
No unrelated inventory id/count may change.

## Test D — native save compatibility

1. Enable the randomizer, acquire randomized items and save.
2. Close the game completely.
3. Disable the randomizer and load that exact save.
4. Existing items must remain ordinary vanilla-valid item ids.
5. Save again with the mod disabled, close and reopen still disabled.
6. Load again, close, re-enable the randomizer and load the same file once more.

All transitions — ON→OFF, OFF→OFF after resave and OFF→ON — must load without
inventory reconstruction being interpreted as an acquisition.

The `+0x02` used-count column is transient and rebuilt from the roster. Randomizer
repair may correct that byte, but load-only steps must never rewrite item id or
owned count.

## Test E — seed is external, not save state

1. Load a randomizer-created save with seed `123456`; note inventory.
2. Close, change seed to `654321`, reopen and load the same save.
3. Existing inventory must not change; only future acquisitions use the new map.
4. Return to `123456`: a future copy of the same original item must again use the
   original 123456 replacement.

## Test F — starting/setup grants

`STARTING ITEMS` covers only two disassembly-audited Bank-R setup sources:

- `func_ovlR_8021592C`, whose grant at `0x80215BEC` loops literal consumable ids
  **1..6** during tutorial/practice setup. Its return address is `0x80215BF4`.
- `func_ovlR_80215C38`'s literal starting-consumable block, with `jal` sites
  `0x80217068..0x80217244`, corresponding to return-address window
  `0x80217070..0x8021724B`.

No broad Bank-R range is used.

### Starting items OFF

1. Start a clean New Game/practice flow with `STARTING ITEMS = OFF`.
2. Literal setup consumables must remain vanilla.
3. Normal pickups/rewards must still randomize.

### Starting items ON

1. Use a disposable New Game/practice save.
2. Set `STARTING ITEMS = ON`, `LOG = ON`, seed `123456`.
3. The log must show at least one bounded diagnostic:
   `universal-item-randomizer: Bank-R starting/setup grant recognized`
4. The tutorial 1..6 batch and/or map-loader literal starting grants that execute
   must be deterministically remapped.
5. Repeat on a clean save with the same seed and require identical replacements.
6. If the diagnostic never appears, do not widen the caller classification by guesswork.

### Sole remaining unclassified Bank-R caller

The whole-game grant scan leaves one Bank-R caller not yet semantically proven:
`jal 0x801DC740` at `0x80216D90` (return address `0x80216D98`). It remains vanilla.
With `LOG = ON`, reaching it emits the bounded diagnostic:

`universal-item-randomizer: unclassified Bank-R grant left vanilla`

If observed during campaign QA:

1. record the scene/event and original item;
2. repeat with the same seed and `STARTING ITEMS` OFF/ON;
3. the item must be identical in both runs;
4. only after the caller's source and role are proven may it receive a dedicated
   classification/source rewrite.

This is our remaining candidate for an as-yet-unclassified scripted/setup grant.

### Class-default equipment stays vanilla

The map loader also equips four class-derived defaults through `func_ovlN_801DD430`.
These are deliberately not covered. The game later reconstructs used counts from
the class-derived equipment source itself; randomizing only the owned-list grant
would separate that source from the owned id and can cause false `used/owned`
state. This path needs a source/reference-safe design before it can be enabled.

## Test G — key items

With `KEY ITEMS = OFF`, class-3/4 quest/key items remain vanilla. When testing
`KEY ITEMS = ON` on a disposable save, a key item may map only to another member
of the audited class-3/4 pool. It must never map into ordinary consumables,
equipment or unknown classes. Unknown consumable classes are identity-mapped.

## Test H — post-game regression

1. Finish the game with the randomizer enabled.
2. Save/post-game using the same campaign file.
3. Close completely and reopen/load with the randomizer enabled.
4. Close again and load with the randomizer disabled.
5. Save disabled, close, enable the mod and load once more.
6. All loads must succeed and owned ids/counts must remain identical across
   load-only steps.

This is the acceptance test for the older randomizer's reported failure mode.

## Test I — shops

Bank AB builds a zero-terminated raw `u16 item_word` list in a 0x200-byte buffer
whose pointer is stored at `0x80219F40`. The randomizer maps that source before
Bank AB builds the UI/detail/price/purchase caches.

### Shops OFF

Open a normal shop with `RANDOMIZE SHOPS = OFF`; stock, names and prices must be
vanilla, and a purchase must add exactly the displayed item.

### Shops ON

1. Enable shops with seed `123456` on a clean save.
2. Visible stock must change deterministically.
3. For equipment and consumables, list name/icon, detail, price and purchased id
   must all refer to the same replacement.
4. Same original item obtained by another covered route must map identically.
5. Reopening with same seed must reproduce stock; a different seed may change
   future stock without rewriting owned inventory.
6. Save after purchase, disable mod and load: save remains valid.

If a shop briefly displays vanilla stock before changing, or displayed/purchased
ids diverge, disable the shop option until timing is moved earlier.

## Test J — unclassified direct grants stay vanilla

Whenever campaign QA observes a grant outside the known pickup/reward/setup/shop
routes, record it and compare identical-seed runs with optional switches toggled.
It must remain identical unless explicitly classified. Never broaden the central
fallback merely to catch an unknown route.

## Acceptance criteria for 0.3.1

- map popup and inventory agree across map transitions;
- battle reward UI and inventory agree;
- post-battle counts saturate at 99 and used-count rebuild is correct;
- same seed gives the same replacement across every covered route;
- starting/setup and key-item behavior respects defaults/options;
- the sole unclassified Bank-R caller stays vanilla until proven;
- class-default equipment remains vanilla until source/reference coupling is safe;
- shops are internally consistent ON and fully vanilla OFF;
- changing seed never rewrites existing inventory;
- save ON→OFF→ON works;
- finish/post-game→close→reopen works with the same save;
- no unclassified direct grant is randomized accidentally.
