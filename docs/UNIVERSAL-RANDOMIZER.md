# Universal Item Randomizer

Branch: `randomizer/universal-grant`

## Goal

A deterministic, save-safe Ogre Battle 64 item randomizer that randomizes real
acquisition paths rather than reinterpreting inventory deltas after the fact.
The native save format is never extended and never stores a seed, mapping,
version flag or randomizer metadata.

## Current architecture

### 1. Central Bank-N grant

`func_ovlN_801DC740(item_word)` is replaced with `RECOMP_PATCH`.

- bit 15 selects the inventory (`1` = 278-slot equipment list, `0` = 40-slot
  consumable/key-item list);
- low 15 bits are the item id;
- known pickup/reward sources are rewritten before the UI consumes them, so
  popup text and delivered item stay synchronized;
- direct setup grants are preserved unless `STARTING ITEMS` is enabled;
- unknown direct grants remain vanilla by default; `RANDOMIZE SHOPS` is still
  validation-mode until Bank-AB shop display/stock is classified.

The runtime patch adds a bank-function lookup fallback used by function
replacements. It does not insert streamed banks into `sections_info` and does
not change DMA, save-state or overlay loading semantics.

### 2. Secondary post-battle add

`func_80172820(id,count)` is a separate streamedB acquisition path. Reverse
engineering found one game caller: Bank-L `func_ovlL_80235334`, which passes
u16 ids/counts from a 14-entry post-battle table.

It now has its own `RECOMP_PATCH`:

- maps the equipment id through the same deterministic equipment permutation;
- adds the supplied count with the vanilla cap of 99;
- fills the first empty slot when necessary;
- immediately rebuilds the equipment `+0x02` use column from the roster.

### 3. Transient `+0x02` repair

The save does not store `+0x02`; the game reconstructs it from the live roster.
A newly occupied record can otherwise inherit a stale byte from an old empty
slot and display `1/1` / refuse equip.

`use_repair.c` therefore runs a second frame hook that:

- waits until both character and unit roster structures are populated;
- reconstructs the proven roster reference counts;
- writes only `+0x02`;
- never changes item ids or owned counts;
- snapshots ids and only runs a full repair again when an id changes.

This is deliberately not an acquisition detector and does not randomize load
reconstruction.

## Deterministic mapping

Each eligible pool uses a Sattolo cycle built from `SEED`.

Properties:

- same seed -> same mapping after restart;
- no two source ids collide on one replacement within a pool;
- for pools larger than one, an eligible item never maps to itself;
- no mapping table is written to the game save.

Consumables of classes 3/4 (quest/key-item groups) stay identity-mapped by
default. `KEY ITEMS` enables a separate permutation only inside that group.

## UI/source synchronization already covered

The per-frame source hook rewrites only future acquisition sources, never the
owned inventory:

- Bank-N drop table at `0x801EDB38`;
- ground/table-P pickup list at `0x801F1004`;
- battle reward queue at `0x801936D8`.

Source shadows prevent the mod from mapping its own value a second time. A map
reload/restored raw value is mapped again deterministically.

## Shop status

The actual town shop is Bank AB (`ROM 0x1977B0`, RAM `0x80214FA0`). Its stock,
display and purchase flow still need exact classification before shops can be
randomized safely. `RANDOMIZE SHOPS` therefore remains OFF by default and is not
considered a finished 1.0 feature yet.

## Build/CI state

Automated GitHub Actions currently verifies all of the following without a ROM:

1. Python tooling syntax;
2. main+bank symbol dump merge;
3. N64ModernRuntime project patch + randomizer patch compose cleanly;
4. every C source in `mods/universal-item-randomizer/src/` compiles for MIPS;
5. the linked ELF contains recomp hook/patch sections;
6. both acquisition replacement symbols resolve;
7. RecompModTool packages the result into a valid `.nrm`;
8. the `.nrm` is uploaded as a workflow artifact.

The current package contains `mod.json`, `mod_syms.bin` and `mod_binary.bin`.
The WIP package version is `0.2.0`.

## Remaining 1.0 work

- run the packaged mod inside the Rev-A recomp build;
- verify map pickup, ground pickup, battle reward and post-battle 14-entry add;
- run vanilla -> randomizer -> vanilla save compatibility;
- run randomizer save/load/restart with identical seed mapping;
- run post-game/ending save test;
- classify Bank-AB shop stock/display/purchase path before enabling shops by
  default;
- classify any remaining script/NPC direct-grant caller before treating unknown
  callers as randomizable by default.

## Required QA matrix

| Test | Expected result |
|---|---|
| Vanilla save -> randomizer -> acquire -> save -> randomizer OFF -> load | Save loads; existing inventory stays exactly as saved |
| Randomizer -> save -> close -> same seed -> load | Existing inventory untouched; future mapping identical |
| Different seed on same save | Existing inventory untouched; only future acquisitions use new map |
| Map pickup | Popup item == delivered item |
| Battle reward | Reward text/item == delivered item |
| Post-battle secondary add | Mapped equipment/count added, use count valid |
| New-game/setup with STARTING ITEMS OFF | Vanilla starting items |
| New-game/setup with STARTING ITEMS ON | Deterministically mapped starting items |
| KEY ITEMS OFF | Quest/key item ids remain vanilla |
| Post-game save/reopen | Save remains loadable with mod on or off |
