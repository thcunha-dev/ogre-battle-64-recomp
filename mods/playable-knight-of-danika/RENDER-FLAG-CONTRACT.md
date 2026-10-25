# Knight of Danika — battle renderer flag contract

This note locks the verified provenance of the context arguments passed to the real battle renderer. Its purpose is to prevent an allied-Danika patch from confusing class metadata with battle-side/orientation metadata.

## Verified chain

The real renderer is `func_801AD6C4` and its wrapper is `func_801B3868`.

The wrapper computes:

- renderer `a1 = (object+0x14 != 3)`
- renderer `a2 = (object+0xB4 & 0x2)`

The callback object is constructed by `func_801AE794`.

During that construction, `func_801AE794` calls `func_801B3D1C`. In the relevant loop it passes explicit output pointers including:

- `arg8 -> sp+0x50`
- `arg9 -> sp+0x54`
- `arg10 -> sp+0x58`

`func_801B3D1C` indexes battle-layout records with stride `0x1A`. Its relevant output mapping is:

- `record+0x02 -> a2 output`
- `record+0x04 -> a3 output`
- `record+0x06 -> arg5 output`
- `record+0x08 -> arg6 output`
- `record+0x0A -> arg7 output`
- `record+0x0C -> arg8 output`
- `record+0x0E -> arg9 output`
- `record+0x10 -> arg10 output`

Therefore in the callback-building loop:

`battle_record+0x0C -> sp+0x50`

`func_801AE794` then uses that same word twice:

1. bit 0 set -> `object+0x14 = 3`; bit 0 clear -> `object+0x14 = 2`;
2. the complete word is copied to `object+0xB4`.

Finally `func_801B3868` turns those object fields into renderer arguments. Thus both renderer context arguments are correlated views of one battle-layout flag word, `battle_record+0x0C`:

- renderer `a1` is the inverse boolean view of source bit 0;
- renderer `a2` is source bit 1 (`0x2`).

## Safety consequence

These are battle-layout flags, not class-table fields. Class ID `0x71` alone cannot be used as the allied override condition because enemy/front Knight of Danika must remain vanilla.

The required gate shape is:

`class == 0x71 && proven allied/rear battle-context condition`

Only then may the player-side resource/animation path borrow a Dragoon-compatible donor.

Until the meaning of `battle_record+0x0C` bits 0 and 1 is independently proven, executable patch code must not name either bit `allied`, `enemy`, `front`, or `rear`.

## Greatsword consequence

The 21 aligned class-record values where Dragoon `0x14 == 0x9C != Danika 0x71` remain structural candidates only. The proven renderer-side selector is outside the class record, so no whole-record or bulk-field copy is permitted.

## Fail-closed rule

If the battle side/orientation cannot be proven for an object, Knight of Danika uses the vanilla path. Enemy/front Danika is never redirected by default.
