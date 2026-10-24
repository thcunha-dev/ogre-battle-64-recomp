# Universal Item Randomizer 0.3.1 — engineering status

Status: **feature-complete for the currently safe acquisition model; real campaign QA pending**.

Do not promote this mod to 1.0 solely because CI is green. The remaining blocker is behavioural proof on a real Rev-A recomp build, especially native-save transitions and post-game loading.

## Core architecture

- External deterministic seed; no seed, flag, map id or randomizer metadata is stored in Ogre Battle 64's native save.
- One shared mapper is used by every covered acquisition route.
- Equipment pool: valid IDs 1..277. ROM sentinel 278 (`None`) is excluded.
- Consumables: IDs 1..40. Classes 0..2 are normal; audited key/quest classes 3..4 are protected by default and may only map inside their own pool when explicitly enabled.
- Unknown consumable classes remain identity-mapped.
- Mapping is deterministic and one-to-one; Sattolo cycles avoid collisions/fixed points for pools larger than one.
- Main grant `func_ovlN_801DC740` and secondary post-battle grant `func_80172820(id,count)` are replaced.
- Count operations saturate at 99; full inventories never overwrite occupied slots.
- Both grant replacements now reject invalid IDs/item-words before touching owned inventory.

## Proven acquisition/source coverage

All Rev-A callers of the main grant are classified. Normal display-sensitive routes are mapped at their source so UI and delivered item remain aligned:

- Table-O/map-object source;
- Table-P/ground-pickup source;
- battle reward queue;
- audited tutorial/starting direct grants, optional and OFF by default;
- Bank-AB shop raw stock, optional and OFF by default;
- secondary Bank-L post-battle equipment add.

The remaining Bank-R per-unit consumable-28 loadout is deliberately vanilla: the game writes ID 28 into the unit loadout before adding the owned copy. Mapping only the owned copy would split the reference from inventory. Class-default equipment is also deliberately vanilla until reference + owned item can be transformed atomically.

## Source-generation and fail-closed hardening

The latest hardening fixed a real stale-shadow bug class and made all display-sensitive sources transactional:

- Table-O and Table-P shadows are keyed by `MAP_INDEX`, so a new map cannot inherit an old map's coincidentally equal replacement.
- Table-O validates all **35 x 3 = 105 item words** before writing any replacement.
- Pickup lists validate every active entry before any write.
- Battle reward queue validates all 20 slots before any write.
- An invalid source generation clears its shadow and remains untouched for that frame; no partial randomization.
- Reward zeroing, map changes and Table-O unload/reload are explicit shadow-generation boundaries.
- Main grant validates raw and mapped item-words before inventory mutation.
- Post-battle add rejects original or mapped equipment IDs outside 1..277.

## Native-save policy

- Existing inventory is never scanned as an acquisition source.
- Load/save reconstruction is explicitly excluded from acquisition detection.
- Changing seed affects future acquisitions only.
- Saves created with the randomizer enabled contain ordinary vanilla-valid item IDs/counts and are intended to load with the mod disabled.
- `+0x02` used/equipped is transient bookkeeping, not custom persistence. Repair only writes that byte and derives references from native roster/class state.
- Equipment ID 277 and consumable ID 40 are covered; invalid references become zero-use and use counts clamp at 255.

## Configuration lifecycle

0.3.1 snapshots config once per game process. `seed`, `key_items`, `starting_items`, `shops` and `log` are **not hot-reload settings**.

After changing any of them, close the game completely and reopen it. The new value applies on the next process. Existing inventory remains unchanged.

## Unified host verification suite

`python3 tools/test_universal_randomizer_all.py` is the single source of truth. `--count` exposes the suite size so build manifests derive it automatically.

The suite currently contains **18 tests**:

1. save-safety contract;
2. shared mapper invariants;
3. deterministic golden seed vectors;
4. release-safe manifest/default policy;
5. artifact pipeline policy;
6. version consistency;
7. configuration lifecycle;
8. audited acquisition/caller coverage;
9. inventory-writer taxonomy;
10. bounded QA telemetry contract;
11. persistence model — 5,000 ON -> OFF -> ON sequences;
12. map/reward source-shadow generation model;
13. full Table-O fail-closed validation;
14. pickup/reward fail-closed validation;
15. main/post-battle grant validation;
16. Bank-AB shop source model;
17. inventory-capacity/count model;
18. `+0x02` use-repair boundary model.

The fast 18-test gate is green on the current code lineage. Heavy runtime/package/QA-payload workflows are also gated by this same suite before they may publish artifacts.

## Reproducible QA artifacts

Integrated and QA-payload manifests include:

- source commit/branch;
- Rev-A reference SHA-1;
- pinned runtime/N64Recomp commits;
- `.nrm` SHA-256 and size;
- dynamically derived host-suite count;
- `save_policy=no_randomizer_metadata_in_native_save`;
- `config_lifecycle=restart_required`;
- golden-vector/release-policy/pipeline-policy/model markers.

The self-contained QA payload carries:

- `universal-item-randomizer.nrm`;
- `BUILD-MANIFEST.txt`;
- `TESTING.md`;
- `QA-CHECKLIST.md`;
- `QA-TELEMETRY.md`;
- `STATUS.md`;
- `SEED-VECTORS.md`;
- `VERIFY-QA.ps1`.

`VERIFY-QA.ps1` checks required files, version, manifest markers and the `.nrm` SHA-256. CI executes it before uploading the QA payload and the Windows bundle path executes it again before staging the mod.

## CI efficiency

Package/runtime workflows now rebuild only for code, headers, mod manifest/linker, tests, runtime patches or workflow changes. Documentation-only edits no longer waste a full MIPS/runtime rebuild. The QA-payload workflow still reacts to documentation because those files are part of the deliverable.

## Golden seed reference

For QA seed `123456`, locked equipment examples include:

- 1 -> 270
- 2 -> 239
- 3 -> 37
- 100 -> 189
- 200 -> 223
- 277 -> 245

See `SEED-VECTORS.md` for the release reference.

## Remaining 1.0 blockers

The remaining weight is real-game validation, not missing central architecture:

- verify map-object/Table-O and ground/Table-P UI vs owned item across map transitions;
- verify battle reward UI vs owned item;
- verify post-battle counts and used-count rebuild;
- verify shops OFF are fully vanilla and shops ON keep list/detail/price/purchase synchronized;
- verify audited starting/setup behaviour and protected coupled loadouts;
- run vanilla -> randomizer ON -> save -> OFF -> save -> ON using the same native file;
- change seed only after full restart and verify existing inventory does not move;
- finish the game, save post-ending, close/reopen ON, close/reopen OFF, save OFF, reopen ON;
- run enough campaign/regression coverage to expose scripted behaviour not visible in static RE.

Optional future expansion, not a 0.3.1 blocker: atomically randomize class-default/recruit loadouts by transforming both native references and owned inventory to the same replacement.
