# Universal Item Randomizer 0.3.1 — engineering status

Status: **feature-complete for the currently safe acquisition model; real campaign QA pending**.

Do not promote this mod to 1.0 solely because CI is green. The remaining blocker is behavioural proof on a real Rev-A recomp build, especially native-save transitions and post-game loading.

## Current verification

- External deterministic seed; no randomizer metadata is stored in the native save.
- Shared one-to-one mapper for every covered route.
- Equipment IDs 1..277; consumables 1..40; audited key classes 3..4 protected by default.
- Main Bank-N grant and secondary post-battle equipment grant replaced.
- Display-sensitive Table-O, Table-P and battle-reward sources are mapped before UI/final grant.
- Table-O/Table-P shadows are generation-keyed by `MAP_INDEX`.
- Table-O validates all 105 words before write; pickup/reward sources validate the complete active generation before write.
- Invalid sources fail closed with no partial rewrite.
- Main and post-battle grants reject invalid IDs before owned-inventory mutation.
- Shops are source-mapped in Bank AB and remain OFF by default.
- `+0x02` repair only updates transient use bookkeeping.
- Config is snapshotted per process; seed/options require a full restart to change.

`python3 tools/test_universal_randomizer_all.py` is the single host-side verification entry point. The current suite contains **18 tests**, including 5,000 modeled ON -> OFF -> ON persistence sequences, source-generation models, golden seed vectors, release/pipeline/version/config contracts, fail-closed source/grant validation, shop, capacity and use-repair boundaries.

The fast 18-test gate is green. Package/runtime/QA-payload jobs are gated by the same suite before artifact publication.

## QA artifact

The self-contained payload carries the `.nrm`, build manifest, `TESTING.md`, `QA-CHECKLIST.md`, `QA-TELEMETRY.md`, `STATUS.md`, `SEED-VECTORS.md` and `VERIFY-QA.ps1`. The verifier checks required files, version, policy markers and `.nrm` SHA-256 before manual testing.

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
