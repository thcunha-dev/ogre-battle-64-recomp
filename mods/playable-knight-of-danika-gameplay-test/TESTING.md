# Knight of Danika - Playable Candidate

This build abandons the failed streamed-overlay hook approach. It does not hook battle overlay functions.

## Architecture

- Original enemy Danika remains class `0x71` and is not modified.
- Hidden Dragoon class `0x9C` is used as a dedicated player-only carrier.
- Vanilla `0x9C` has class alias `+0x45 = 0x14` (Dragoon).
- This mod changes only that hidden-class alias to `+0x45 = 0x71` (Danika).
- The first generic allied Fighter (`0x02`) is converted to class `0x9C`.
- Normal class accessors can therefore resolve Danika data through the game's existing alias mechanism while the original enemy Danika remains independent.

## Why this is safer

The Ogre Battle 64 recomp uses streamed/swappable banks. Static disassembly functions inside those banks are not necessarily registered as ordinary mod-hook targets at runtime. The previous `func_801AE794` build compiled but the runtime correctly rejected the hook because that function was not present in the mod-hook function registry.

This build uses only the already-proven resident hook `func_80072944` and direct writes to two known data fields:

1. hidden class `0x9C` alias byte (`record + 0x45`): exact vanilla `0x14` -> `0x71`;
2. one allied persistent-roster class byte (`+0x12`): exact Fighter `0x02` -> `0x9C`.

There are no battle-participant writes, no render-record writes and no enemy-class writes.

## Current validation target

The desired result is a normal allied character whose class resolves through `0x9C -> 0x71`, allowing us to validate whether the game's own alias path carries Danika presentation, equipment behavior and battle resources correctly. Native Change Class integration and endgame balancing come after this carrier is stable.

Use a copy/disposable save until native integration is complete.
