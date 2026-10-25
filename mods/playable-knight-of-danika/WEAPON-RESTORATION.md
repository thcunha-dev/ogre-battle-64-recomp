# Knight of Danika — greatsword restoration policy

This restoration uses the playable Dragoon (`class 0x14`) as the compatibility baseline for weapon handling and attack presentation of an allied Knight of Danika (`class 0x71`).

## Design target

The allied Knight of Danika should:

- remain class `0x71`;
- keep the Knight of Danika armor, helmet, palette and visual identity;
- use a **greatsword / large-sword weapon family**;
- use Dragoon-compatible player-side pose, hand/weapon anchor and attack-animation structure wherever the original Danika lacks an allied-side equivalent;
- preserve the original enemy/front Knight of Danika presentation unchanged.

The goal is not to recolor a Dragoon.  Dragoon is a structural donor only.

## What may be inherited from Dragoon

Only proven compatibility components may be redirected or cloned:

1. player-side battle stance skeleton;
2. rear-facing attack frame sequence;
3. weapon hand/anchor offsets;
4. greatsword-compatible attack timing/event sequence;
5. equipment-category allowance if class `0x71` lacks the necessary player-side eligibility;
6. any side-specific animation metadata needed to prevent invalid-resource access.

Each item must be traced to its real consumer before patching.

## What must remain Danika-specific

- class ID `0x71`;
- stats/growth unless separately designed later;
- original enemy/front graphics;
- armor and palette;
- class name and identity;
- Danika-specific attacks/behavior unless a specific player-side animation dependency requires a compatibility shim.

## Crash-safety rule

Equipping a greatsword must never be implemented by blindly writing an item ID or copying the whole Dragoon class record.

Before enabling the weapon family we must prove all of the following:

- the equipment acceptance path recognizes the weapon as valid for the class;
- the battle renderer receives a valid player-side sprite/animation set;
- the animation references a valid weapon anchor and frame sequence;
- no enemy-only pointer/table is dereferenced on the allied side;
- formation/menu rendering remains valid;
- save/load stores only normal vanilla-compatible class/equipment IDs.

If any dependency remains unresolved, the restoration must fail closed to a known-safe compatible path rather than guess a pointer.

## Current baseline

- Player Dragoon: `0x14`
- Knight of Danika: `0x71`
- Hidden/enemy Dragoon-like entry: `0x9C`
- True Rev-A class-record base: `0x80187C34`
- Class stride: `0x48`

The weapon compatibility scanner is `tools/scan_danika_weapon_compat.py`.

It specifically ranks fields where `0x14 == 0x9C != 0x71` and correlates them with real class accessors/callers.  Those matches are candidates only; they are not automatically treated as weapon fields.
