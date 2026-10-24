# Universal Item Randomizer 0.3.1 — QA release checklist

Use this as the short execution sheet. `TESTING.md` remains the detailed source
of truth for each procedure. Do not mark 1.0 ready until every required box below
has evidence from a real Rev-A recomp build.

## Build identity

- [ ] `BUILD-MANIFEST.txt` says `version=0.3.1`.
- [ ] `source_commit` matches the tested branch artifact.
- [ ] `.nrm` SHA-256 matches `nrm_sha256` in the manifest.
- [ ] Rev-A reference SHA-1 is `d26b14bee422a09581ce438d45ba9fec9783fbb8`.
- [ ] Host suite count in manifest matches `python3 tools/test_universal_randomizer_all.py --count`.

## Configuration lifecycle

- [ ] Start with seed `123456`, shops OFF, starting items OFF, key items OFF.
- [ ] After every seed/option change, close the game completely and reopen it.
- [ ] Never interpret an in-process config edit as a supported hot-reload test.

## Deterministic acquisition

- [ ] Map-object/Table-O popup matches owned item.
- [ ] Ground/Table-P pickup popup matches owned item.
- [ ] Battle reward text matches owned item.
- [ ] Post-battle equipment transfer maps consistently and count saturates at 99.
- [ ] Same original ID maps to the same replacement across covered routes.
- [ ] At least one seed-123456 equipment result agrees with `SEED-VECTORS.md`.

## Map/source generation

- [ ] Move between at least two maps and acquire items on both.
- [ ] Revisit a previous map and verify sources map once, not twice.
- [ ] Verify a map-object/Table-O source after a map transition.
- [ ] Verify a ground/Table-P source after a map transition.
- [ ] Repeated frames do not visibly change a mapped source.

## Inventory integrity

- [ ] No unrelated item ID changes after any acquisition.
- [ ] No count exceeds 99.
- [ ] No false/stale used-count (`+0x02`) appears after new equipment.
- [ ] Consumable ID 40 behaves normally when encountered.
- [ ] Full inventory does not overwrite another occupied slot.

## Starting/setup

- [ ] `STARTING ITEMS = OFF` leaves audited setup grants vanilla.
- [ ] `STARTING ITEMS = ON` on a disposable New Game/practice save remaps audited setup grants.
- [ ] With LOG ON, starting/setup diagnostic appears when that route executes.
- [ ] Coupled per-unit consumable ID 28 remains vanilla/aligned.
- [ ] Class-default equipment remains vanilla/aligned.

## Key items

- [ ] `KEY ITEMS = OFF` preserves normal campaign progression/key IDs.
- [ ] Optional disposable test with `KEY ITEMS = ON` stays inside audited key classes 3/4.
- [ ] Unknown consumable classes remain identity-mapped.

## Shops

- [ ] Shops OFF: stock/name/detail/price/purchase are vanilla.
- [ ] Shops ON: stock changes deterministically after a full restart.
- [ ] List name/icon/detail/price/purchased ID all describe the same replacement.
- [ ] Reopening the same shop with the same seed reproduces stock.
- [ ] Changing seed after restart affects future stock only, not owned inventory.
- [ ] Save after a randomized purchase loads correctly with the mod disabled.

## Native save compatibility

- [ ] Vanilla save -> randomizer ON -> load succeeds.
- [ ] Acquire randomized items -> save -> close.
- [ ] Randomizer OFF -> load exact same save; IDs/counts unchanged.
- [ ] Save while OFF -> close -> reopen OFF; still valid.
- [ ] Re-enable randomizer -> reopen -> same save loads; existing IDs/counts unchanged.
- [ ] Change seed -> reopen -> existing inventory unchanged.
- [ ] Future acquisition uses the new seed.
- [ ] Return to seed `123456` -> reopen -> future mapping again matches golden semantics.

## Post-game acceptance

- [ ] Finish game with randomizer ON.
- [ ] Create/load the post-ending save with randomizer ON.
- [ ] Close completely and reopen ON; load succeeds.
- [ ] Close completely and reopen OFF; same save loads.
- [ ] Save while OFF, close, reopen ON; same file still loads.
- [ ] Owned IDs/counts are identical across load-only transitions.

## Regression pass

- [ ] Several battles completed without crash or inventory drift.
- [ ] Several map transitions completed without double-map symptoms.
- [ ] At least one shop transaction with shops ON completed normally.
- [ ] At least one save/restart cycle after meaningful campaign progress completed normally.
- [ ] No scripted progression item became unreachable with safe defaults.

## Release decision

- [ ] All mandatory boxes above have passed on one traceable QA artifact.
- [ ] No unresolved save/post-game issue remains.
- [ ] PR can leave draft only after the real-game evidence above exists.
