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
- Pickup source shadow is keyed by map index so RAM reuse across maps cannot
  suppress a legitimate new mapping by coincidence.
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

## CI contracts

The integrated runtime workflow must pass all five architecture/QA gates before
it builds the runtime/mod:

1. `tools/test_randomizer_save_safety.py`
2. `tools/test_universal_randomizer_mapping.py`
3. `tools/test_stock_runtime_coverage.py`
4. `tools/test_inventory_writer_taxonomy.py`
5. `tools/test_randomizer_qa_telemetry.py`

It then compiles the patched runtime, builds the MIPS mod ELF, builds the matching
RecompModTool and packages the `.nrm` against Bank-N-augmented Rev-A references.

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
- test map transitions and repeated pickups;
- test post-battle count/use bookkeeping;
- test save ON -> OFF -> ON with the same file;
- test finish/post-game -> close -> reopen, including mod disabled afterward;
- exercise key-item OFF through normal campaign progression;
- complete a campaign/regression pass to catch any scripted game behaviour not
  visible from the static writer/caller audit.

Optional future expansion, not a 0.3.1 blocker: safely randomize class-default
and per-unit starting loadouts by mapping both roster/source references and owned
inventory to the same replacement in one operation.
