# Playable Knight of Danika — research log

Goal: restore the Knight of Danika / Gatekeeper as a stable allied class, including a real player-side/rear battle presentation instead of relying on cheat-only behavior or fallback graphics.

## Confirmed class identities

- Player Dragoon: class ID `0x14`.
- Knight of Danika / Gatekeeper: class ID `0x71`.
- Hidden/enemy Dragoon-like entry: class ID `0x9C`.

These IDs are the working reverse-engineering anchors for the restoration.

## Rev-A class table contract

The verified Rev-A class table begins at RAM `0x80187C62` with stride `0x48` bytes per class record.

Computed records:

- Dragoon `0x14` -> `0x80188202`
- Knight of Danika `0x71` -> `0x80189C2A`
- hidden/enemy Dragoon `0x9C` -> `0x8018A842`

These are **class records, not sprite pointers**. Do not patch graphics by treating these addresses as image/animation data.

Verified Rev-A ROM SHA-1: `d26b14bee422a09581ce438d45ba9fec9783fbb8`.

## Full 0x48-byte record extraction

The CI reverse-engineering probe now parses all 72 bytes for all three records directly from `asm/data/5C230.data.s` and produces byte and 16-bit diffs.

Important structural observations:

- Dragoon `0x14` and hidden Dragoon `0x9C` share the first resource-like words at offsets `+0x00`, `+0x02` and `+0x06`: `0x0017`, `0x00B4`, `0x00E0`.
- Knight of Danika `0x71` differs at those same positions: `0x0023`, `0x00BD`, `0x00E6`.
- Offsets `+0x08..+0x0E` are largely identical across all three records.
- The alias/key byte at record offset `+0x17` is `0x00` for Dragoon, `0x00` for Danika and `0x14` for hidden Dragoon. This is significant because the class accessor family explicitly reads that byte before deciding which record supplies the requested field.
- The three records diverge heavily after `+0x18`; those fields must not be copied wholesale from Dragoon to Danika.

These observations prove that Danika has its own class/resource identity and that a safe restoration should not replace the entire `0x71` record with the Dragoon record.

## Class-field accessor family

Repository-wide scanning found the executable direct references to the class-table base in `asm/40E80.s`.

### `func_8016DFA8`

This function:

1. masks both inputs to class-sized bytes;
2. computes `class_id * 0x48` exactly;
3. reads the first class's key byte at record offset `+0x17` (`D_80187C79`);
4. compares that key to the second selector;
5. returns the u16 at class-record offset `+0x00` from either the first or second record.

Sibling accessors repeat the same selection pattern for sequential record fields, e.g. `func_8016DFFC` reads offset `+0x02`, and the following family continues through later fields.

### `func_8016E52C`

This larger routine performs the same `class_id * 0x48` + `+0x17` alias/key resolution inline and fills several sequential u16 parameters from class-record offsets beginning at `+0x00`, `+0x02`, `+0x04`, etc.

The probe found exactly **four calls** to `func_8016E52C`, all inside `func_8017FC48`.

This is the first proven bridge from the class table into the higher-level resource-selection path.

## Candidate asset-selection bridge: `func_8017FC48`

`func_8017FC48` occupies `asm/40E80.s` around RAM `0x8017FC48` and is now a primary investigation target.

Static scan facts:

- 672 assembly lines/instructions/labels in the function body.
- 12 unique `jal` targets.
- four calls to `func_8016E52C`.
- one call to `func_8016E490` immediately after one expanded class-field set.
- 40 materializations of constants in the `0x01DE....` range.
- 62 references to runtime globals in the `D_8019....` range.
- after several `func_8016E52C` calls, the first resolved byte from the temporary output is used as an argument while a `0x01DE....` constant is prepared on another argument register before control converges on a shared path.

Examples of repeatedly selected constants include:

- `0x01DE6446`
- `0x01DE5B60`
- `0x01DE7098`
- `0x01DE365E`
- `0x01DE2E4E`
- `0x01DE4258`

These values are **not yet labelled sprite addresses**. They are proven resource-like constants in the class-data consumer path, but their exact asset role still requires downstream caller/loader proof.

## Why `0x9C` matters

Hidden Dragoon `0x9C` has `+0x17 = 0x14`. The accessor logic explicitly checks this key against an alternate class selector. Combined with the fact that `0x14` and `0x9C` share the early resource-like u16 values, this provides a concrete example of a class variant that can resolve through another class's resource fields.

That behavior is useful as a model for understanding how allied/enemy variants may share or override resource identities, but it is **not** permission to set Danika's `+0x17` to `0x14` blindly. Doing so could redirect more than battle graphics.

## Historical behavior to reproduce/fix

Old cheat/hacking documentation reports that class `0x71` can be inserted into the player's party and can retain class/stat/attack behavior, but lacks a proper player-side battle sprite configuration and can fall back to an unrelated soldier-like presentation or otherwise behave unsafely depending on context.

This suggests party storage and basic class data are not the primary blocker. The main restoration target remains the graphics/animation lookup used when `0x71` is rendered from the allied side.

## Restoration strategy

1. Continue downstream tracing from `func_8017FC48` to identify the exact loader/renderer semantics of the `0x01DE....` constants.
2. Prove the player-side lookup behavior for `0x14`, `0x71`, and `0x9C` before applying any graphics patch.
3. Preserve the original Knight of Danika enemy/front resource path unchanged.
4. Build the missing allied/rear resource set for `0x71` using playable Dragoon `0x14` as the pose/animation skeleton only where compatible.
5. Preserve Knight of Danika armor, helmet, sword, silhouette and palette identity rather than simply showing a Dragoon.
6. Patch only the player-side path needed for `0x71`; unknown classes must retain vanilla behavior.
7. Audit formation, equipment, attack, menu and save paths for enemy-only assumptions before release.

## Automated evidence

- `tools/audit_knight_of_danika.py` locks the class IDs, table base/stride, computed addresses and Rev-A contract.
- `tools/scan_danika_battle_lookup.py` scans direct/split address references, extracts complete target records, diffs fields, traces class-accessor callers and summarizes the `func_8017FC48` bridge.
- `.github/workflows/danika-research.yml` runs both tools on the mod branch and uploads `danika-battle-lookup-report` as an artifact.

Latest proven research run for the class-to-resource bridge: GitHub Actions run `40166130725`, successful at commit `2293e7c9b33f642fc0f688c902c22772669edb72`; report artifact `12588711601`.

## Safety rules

- Never overwrite the global Dragoon resources to make Danika work.
- Never redirect all enemy-only classes to the same player sprite.
- Do not assume class records contain direct graphics pointers until proven from code/data flow.
- Do not copy the entire Dragoon class record over Danika.
- Do not change Danika's `+0x17` alias/key merely because hidden Dragoon uses `0x14`; prove side effects first.
- Prefer a class-specific player-side override over broad renderer changes.
- Any unsupported path must fail closed to vanilla/fallback behavior rather than dereferencing guessed pointers.

## Current milestone

The project has moved beyond class-ID discovery into a proven class-to-resource-selection chain:

`class record (0x48 bytes)` -> `+0x17 alias/key resolution` -> `func_8016E52C` -> `func_8017FC48` -> downstream resource/load path.

Next blocking discovery: label the downstream consumer of the `0x01DE....` constants and identify which branch corresponds specifically to allied/rear battle presentation. Only then should the first graphics override be implemented.
