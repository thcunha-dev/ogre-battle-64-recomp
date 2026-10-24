# Universal Item Randomizer 0.3.1 — engineering status

Status: **feature-complete for the currently safe acquisition model; campaign QA pending**.

This file distinguishes static/CI proof from behaviour that still requires a real
Rev-A game run. Do not promote the mod to 1.0 solely because the build is green.

## Implemented and statically verified

- Deterministic external seed; no randomizer state is stored in the native save.
- One shared mapping for all covered routes; same original id + same seed gives
  the same replacement.
- Equipment and consumables remain in their own id/list spaces.
- Key/quest consumables are identity by default; optional key randomization is
  constrained to the audited key classes.
- Main Bank-N grant `func_ovlN_801DC740` is replaced with native id/count list
  semantics and bank-hook runtime support.
- Every Rev-A caller of the main grant is classified:
  - map object/drop source;
  - ground pickup source;
  - battle reward source;
  - tutorial/setup literal 1..6 grants;
  - map-loader literal starting-consumable block;
  - coupled per-unit consumable-28 loadout, deliberately left vanilla.
- Secondary post-battle equipment add `func_80172820(id,count)` is replaced and
  uses the shared mapper; count saturates at 99 before narrowing.
- Display-sensitive map/drop/pickup/reward sources are transformed before UI and
  final grant, avoiding popup/inventory mismatches and double mapping.
- Both Table-O/map-object and Table-P/ground-pickup source shadows are keyed by
  `MAP_INDEX`. RAM reuse across maps therefore cannot suppress a legitimate new
  mapping even when a new vanilla id exactly equals the replacement written on
  the previous map.
- Town shop stock is mapped at the Bank-AB source when `RANDOMIZE SHOPS` is ON;
  shops are vanilla by default.
- `+0x02` used counts are rebuilt from roster references without touching item
  ids, owned counts, seed or save metadata. Consumable id 40 is covered.
- Post-battle add forces the same full used-count rebuild as the native path.
- The old inventory-delta/save-load acquisition heuristic is gone.
- Save-load functions are explicitly excluded from acquisition detection.
- Class-change transfers, class-default equipment, debug/cheat writers and save
  reconstruction are classified as non-acquisition writers and are protected by
  CI from accidental hooking/patching.
- Class-default equipment and the coupled per-unit consumable-28 setup remain
  vanilla because their roster/source references must be changed atomically with
  owned inventory to be safe.
- `LOG` QA telemetry is route-scoped and bounded; it observes the major covered
  acquisition contexts without persisting state or reintroducing inventory-delta
  detection. See `QA-TELEMETRY.md`.

## Configuration lifecycle

0.3.1 intentionally snapshots randomizer configuration once per game process.
`seed`, `key_items`, `starting_items`, `shops` and diagnostic logging are **not
hot-reload settings**. After changing one of them, close the game completely and
reopen it; the new value becomes active on the **next launch / next process**.
Existing inventory remains untouched because configuration is external and only
future acquisitions use the newly constructed mapping.

This process-lifetime snapshot is deliberate for 0.3.1: it prevents a running
map/shop source from changing mapping policy halfway through a source generation.
Live hot-reload can be considered later only with explicit generation invalidation
for every mapped source.

## Host verification suite

`python3 tools/test_universal_randomizer_all.py` is the single source of truth for
all host-side verification. The suite count is exposed through `--count` so build
manifests derive the number automatically instead of hard-coding it. It currently
runs **14 tests**:

1. `tools/test_randomizer_save_safety.py`
2. `tools/test_universal_randomizer_mapping.py`
3. `tools/test_randomizer_golden_vectors.py`
4. `tools/test_randomizer_release_policy.py`
5. `tools/test_randomizer_pipeline_policy.py`
6. `tools/test_randomizer_version_consistency.py`
7. `tools/test_stock_runtime_coverage.py`
8. `tools/test_inventory_writer_taxonomy.py`
9. `tools/test_randomizer_qa_telemetry.py`
10. `tools/test_randomizer_persistence_model.py`
11. `tools/test_randomizer_source_shadow_model.py`
12. `tools/test_randomizer_shop_model.py`
13. `tools/test_randomizer_inventory_capacity_model.py`
14. `tools/test_randomizer_use_repair_model.py`

The release-policy contract locks the safety-critical manifest defaults: the mod
itself is disabled by default, seed defaults to 1, and shops, starting items, key
items and diagnostic logging all remain OFF. It also protects the explicit empty
`data_reference_syms_files` input required by the pinned RecompModTool.

The pipeline-policy contract requires every artifact-producing randomizer workflow
to execute this same unified suite before compiling or uploading `.nrm`, QA payload
or integrated artifacts. It also verifies that test-file changes retrigger those
workflows.

