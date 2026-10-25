# Playable Knight of Danika — research log

Goal: restore the Knight of Danika / Gatekeeper as a stable allied class, including a real player-side/rear battle presentation instead of relying on cheat-only behavior or fallback graphics.

## Confirmed class identities

- Player Dragoon: class ID `0x14`.
- Knight of Danika / Gatekeeper: class ID `0x71`.
- Hidden/enemy Dragoon-like entry: class ID `0x9C`.

These IDs are treated as the working reverse-engineering anchors for the first restoration pass.

## Rev-A class table contract

The verified Rev-A class table used elsewhere in this project begins at RAM `0x80187C62` with stride `0x48` bytes per class record.

Computed class-record addresses:

- Dragoon `0x14` -> `0x80188202`
- Knight of Danika `0x71` -> `0x80189C2A`
- hidden/enemy Dragoon `0x9C` -> `0x8018A842`

These are **class records, not sprite pointers**. Do not patch graphics by treating these addresses as image/animation data.

Verified Rev-A ROM SHA-1 used by the broader project: `d26b14bee422a09581ce438d45ba9fec9783fbb8`.

## Historical behavior to reproduce/fix

Old cheat/hacking documentation reports that class `0x71` can be inserted into the player's party and can retain class/stat/attack behavior, but lacks a proper player-side battle sprite configuration and can fall back to an unrelated soldier-like presentation or otherwise behave unsafely depending on context.

This strongly suggests that party storage and basic class data are not the primary blocker. The main restoration target is the graphics/animation lookup used when `0x71` is rendered from the allied side.

## Restoration strategy

1. Identify the battle renderer / asset lookup that maps class ID and battle side to sprite/animation resources.
2. Prove the player-side lookup behavior for `0x14`, `0x71`, and `0x9C` before applying any patch.
3. Preserve the original Knight of Danika enemy/front resource path unchanged.
4. Build the missing allied/rear resource set for `0x71` using the playable Dragoon `0x14` as the pose/animation skeleton where compatible.
5. Preserve Knight of Danika armor, helmet, sword, silhouette and palette identity rather than simply showing a Dragoon.
6. Patch only the player-side path needed for `0x71`; unknown classes must retain vanilla behavior.
7. Audit formation, equipment, attack, menu and save paths for any other enemy-only assumptions before release.

## Safety rules

- Never overwrite the global Dragoon resources to make Danika work.
- Never redirect all enemy-only classes to the same player sprite.
- Do not assume class records contain direct graphics pointers until proven from code/data flow.
- Prefer a class-specific player-side override over broad renderer changes.
- Any unsupported path must fail closed to vanilla/fallback behavior rather than dereferencing guessed pointers.

## Current milestone

Research foundation established. Next blocking discovery: locate the exact battle-side graphics/animation selection path and document the resource identifiers used by Dragoon `0x14` versus Gatekeeper `0x71`.
