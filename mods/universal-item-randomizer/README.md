# Universal Item Randomizer

A deterministic, save-safe replacement for the experimental Ogre Battle 64 item randomizer.

## Design rules

- **Native saves stay native.** The mod never stores a seed, mapping, version, flags, or other randomizer metadata in Ogre Battle 64's save data.
- **Loading a save does not reroll inventory.** Existing inventory is reconstructed by the game's save loader and does not pass through the universal grant replacement.
- **The seed is external configuration.** The same seed rebuilds the same mapping every launch.
- **Mappings are one-to-one.** Each eligible pool is shuffled with a Sattolo cycle, so two different source IDs cannot collapse onto the same replacement and (for pools larger than one) no item maps to itself.
- **Key items are protected by default.** Consumable classes 0..2 are the normal pool; classes 3..4 remain unchanged unless KEY ITEMS is explicitly enabled, in which case they are shuffled only among the key-item pool.

## Current coverage

Implemented and compile-tested:

- Bank-N universal grant replacement `func_ovlN_801DC740`.
- Equipment and consumable grants through that routine.
- Map-object drop table rewrite, so popup and received item agree for the proven table-driven path.
- Per-map ground pickup list rewrite.
- Pending battle-reward queue rewrite.
- New-game/tutorial direct grants are preserved by default and can be enabled with STARTING ITEMS.
- Unknown direct grant callers are preserved by default. The SHOPS option is currently a validation switch for these unclassified direct grants and should remain OFF for normal testing.

Still pending before calling this 1.0:

- The separate post-battle `func_80172820(id,count)` path used by one Bank-L caller.
- Classification/source synchronization for every scripted/cutscene/shop direct grant.
- The second map-object caller whose popup source is not yet rewritten before the universal grant.
- Full in-game Rev-A regression testing, especially used/equipped counts and post-game save compatibility.

## Why this does not use the old inventory watcher

The experimental randomizer watched inventory slots every frame and had to guess whether a burst of changes was a save load or a real acquisition. This version instead replaces the actual grant routine and only rewrites known source values that also feed the game's popup/reward UI. The frame hook never scans or rewrites existing owned-item records.

## Runtime support

Bank functions are recompiled outside the main ELF because their RAM ranges overlap. `patches/n64modernruntime-randomizer.patch` adds a reference-only `ROM -> BankFunctionEntry[]` registry so code-mod **replacements** can resolve a bank function without pretending those records are normal code sections or loading a bank early.

`tools/gen_bank_funcs.py` generates a static registrar for all bank records. `tools/prepare-universal-randomizer.sh` applies the runtime patch idempotently to a prepared local runtime tree and regenerates the bank registry.

## Build

For a normal full project tree with the Rev-A ROM-derived ELFs available:

```sh
./tools/prepare-universal-randomizer.sh
./tools/build-universal-randomizer.sh
```

The dedicated builder dumps symbols from the main ELF and all bank ELFs, merges them, verifies `func_ovlN_801DC740` is visible to RecompModTool, and packages `build/mods/universal-item-randomizer.nrm`.

GitHub Actions also performs ROM-less smoke tests: the runtime patches must compose, the mod must compile/link for MIPS, and a minimal Rev-A reference context is used to exercise RecompModTool packaging.

## Required save regression matrix

Before 1.0, all of these must pass on a real Rev-A build:

1. Vanilla -> save -> enable randomizer -> acquire item -> save -> disable randomizer -> load the same save.
2. Randomizer -> save -> close game -> reopen with the same seed -> load; existing inventory must remain untouched and future mappings must match.
3. Finish the game with the randomizer enabled -> save/post-game -> close -> reopen -> load the same save with the mod enabled and disabled.
4. Map pickup: popup name/icon must equal the item added to inventory.
5. Battle reward: reward text must equal the item added to inventory.
6. Key/quest item with KEY ITEMS off: identity must be preserved.
7. Starting setup with STARTING ITEMS off: vanilla starting inventory must be unchanged.
8. Shops with SHOPS off: purchase and displayed stock must remain vanilla.
9. Repeated grants and full stacks: count must clamp at the game's native limit (99).
10. Equipment availability: `used < owned` behavior must remain correct; no stale `+0x02` record may create a false `1/1` unusable item.
