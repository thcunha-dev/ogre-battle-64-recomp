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

The CI reverse-engineering probe parses all 72 bytes for all three records directly from `asm/data/5C230.data.s` and produces byte and 16-bit diffs.

Important structural observations:

- Dragoon `0x14` and hidden Dragoon `0x9C` share the first identifier-like words at offsets `+0x00`, `+0x02` and `+0x06`: `0x0017`, `0x00B4`, `0x00E0`.
- Knight of Danika `0x71` differs at those same positions: `0x0023`, `0x00BD`, `0x00E6`.
- Offsets `+0x08..+0x0E` are largely identical across all three records.
- The alias/key byte at record offset `+0x17` is `0x00` for Dragoon, `0x00` for Danika and `0x14` for hidden Dragoon. The class accessor family explicitly reads that byte before deciding which record supplies a requested field.
- The three records diverge heavily after `+0x18`; those fields must not be copied wholesale from Dragoon to Danika.

These observations prove that Danika has its own class identity and that a safe restoration must not replace the entire `0x71` record with the Dragoon record.

## Class-field accessor family

### `func_8016DFA8`

This function:

1. masks both inputs to class-sized bytes;
2. computes `class_id * 0x48` exactly;
3. reads the first class's key byte at record offset `+0x17` (`D_80187C79`);
4. compares that key to the second selector;
5. returns the u16 at class-record offset `+0x00` from either the first or second record.

Sibling accessors repeat the same selection pattern for sequential record fields, e.g. `func_8016DFFC` reads offset `+0x02`.

### `func_8016E52C`

This larger routine performs the same `class_id * 0x48` + `+0x17` alias/key resolution inline and fills several sequential values from class-record offsets.

The probe found exactly four calls to `func_8016E52C`, all inside `func_8017FC48`.

## False lead eliminated: `func_8017FC48` is a text formatter

The deeper bridge tracer conclusively rules out `func_8017FC48` as the battle graphics loader.

Evidence:

- The function parses an input byte stream from `$s6` and writes a zero-terminated output byte stream through `$s1`.
- It recognizes control sequences including values such as `0x8194`/`0x8196` and dispatches formatting substitutions.
- `func_80093460`, used in the same tail path, is a `strlen`-style byte counter: it advances until a zero byte and returns the length.
- `func_8009C550` is a `strcpy`-style routine: it copies bytes from `$a1` to `$a0` until the zero terminator.
- The shared path at `.L80180564` calls `func_8017FB18`, which resolves data from the selected `0x01DE....` bank and writes the resulting bytes into the output string before parsing resumes.
- The supposed resource constants also appear together in a data table near `0x80190E74`, consistent with a bank/table of text sources rather than a class battle-renderer dispatch table.

Therefore the following values are now classified as **text/string-resource bank addresses in this path**, not sprite pointers:

- `0x01DE6446`
- `0x01DE5B60`
- `0x01DE7098`
- `0x01DE365E`
- `0x01DE2E4E`
- `0x01DE4258`

This is useful negative evidence: it closes a large false path and prevents a dangerous patch to class fields based on UI/text behavior.

The class accessor calls inside `func_8017FC48` are consequently evidence about class-driven text/menu formatting only. They do **not** prove that the same early record fields are graphics IDs.

## Why `0x9C` still matters

Hidden Dragoon `0x9C` has `+0x17 = 0x14`, while `0x14` and `0x9C` share several early record values. This remains a concrete example of aliasing between class records, but its graphics meaning is not established.

Do not set Danika's `+0x17` to `0x14` blindly. That byte redirects multiple class-field accessors and can alter text, menu and other non-graphics behavior.

## New graphics-search target

The investigation now pivots away from the text formatter and toward the actual battle entity/resource setup path.

Priority evidence to trace:

1. consumers of the early class-record u16 values at offsets `+0x00`, `+0x02`, `+0x04`, `+0x06` outside text/UI code;
2. code that reads a battle unit's class byte and subsequently touches DMA/ROM loading, decompression, texture/sprite/animation data, display lists, palettes, or battle entity setup;
3. player/enemy side or orientation decisions made near those loaders;
4. any class-indexed tables where `0x14`, `0x71` and `0x9C` select different graphics metadata;
5. a path where the original enemy/front Danika resource can be preserved while only the allied/rear lookup receives a class-specific override.

The first three u16 pairs remain high-value candidates because `0x14` and `0x9C` match while `0x71` differs, but they are now deliberately called **identifier-like class fields**, not graphics IDs, until a downstream loader proves their semantics.

## Historical behavior to reproduce/fix

Old cheat/hacking documentation reports that class `0x71` can be inserted into the player's party and can retain class/stat/attack behavior, but lacks a proper player-side battle sprite configuration and can fall back to an unrelated soldier-like presentation or otherwise behave unsafely depending on context.

This suggests party storage and basic class data are not the primary blocker. The main restoration target remains the graphics/animation lookup used when `0x71` is rendered from the allied side.

## Restoration strategy

1. Locate the actual battle graphics/resource setup path; `func_8017FC48` is explicitly excluded.
2. Prove the player-side lookup behavior for `0x14`, `0x71`, and `0x9C` before applying any graphics patch.
3. Preserve the original Knight of Danika enemy/front resource path unchanged.
4. Build the missing allied/rear resource set for `0x71` using playable Dragoon `0x14` as the pose/animation skeleton only where compatible.
5. Preserve Knight of Danika armor, helmet, sword, silhouette and palette identity rather than simply showing a Dragoon.
6. Patch only the player-side path needed for `0x71`; unknown classes must retain vanilla behavior.
7. Audit formation, equipment, attack, menu and save paths for enemy-only assumptions before release.

## Automated evidence

- `tools/audit_knight_of_danika.py` locks the class IDs, table base/stride, computed addresses and Rev-A contract.
- `tools/scan_danika_battle_lookup.py` extracts complete target records and traces the class accessor family.
- `tools/trace_danika_asset_bridge.py` proved that `func_8017FC48` is a text/control-code formatting path and performs a caller/definition census around it.
- `.github/workflows/danika-research.yml` runs the research tools and uploads both reports.

Latest successful exclusion/bridge run: GitHub Actions run `40166324483` at commit `b7a7a5a8235f721b13b63559b5e0c2c040e9258a`; research artifact `12588147857`.

## Safety rules

- Never overwrite the global Dragoon resources to make Danika work.
- Never redirect all enemy-only classes to the same player sprite.
- Do not assume class records contain direct graphics pointers until proven from code/data flow.
- Do not copy the entire Dragoon class record over Danika.
- Do not change Danika's `+0x17` alias/key merely because hidden Dragoon uses `0x14`; prove side effects first.
- Do not patch the `0x01DE....` string-resource banks as graphics.
- Prefer a class-specific player-side override over broad renderer changes.
- Any unsupported path must fail closed to vanilla/fallback behavior rather than dereferencing guessed pointers.

## Current milestone

Class identities and the complete class records are mapped, the alias/accessor behavior is proven, and the first large candidate consumer has been definitively classified as text rather than graphics.

Closed false path:

`class record` -> `class accessors` -> `func_8017FC48` -> `0x01DE....` **text/string resources**

Next blocking discovery: locate the independent battle graphics loader/entity setup path and prove where class and battle side choose the front/rear visual resource set. Only then should the first graphics override be implemented.
