# Universal Item Randomizer

Deterministic, save-safe item randomizer for Ogre Battle 64 Rev A.

## Two build paths

The project currently keeps two closely related architectures:

- **Enhanced 0.3.0** — includes a Bank-N `RECOMP_PATCH` for
  `func_ovlN_801DC740`, so it uses the small runtime bank-replacement layer. It
  also supports optional `STARTING ITEMS` for Bank-R direct tutorial/startup
  grants.
- **Stock-runtime compatibility build** — removes the Bank-N replacement and
  relies on the proven acquisition-source rewrites plus the streamedB
  `func_80172820` replacement. This build is intended for the unmodified 0.8.3
  runtime and intentionally omits `STARTING ITEMS`.

The stock-runtime path is the preferred 1.0 direction if its in-game tests pass:
the Rev-A ROM audit proves that every normal Bank-N gameplay grant consumes a
source that is already rewritten before delivery, so the custom Bank-N runtime
lookup is unnecessary for normal map/battle/shop play.

## Design rules

- **Native saves stay native.** The mod never stores seed, mapping, version,
  flags, or randomizer metadata in Ogre Battle 64's save.
- **Loading a save does not reroll inventory.** Existing inventory reconstruction
  is not treated as acquisition.
- **The seed is external configuration.** The same seed rebuilds the same mapping
  each launch.
- **Mappings are one-to-one.** Eligible pools use a Sattolo cycle: no collisions
  and no fixed point for pools larger than one.
- **Key items are protected by default.** Consumable classes 0..2 form the normal
  pool; classes 3..4 stay identity-mapped unless `KEY ITEMS` is enabled.

## Proven acquisition coverage

Implemented and MIPS-compiled:

- Table-O map-object source randomization for **both** Bank-N map callers.
- Table-P / ground-pickup source randomization, including its direct writer.
- Pending battle-reward queue randomization.
- Secondary streamedB post-battle add replacement `func_80172820(id,count)`.
- Bank-AB **raw shop-stock source** randomization so list, detail, price and
  purchased item all derive from the same replacement id.
- Transient `+0x02` used/equipped repair from the live roster.
- Immediate equipment use-count reconstruction after the post-battle add.
- Optional key-item pool randomization.

Enhanced-only:

- Bank-N universal grant replacement `func_ovlN_801DC740`.
- Optional Bank-R `STARTING ITEMS` direct grants.

A full Rev-A writer audit is in
`docs/UNIVERSAL-RANDOMIZER-WRITER-AUDIT.md`. It classifies the other meaningful
inventory writers as save/setup, equip/unequip/transfer, consumption, or
transient use-count maintenance and intentionally leaves them vanilla.

## Shop safety

The actual town shop is Bank AB (`ROM 0x1977B0 -> RAM 0x80214FA0`). Its stock
builder creates a 0x200-byte zero-terminated raw `u16 item_word` list and stores
its pointer at `0x80219F40`.

Before rewriting that source the mod requires:

1. the unique 16-byte Rev-A Bank-AB code fingerprint at `0x80214FA0`;
2. an aligned pointer inside RDRAM;
3. the vanilla stock prefix `1,2,3,4,5,6,8`;
4. a zero terminator inside the allocation;
5. every entry to validate as a real equipment/consumable id.

ROM analysis also proved the timing: the current overlay update is called at
`0x80075F58`, and `func_80072944` runs immediately after it at `0x80075F60`.
The Bank-N transition constructs the shop source and returns before that frame
hook, so the source can be mapped before Bank AB's next update consumes it.

`RANDOMIZE SHOPS` remains OFF by default until in-game QA is complete.

## Pool bounds proven from Rev A

- Equipment table: IDs `0..278`.
- Legitimate randomizable equipment: **1..277**.
- IDs `0` and `278`: `None` sentinels, excluded.
- Consumables: IDs `1..40`.
- Classes `0..2`: normal pool.
- Classes `3..4`: protected key/quest pool.

## Save policy

The mod never changes the native save structure. A randomized item is still just
a normal Ogre Battle 64 item ID/count in the save. Turning the mod off must not
require conversion or cleanup.

Required 1.0 regression matrix:

1. vanilla -> randomizer -> save -> vanilla;
2. randomizer -> save/load/restart -> same seed;
3. same save with a different seed (existing inventory unchanged);
4. map pickup popup == delivered item;
5. battle reward text == delivered item;
6. post-battle add count/use correctness;
7. shop list/detail/price/purchase agreement;
8. key item unchanged with `KEY ITEMS` OFF;
9. post-game/ending save reopen with mod ON and OFF.

See `TESTING.md` for the detailed protocol.

## Build status

The enhanced `0.3.0` package is green in GitHub Actions and produces a valid
`.nrm` containing `mod.json`, `mod_syms.bin` and `mod_binary.bin`.

Enhanced `.nrm` SHA-256:

`1f5fb45f696f3bbe7c9ecb894b71c4973476eabbf6699ea14abcff25bfc81b17`

The modified runtime `librecomp/src/overlays.cpp` translation unit also compiles
successfully after applying the OB64 project patch and the randomizer bank lookup
layer.

The project RecompModTool requires `data_reference_syms_files` to be present in
`mod.toml` even when empty. The manifest therefore declares
`data_reference_syms_files = []`; omitting that key triggers a null dereference
inside that tool version.
