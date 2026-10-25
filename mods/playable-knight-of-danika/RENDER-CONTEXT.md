# Knight of Danika — render-context chain

This note records the narrow runtime path that determines two renderer context inputs for battle participants. It exists to prevent the playable-Danika restoration from confusing camera/layout/resource-group flags with proven player/enemy ownership.

## Proven data path

The battle record package loaded at resource address `0x315736` installs a table pointer in `D_801BA6D8` through `func_801B3BD8`.

`func_801B3D1C(group, slot, ...)` resolves a record from that table. Its per-slot record stride is `0x1A` bytes. The record fields are copied through output pointers supplied by the caller.

For the render-object construction call in `func_801AE794`:

- `record+0x02` -> descriptor `+0x4C` (class word; low byte at descriptor `+0x4F` is class ID);
- `record+0x04` -> caller stack `+0x4C`;
- `record+0x06` -> descriptor `+0x5C`;
- `record+0x08` -> descriptor `+0x60` (with the special `0x8000` sign-preserving case);
- `record+0x0A` -> descriptor `+0x64`;
- **`record+0x0C` -> caller stack `+0x50`;**
- `record+0x0E` -> caller stack `+0x54`;
- `record+0x10` -> caller stack `+0x58`.

The `record+0x0C` value is then used in two independent ways:

1. `sp+0x50 & 1` selects render object byte `object+0x14`:
   - bit 0 set -> state `3`;
   - bit 0 clear -> state `2`.
2. the full `sp+0x50` value is copied to `object+0xB4`.

The callback `func_801B3868` transforms those values before entering the real display-list renderer `func_801AD6C4`:

- renderer `a1 = (object+0x14 != 3)`;
- renderer `a2 = object+0xB4 & 0x2`.

Therefore **bit 0 and bit 1 of battle-record `+0x0C` are genuine renderer-context inputs**.

## Resource-group selector is not side

A second nearby state variable, `D_801BA72D`, has now been separated from ownership semantics.

`func_801B2D2C` accepts a selector bounded to eight modes, indexes `D_801B9540`, stores the selected resource-group value in `D_801BA72D`, and feeds its low byte to `func_801ACF60`. The currently observed eight table values are:

- mode 0 -> `0x003E`
- mode 1 -> `0x0025`
- mode 2 -> `0x8004`
- mode 3 -> `0x0035`
- mode 4 -> `0x0034`
- mode 5 -> `0x0039`
- mode 6 -> `0x800E`
- mode 7 -> `0x0000`

This makes `D_801BA72D` a **multi-mode battle resource-group selector**, not a boolean allied/enemy flag. It must not be used as `DANIKA_SIDE_ALLIED`.

`tools/trace_danika_resource_group_selector.py` locks this classification in CI so a future patch cannot accidentally regress to treating the selector as ownership state.

## What this does NOT prove

It does not prove that either `record+0x0C` bit means "player", "ally", "enemy", "left side", or "right side".

The current Danika gate remains deliberately fail-closed:

```text
class == 0x71 AND independently_proven_side == ALLIED
```

Until an ownership/team producer is traced into one of these context values, neither `record+0x0C bit0`, `bit1`, nor `D_801BA72D` may activate the Dragoon donor path.

This restriction protects the original enemy/front Knight of Danika presentation from accidental replacement.

## Eliminated patch target

`func_8016DE3C` is not the missing rear-sprite selector. In the renderer it receives descriptor `+0x4B` and class ID at descriptor `+0x4F`, but resolves class-record `+0x04`, which is the same `0x01` category for Dragoon `0x14`, Danika `0x71`, and hidden Dragoon `0x9C`. The renderer only special-cases return value `2`, consistent with size/scale behavior.

Do not patch `func_8016DE3C` for playable Danika graphics.

## Next reverse-engineering target

Trace the provenance/semantics of `record+0x0C` inside resource `0x315736` and independently correlate it with a known player/enemy ownership field. In parallel, `tools/trace_danika_visual_descriptor_init.py` inventories `func_801AD13C` and its callers to locate the class-bearing resource/animation decision feeding the renderer. The temporary Dragoon rear-resource substitution may be attached only after both class-resource provenance and allied ownership are independently proven.
