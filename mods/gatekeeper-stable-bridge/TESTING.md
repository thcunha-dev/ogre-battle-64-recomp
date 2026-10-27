# Gatekeeper Stable Combat Bridge

Development-only stability baseline.

## What it does
- Finds the second Fighter (`0x02`) in the persistent player roster.
- Changes only that character's class byte to real playable Dragoon (`0x14`).
- Does not use Gatekeeper `0x71` in the battle pipeline.
- Does not touch live battle participant memory, visual selector tables, enemy data, or equipment bytes.

## Why
The previous direct `0x71` and hybrid `0x71`/`0x14` builds black-screened when entering Training. This bridge removes the mixed-class state and proves whether a fully coherent playable 2H class can enter Training from the same save.

## Test
1. Disable every previous Danika/Gatekeeper development mod.
2. Use a backup/copy save with at least two Fighters.
3. Enable only this mod.
4. Open the roster: the second Fighter should now be Dragoon.
5. Put that unit in Training.
6. Report whether Training loads, what weapon is visible, and whether attacks animate normally.

Do not save over an important save while this development mod is active.