The version-consistency contract ties `mod.toml`, QA documentation and artifact
workflow names to the same `0.3.1` version so a partial version bump cannot create
mislabelled packages.

The golden-vector test locks the public seed semantics so accidental changes to
mixer constants, salts or Sattolo ordering cannot silently make an existing seed
produce different equipment replacements. For the QA seed `123456`, examples
include equipment `1 -> 270`, `2 -> 239`, `3 -> 37`, `100 -> 189`,
`200 -> 223` and `277 -> 245`.

The persistence model executes **5,000 deterministic ON -> OFF -> ON sequences**
with seed changes, mixed equipment/consumable acquisition, native-save round
trips, count saturation and key-item protection. It proves the intended policy:
loading never remaps existing ids; disabling or changing seed only affects future
acquisitions; the modeled native save contains item ids and counts only.

The source-shadow model exercises RAM reuse between maps/reward generations,
including the dangerous case where a new map's vanilla id equals the replacement
written into the previous map's RAM. Both pickup and drop-table map-generation
changes must force a fresh mapping while repeated frames on the same source remain
stable. Reward zeroing and drop-table unload/reload are also generation boundaries.

The shop model verifies that the Bank-AB raw stock source is transformed once,
keeps equipment/consumable list class through bit15, preserves the zero
terminator, fails closed on invalid/unterminated sources, and maps a freshly
rebuilt vanilla stock deterministically on the next shop opening.

The inventory-capacity model checks both acquisition paths at their fixed-slot
boundaries: a full list cannot overwrite an occupied record, existing stacks may
still grow and saturate at 99, new stacks claim the first empty slot, and zero
id/zero amount operations remain no-ops.

The used-count boundary model verifies equipment ID 277, consumable ID 40,
invalid-ID zeroing and saturation of reference counts at 255, and asserts that the
repair module never writes owned IDs or counts.

The save-safety contract scans every current and future `.c`/`.h` in the mod so a
new source file cannot silently add seed serialization, save hooks or custom
randomizer metadata outside the original audited files.

## Integrated build proof

Both the fast mapping workflow and the integrated runtime workflow invoke the
same unified host suite. The integrated job only continues after every current
suite test passes, then:

- applies the pinned OB64/N64Recomp/runtime layers;
- compiles the patched `librecomp` runtime;
- builds the MIPS mod ELF;
- builds the matching RecompModTool;
- packages the `.nrm` against Bank-N-augmented Rev-A references;
- emits a reproducible `BUILD-MANIFEST.txt` with source commit, pinned
  runtime/Recomp commits, Rev-A reference SHA-1, NRM SHA-256/size, dynamically
  derived host-suite count and explicit save/release/pipeline/model markers.

The current 14-test fast gate is green. A fresh full runtime/MIPS/NRM artifact for
the current Table-O generation fix remains the required artifact before campaign
QA is treated as the release-candidate proof.

A separate QA-payload workflow packages the `.nrm`, build manifest,
`TESTING.md`, `QA-TELEMETRY.md`, `STATUS.md` and `SEED-VECTORS.md` together so
manual campaign validation uses one traceable bundle rather than loose files.

## Static writer taxonomy

Normal owned-item mutations audited so far fall into these categories:

| category | routine/path | randomizer policy |
|---|---|---|
| acquisition | `func_ovlN_801DC740` | replace / map covered sources |
| acquisition | `func_80172820` | replace |
| class transfer | `func_80172C64` | never randomize |
| class transfer | `func_ovlM_801A4110` | never randomize |
| used-count rebuild | `func_8016B774` | bookkeeping only |
| save restore | `func_8016CEC4` and save marshalling | never acquisition |
| debug/cheat | `func_ovlS_801C214C` | ignore |
| class-default setup | `func_ovlN_801DD430` | vanilla until atomically mapped |
| coupled unit consumable setup | Bank-R caller RA `0x80216D98` | vanilla until atomically mapped |

The 40-slot consumable list is written by the same main grant in its bit15-clear
arm; no separate normal consumable grant routine has been found.

## Remaining release blockers

The main blockers are behavioural QA rather than missing central architecture:

- run the full `TESTING.md` matrix on a real Rev-A recomp build;
- prove popup/detail/price/purchased item agreement in shops;
- prove tutorial/starting diagnostics and deterministic results;
- test map transitions and repeated pickups/drop tables;
- test post-battle count/use bookkeeping;
- test save ON -> OFF -> ON with the same file;
- test finish/post-game -> close -> reopen, including mod disabled afterward;
- exercise key-item OFF through normal campaign progression;
- complete a campaign/regression pass to catch any scripted game behaviour not
  visible from the static writer/caller audit.

Optional future expansion, not a 0.3.1 blocker: safely randomize class-default
and per-unit starting loadouts by mapping both roster/source references and owned
inventory to the same replacement in one operation.
