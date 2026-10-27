# Gatekeeper Pure Demo

Purpose: test the first fully coherent `0x71` promotion state.

## What this build changes
- Finds the second Fighter (`0x02`) in the persistent player roster.
- Reads Gatekeeper (`0x71`) class defaults from the real class table.
- Copies all four default equipment IDs into that character.
- Changes only that character's persistent class byte to Gatekeeper (`0x71`).

## What it deliberately does NOT do
- no Dragoon class bridge;
- no live participant/class mutation;
- no battle visual-selector mutation;
- no `func_801...` hook;
- no enemy writes;
- no hardcoded item IDs.

This is the clean counterpart to the proven Stable Dragoon Bridge. The previous direct Gatekeeper smoke test retained Fighter equipment (for example Blessed Sword), while the successful Dragoon bridge only became fully coherent after applying Dragoon's own class defaults. This build gives Gatekeeper the same fair test.

## Test
1. Disable every previous Gatekeeper/Danika development mod.
2. Use a backup/disposable save with at least two Fighters.
3. Enable only `Gatekeeper Pure Demo`.
4. Open the second Fighter's status/equipment page.
5. Record the class and the four equipped items.
6. Put the unit in Training.
7. If Training loads, capture one screenshot while idle/rear-facing and one during Slash.
8. If it black-screens, report that only; the failure then proves native Gatekeeper defaults are still insufficient for allied-side battle setup.

Do not save over an important save while this development build is active.
