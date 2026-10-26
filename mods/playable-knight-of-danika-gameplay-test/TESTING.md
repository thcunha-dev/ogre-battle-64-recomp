# Knight of Danika - Allied Gameplay + Battle Visual Test v2

This developer build keeps the proven gameplay conversion (first generic allied Fighter `0x02` -> Knight of Danika `0x71`) and adds a tightly gated battle-visual diagnostic.

## What v2 changes

The mod remembers the exact player-roster index it converted. During battle it only considers a visual override when that exact roster character is an active live participant.

It then requires exactly one active render record with class `0x71`. If two `0x71` render records exist (for example allied test Danika plus enemy Danika), it fails closed and changes nothing.

For that unique allied test record, it changes only the visual selector at render-record `+0x00`:

1. prefer a uniquely loaded Dragoon (`0x14`) selector;
2. if no Dragoon is loaded, use a uniquely loaded Knight (`0x05`) selector as a diagnostic fallback.

The render-record class word at `+0x02` is never changed, so the character remains class `0x71`.

## Safety

- Use a copy/disposable save.
- Do **not** save over an important save while the mod is enabled.
- The only persistent-roster write is the same exact Fighter `0x02` -> Danika `0x71` class-byte test.
- Live battle participant memory is read only; it is never written.
- Battle visual writes target only the unique `0x71` render record selector (`+0x00`).
- Enemy Danika present at the same time causes the visual override to refuse to run.
- No global Dragoon, Knight or Danika class-table record is changed.
- Disable the mod and restart the game after the test.

## Test

1. Replace the previous gameplay-test NRM with this v2 build.
2. Enable only `Knight of Danika - Allied Gameplay Test` among Danika development mods.
3. Load a disposable/copy save with at least one generic Fighter.
4. Locate the character that becomes `Gatekeeper` / class `0x71`.
5. Put that character into a deployable unit.
6. For the strongest test, have a Dragoon (`0x14`) in the same battle. If unavailable, a Knight (`0x05`) in the battle can serve as the diagnostic donor.
7. Enter combat and observe the Gatekeeper specifically.

### Success signal

If the Gatekeeper no longer appears as the Soldier fallback and instead takes the loaded Dragoon/Knight battle presentation, the selector path is proven. It is acceptable for this diagnostic to look like the donor class: this build is proving the presentation routing, not final artwork.

### Also record

- whether combat begins normally;
- whether attacks execute;
- whether the character remains `Gatekeeper` / class `0x71` in status screens;
- whether weapon/pose/animation follow the donor;
- whether the equipment preview is still Soldier (expected for now; that is a separate path).

Do not save the test state over an important save.
