# Universal Randomizer — Rev-A inventory writer audit

ROM: `Ogre Battle 64 - Person of Lordly Caliber (USA) (Rev 1)`

SHA-1: `d26b14bee422a09581ce438d45ba9fec9783fbb8`

This audit exists to answer the 1.0 question: **which code paths really write
owned item ids/counts, and which of those are gameplay acquisitions that should
be randomized?** It intentionally distinguishes grants from save/setup,
equip/unequip and transient use-count maintenance.

## Central grant call graph

A raw scan of the entire Rev-A ROM for the MIPS encoding of
`jal 0x801DC740` found exactly **46** calls. Every call belongs to only two
modules.

### Bank N record 7 — gameplay

ROM `0x101D00` -> RAM `0x801AD5C0`:

| ROM call | RAM call | role |
|---:|---:|---|
| `0x1025E8` | `0x801ADEA8` | map-object/table-O grant |
| `0x1028C8` | `0x801AE188` | per-unit pending map-object grant |
| `0x110074` | `0x801BB934` | table-P/ground pickup path |
| `0x139B1C` | `0x801E53DC` | battle reward |

These four paths are covered by the central replacement and/or the source
rewrites that also feed the game's popup/reward UI.

### Bank R — setup/tutorial

All remaining 42 calls are inside Bank R's setup/tutorial module. This includes
its helper grants plus the unrolled starter-item batches around
`0x80217068..0x80217244`.

These are deliberately preserved when `STARTING ITEMS` is OFF and mapped when
that option is ON.

**Consequence:** there is no hidden third-party NPC/shop/cutscene caller of
`func_ovlN_801DC740` elsewhere in the Rev-A cart. Any acquisition outside these
paths must write inventory by another routine/source.

## Direct writers classified

The ROM was also scanned for MIPS stores using the owned-list field offsets:

- equipment id/use/count: `0x6B20 / 0x6B22 / 0x6B23`;
- 40-slot id/use/count: `0x3AE0 / 0x3AE2 / 0x3AE3`.

Raw matches in assets/data are not evidence. The meaningful code clusters were
mapped back to their streamed modules and inspected.

### streamedB (`ROM 0x40E80`)

Contains save/load/list helpers, use-column rebuilds and
`func_80172820(id,count)`.

Randomizer action:

- save/load/rebuild: **preserve**;
- `func_80172820`: **replace** because its only game caller is the separate
  Bank-L post-battle 14-entry add path.

### Bank B tutorial record 17 (`ROM 0x69920`)

Writer clusters near `0x6D69C..0x6DF14` clear/copy temporary tutorial state
into the owned lists during scene setup.

Randomizer action: **preserve**. This is reconstruction/setup, not a reward.

### Bank M scene 0x05 (`ROM 0x79750`)

Writer cluster around `0x83110` moves equipment between character slots and
adjusts `+0x02` references.

Randomizer action: **preserve**. This is equip/transfer state.

### Bank S Organize Screen (`ROM 0x87220`)

Writer clusters around `0xBB864`, `0xC9FA4`, `0xCA178` belong to organize /
equip/unequip list maintenance.

Randomizer action: **preserve**.

### Bank N record 7 (`ROM 0x101D00`)

The central grant itself is covered by `RECOMP_PATCH`.

An isolated writer at ROM `0x1193EC` / RAM near `0x801C4CAC` was inspected: it
searches the 40-slot list, decrements the `+0x02` use/reference byte and clears
a unit-side source byte.

Randomizer action: **preserve**. It is reference cleanup, not acquisition.

### Bank AB shop (`ROM 0x1977B0`)

The shop purchase helper writes owned lists, but patching it would be too late
for UI consistency. The randomizer instead rewrites Bank AB's **raw stock
source** at the pointer stored in `0x80219F40` before the shop builds its sorted
caches. The game's own name, price, quantity and purchase state then derive from
the same replacement id.

Randomizer action: **source rewrite** when `RANDOMIZE SHOPS` is enabled.

### Bank AE (`ROM 0x1A9260`)

- `0x1AAFxx / 0x1AB2xx`: consumption/removal and use-count maintenance;
- `0x1AFCxx`: table-P direct add.

Randomizer action:

- maintenance/consumption: **preserve**;
- table-P add: already **covered by rewriting `0x801F1004`**, the same source
  used by popup and delivery.

### Bank AF (`ROM 0x1B2640`)

Writer cluster `0x1B6C04..0x1B6DAC` reads class-derived equipment ids and
increments/caps the equipment `+0x02` use byte. It does not create owned items.

Randomizer action: **preserve**.

### Bank J (`ROM 0x213AE0`)

Writer around `0x2144AC` computes four class/default equipment ids and inserts /
marks them for character/unit setup.

Randomizer action: **preserve**. This is structural equipment state, not loot.
A future recruit/class-gear mode can treat it separately if desired.

### Bank I New Game scene 0x16 (`ROM 0x244770`)

Clusters `0x2494xx..0x24A1xx` create/copy character records, class equipment and
owned-list state, then invoke the native use-column rebuild.

Randomizer action: **preserve**. This is New Game character/setup state.

## Current acquisition coverage from the audit

Randomized real acquisition sources now include:

1. Bank-N table-O/map object grants;
2. Bank-N pending per-unit map-object grant, with popup synchronization;
3. table-P / ground pickups, including its direct writer path;
4. battle reward queue / Bank-N reward grant;
5. Bank-L secondary post-battle `(id,count)` path via `func_80172820`;
6. Bank-AB shop stock source when the shop option is enabled;
7. optional Bank-R starter/tutorial direct grants.

The remaining meaningful inventory writers inspected so far are save/setup,
equipment-transfer or transient use-count maintenance and are intentionally not
randomized.

## Why this matters for save safety

The old inventory-delta randomizer could not reliably distinguish a real grant
from a save/setup burst. This audit lets the new implementation do the opposite:
randomize only proven acquisition sources and leave structural reconstruction
alone. No acquisition decision depends on "N slots changed this frame".
