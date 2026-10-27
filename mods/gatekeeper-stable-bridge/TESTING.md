# Gatekeeper Stable Combat Bridge

Development-only stability baseline.

## What it does
- Finds the second Fighter (`0x02`) in the persistent player roster.
- Replaces its four stored equipment IDs at `+0x2A/+0x2C/+0x2E/+0x30` with the real class-default equipment IDs from playable Dragoon (`0x14`).
- Changes that character's class byte to real playable Dragoon (`0x14`).
- Does not use Gatekeeper `0x71` in the battle pipeline.
- Does not touch live battle participant memory, visual selector tables, or enemy data.

## Why
The previous direct `0x71` and hybrid `0x71`/`0x14` builds black-screened when entering Training. They also left Fighter equipment such as Blessed Sword attached to a different battle package. This bridge removes both mixed-class and mixed-equipment state and gives the engine one fully coherent playable 2H class before Training loads.

## Test
1. Disable every previous Danika/Gatekeeper development mod.
2. Use a backup/copy save with at least two Fighters.
3. Enable only this mod.
4. Open the roster: the second Fighter should now be Dragoon and its equipment should change to Dragoon defaults.
5. Put that unit in Training.
6. Report whether Training loads, which weapon is visible, and whether attacks animate normally.

This is intentionally not the final Gatekeeper presentation. If Training loads correctly, the next step is to keep this stable Dragoon combat package and layer Gatekeeper body/palette/helmet/shoulder visuals on top while preserving dynamic weapon rendering.

Do not save over an important save while this development mod is active.
