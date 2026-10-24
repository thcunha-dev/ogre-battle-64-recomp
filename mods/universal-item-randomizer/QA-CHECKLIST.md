# Universal Item Randomizer 0.3.1 — QA release checklist

Use this as the short execution sheet. `TESTING.md` remains the detailed source
of truth for each procedure. Do not mark 1.0 ready until every required box below
has evidence from a real Rev-A recomp build.

## Build identity

- [ ] Run `VERIFY-QA.ps1` and require `Universal Item Randomizer QA payload: PASS`.
- [ ] `BUILD-MANIFEST.txt` says `version=0.3.1`.
- [ ] `source_commit` matches the tested branch artifact.
- [ ] `.nrm` SHA-256 matches `nrm_sha256` in the manifest.
- [ ] Rev-A reference SHA-1 is `d26b14bee422a09581ce438d45ba9fec9783fbb8`.
- [ ] Host suite count in manifest matches `python3 tools/test_universal_randomizer_all.py --count` (currently 30).
- [ ] Manifest contains `persistence_model=5000_on_off_on_sequences`.
- [ ] Manifest contains `postgame_persistence_model=2000_finished_game_on_off_on_sequences`.
- [ ] Manifest contains `campaign_stress_model=1000_campaigns_x_600_events`.
- [ ] Manifest contains `use_repair=native_slot_indexed`.

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
- [ ] Table-P behaves normally with maps containing the largest practical pickup list.
- [ ] No Table-P test ever treats more than the physical 16 u16 IDs at `0x801F1004..0x801F1023` as item storage; `0x801F1024` is already adjacent metadata.

## Battle reward queue

- [ ] Exercise repeated item-reward battles with `LOG = ON`.
- [ ] Treat the 20-word reward queue beginning at `0x801936D8` per-slot; do not require a whole-queue all-zero state.
- [ ] Confirm displayed battle reward and delivered inventory item remain identical while multiple pending reward slots are present.
- [ ] When observing memory, confirm a consumed/reused physical slot passes through zero or changes away from its previous mod-written value before being reused as a fresh vanilla reward.
- [ ] Primary slot behavior is consistent with the proven Bank-N path: grant at `0x801E53DC`, native clear of `0x801936D8` at `0x801E53F4`.
- [ ] If one physical slot is observed being reused without a zero/change boundary, keep PR draft and reverse engineer that slot's lifecycle before 1.0.

## Inventory integrity / native `+0x02`

- [ ] No unrelated item ID changes after any acquisition.
- [ ] No count exceeds 99.
- [ ] No false/stale used-count (`+0x02`) appears after new equipment.
- [ ] Find at least one owned equipment whose **definition ID differs from its owned-list slot index**; equip/reference it and verify `+0x02` changes on that slot, not on the record whose slot number happens to equal the item ID.
- [ ] Repeat the same slot-vs-ID check for a consumable when practical; roster values are slot refs `<40`, not consumable definition IDs.
- [ ] During load/map setup, no `+0x02` rebuild is observed while only character or only unit roster is populated; first fully populated frame rebuilds correctly.
- [ ] Consumable ID 40 behaves normally when encountered; ID 40 may live in a valid slot `<40`, but roster reference value 40 itself is out of native slot range.
- [ ] Equipment ID 277 behaves normally when encountered.
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
- [ ] No unresolved save/post-game/reward-slot/use-count lifecycle issue remains.
- [ ] PR can leave draft only after the real-game evidence above exists.
