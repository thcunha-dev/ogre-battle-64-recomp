# Knight of Danika — render-context chain

This note records the narrow runtime path that determines two renderer context inputs for battle participants. It exists to prevent the playable-Danika restoration from confusing camera/layout flags with proven player/enemy ownership.

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

## What this does NOT prove

It does not prove that either bit means "player", "ally", "enemy", "left side", or "right side".

The current Danika gate remains deliberately fail-closed:

```text
class == 0x71 AND independently_proven_side == ALLIED
```

Until an ownership/team producer is traced into one of these context values, neither `record+0x0C bit0` nor `bit1` may activate the Dragoon donor path.

This restriction protects the original enemy/front Knight of Danika presentation from accidental replacement.

## Eliminated patch target

`func_8016DE3C` is not the missing rear-sprite selector. In the renderer it receives descriptor `+0x4B` and class ID at descriptor `+0x4F`, but resolves class-record `+0x04`, which is the same `0x01` category for Dragoon `0x14`, Danika `0x71`, and hidden Dragoon `0x9C`. The renderer only special-cases return value `2`, consistent with size/scale behavior.

Do not patch `func_8016DE3C` for playable Danika graphics.

## Next reverse-engineering target

Trace the provenance/semantics of `record+0x0C` inside resource `0x315736` and independently correlate it with a known player/enemy ownership field. In parallel, trace the class-bearing descriptor into the resource/animation selection below `func_801AD13C` and the battle asset loader so the temporary Dragoon rear-resource substitution can be attached to the smallest class-specific selector.
