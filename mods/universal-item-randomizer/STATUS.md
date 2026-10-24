# Universal Item Randomizer 0.3.1 — engineering status

Status: **feature-complete for the currently safe acquisition model; real campaign QA pending**.

Do not promote this mod to 1.0 solely because CI is green. The remaining blocker is behavioural proof on a real Rev-A recomp build, especially native-save transitions and post-game loading.

## Core architecture

- External deterministic seed; no seed, flag, map id or randomizer metadata is stored in Ogre Battle 64's native save.
- One shared mapper is used by every covered acquisition route.
- Equipment pool: valid IDs 1..277. ROM sentinel 278 (`None`) is excluded.
- Consumables: IDs 1..40. Classes 0..2 are normal; audited key/quest classes 3..4 are protected by default and may only map inside their own pool when explicitly enabled.
- Unknown consumable classes remain identity-mapped.
- Main grant `func_ovlN_801DC740` and secondary post-battle grant `func_80172820(id,count)` are replaced.
- Count operations saturate at 99; full inventories never overwrite occupied slots.
- Both grant replacements reject invalid IDs/item-words before touching owned inventory.

## Proven acquisition/source coverage

All Rev-A callers of the main grant are classified. Covered display-sensitive routes are mapped at their source so UI and delivered item remain aligned:

- Table-O/map-object source;
- Table-P/ground-pickup source;
- battle reward queue;
- audited tutorial/starting direct grants, optional and OFF by default;
- Bank-AB shop raw stock, optional and OFF by default;
- secondary Bank-L post-battle equipment add.

The Bank-R per-unit consumable-28 loadout and class-default equipment remain vanilla because native references and owned inventory must be transformed atomically to stay safe.

## Source-generation and fail-closed hardening

- Table-O and Table-P shadows are keyed by `MAP_INDEX`.
- Table-O validates all 105 item words before any write.
- Pickup lists validate every active entry before any write.
- Battle reward queue validates all 20 slots before any write.
- Invalid source generations clear their shadow and remain untouched for that frame; no partial randomization.
- Reward zeroing, map changes and Table-O unload/reload are explicit generation boundaries.
- Main grant validates raw and mapped item-words.
- Post-battle add rejects original or mapped equipment IDs outside 1..277.

## Native-save policy

- Existing inventory is never scanned as an acquisition source.
- Load/save reconstruction is explicitly excluded from acquisition detection.
- Changing seed affects future acquisitions only.
- Saves created with the randomizer enabled contain ordinary vanilla-valid item IDs/counts and are intended to load with the mod disabled.
- `+0x02` used/equipped is transient bookkeeping, not custom persistence; repair only writes that byte.

## Configuration lifecycle

0.3.1 snapshots config once per process. `seed`, `key_items`, `starting_items`, `shops` and `log` are **not hot-reload settings**. After changing one, close the game completely and reopen it.

## Unified host verification suite

`python3 tools/test_universal_randomizer_all.py` is the single source of truth and `--count` exposes the suite size dynamically.

Current suite: **18 tests** covering save safety, mapper invariants, golden vectors, release/pipeline/version/config policies, audited caller/writer coverage, QA telemetry, 5,000 persistence sequences, source shadows, full Table-O validation, pickup/reward validation, grant validation, shop source behavior, capacity/count boundaries and `+0x02` repair boundaries.

The fast 18-test gate is green. Heavy package/runtime/QA-payload workflows are gated by the same suite before publishing artifacts.

## QA artifacts

Build manifests include source commit, Rev-A SHA-1, pinned runtime/Recomp commits, NRM SHA-256/size, dynamically derived suite count, save policy, restart-required config lifecycle and model/policy markers.

The QA payload carries `.nrm`, manifest, detailed protocol, short checklist, telemetry guide, status, golden vectors and `VERIFY-QA.ps1`. The PowerShell verifier checks required files, version, policy markers and `.nrm` SHA-256 before manual testing.

## CI efficiency

Package/runtime workflows rebuild only for code, headers, manifest/linker, tests, runtime patches or workflow changes. Documentation-only edits no longer waste a full runtime/MIPS build; the QA-payload workflow still reacts to documentation because docs are part of that deliverable.

## Remaining 1.0 blockers

- real Rev-A map-object/Table-O and ground/Table-P UI vs owned-item QA across map transitions;
- battle reward UI vs owned-item QA;
- post-battle count/use bookkeeping;
- shop OFF vanilla and shop ON list/detail/price/purchase consistency;
- audited starting/setup and protected coupled-loadout behavior;
- vanilla -> ON -> save -> OFF -> save -> ON on one native file;
- seed change after full restart with existing inventory unchanged;
- finish/post-game -> close/reopen ON -> close/reopen OFF -> save OFF -> reopen ON;
- enough campaign/regression coverage to expose scripted behavior not visible in static RE.

Optional future expansion, not a 0.3.1 blocker: atomically randomize class-default/recruit loadouts by transforming both native references and owned inventory to the same replacement.
