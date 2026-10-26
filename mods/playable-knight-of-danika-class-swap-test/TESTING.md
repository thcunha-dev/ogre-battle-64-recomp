# Knight of Danika - Allied Class Swap Test

This is a temporary developer-only test mod. Its only purpose is to prove that
Knight of Danika / Gatekeeper class `0x71` can exist on the player's roster and
reach normal menus/battles before the final allied-only presentation override is
enabled.

## What it changes

The mod repeatedly scans the proven persistent player roster until the save has
loaded far enough to expose an allied Dragoon:

- roster base: `0x80193BE0`
- record stride: `0x38`
- class byte: `+0x12`
- maximum entries: 100

The first entry whose class byte is exactly playable Dragoon `0x14` is changed
to Knight of Danika `0x71`. No other class is eligible. After one successful
conversion, the mod performs no further writes for that process run.

The test does **not** scan or write the live enemy participant table. The enemy
Knight of Danika is therefore outside the write path by construction.

## Important save warning

The player roster is persistent game state. The test writes only RAM, but if the
game is subsequently saved, the changed class may be serialized into that save.
Use a disposable/copy save and do not overwrite an important save while this mod
is enabled.

## Test procedure

1. Make a backup/copy of the save.
2. Have at least one allied Dragoon (`0x14`) in the persistent roster.
3. Disable the read-only Danika battle-probe mod for this first smoke test.
4. Enable only `Knight of Danika - Allied Class Swap Test`.
5. Launch/load the copied save. The test will keep waiting read-only until a
   Dragoon appears in the loaded player roster.
6. Open the roster/unit screen and locate the Dragoon that was first in roster
   order. Its class should now resolve as class `0x71` / Knight of Danika.
7. Put that unit into a formation and enter a battle.
8. Observe separately:
   - whether the unit remains class `0x71`;
   - whether menus/stats can be opened without crashing;
   - whether the front visual/identity remains Danika;
   - whether rear pose, attack animation or weapon presentation are missing or
     incorrect. Those visual issues are expected to be the next hook target.
9. Exit without saving over the important/original save.

## Expected log

While no Dragoon is available yet, this is emitted only once:

`DANIKA_CLASS_SWAP waiting_for_dragoon`

When the first Dragoon is found:

`DANIKA_CLASS_SWAP 14->71 i=XX`

## Acceptance criteria for this milestone

The milestone passes if an allied roster character becomes class `0x71`, remains
selectable/usable through the unit UI, and reaches battle without corrupting the
enemy Danika or unrelated classes. Rear sprite/weapon/animation parity is a
separate presentation milestone and may still be incomplete in this build.
