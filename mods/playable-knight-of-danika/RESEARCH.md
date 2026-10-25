# Playable Knight of Danika — research log

Goal: restore the Knight of Danika / Gatekeeper as a stable allied class, including a real player-side/rear battle presentation and safe greatsword support instead of relying on cheat-only behavior or fallback graphics.

## Confirmed class identities

- Player Dragoon: class ID `0x14`.
- Knight of Danika / Gatekeeper: class ID `0x71`.
- Hidden/enemy Dragoon-like entry: class ID `0x9C`.

These IDs are the working reverse-engineering anchors for the restoration.

## Corrected Rev-A class table contract

The true Rev-A class-record origin is RAM `0x80187C34`, with stride `0x48` bytes.

True aligned record starts:

- Dragoon `0x14` -> `0x801881D4`
- Knight of Danika `0x71` -> `0x80189BFC`
- hidden/enemy Dragoon `0x9C` -> `0x8018A814`

An earlier research pass incorrectly treated `0x80187C62` as the full-record origin. It is actually the `record+0x2E` field anchor used by a family of accessors. Likewise `0x80187C79` is `record+0x45`, not `record+0x17`.

The old computed addresses are still meaningful as addresses of the `+0x2E` field for each class:

- Dragoon `0x14` field `+0x2E` -> `0x80188202`
- Danika `0x71` field `+0x2E` -> `0x80189C2A`
- hidden Dragoon `0x9C` field `+0x2E` -> `0x8018A842`

They are metadata fields, not sprite pointers.

Verified Rev-A ROM SHA-1: `d26b14bee422a09581ce438d45ba9fec9783fbb8`.

## Why the alignment correction matters

`func_8016EBC4` independently indexes `D_80187C34 + class_id * 0x48`, proving the true record origin. The CI audit now locks this alignment so future research cannot regress to the older `0x62`-as-record-start model.

All class-field semantics from this point forward are expressed relative to the true `0x80187C34` record origin.

## Class-field accessor family

The accessor family in `asm/40E80.s` indexes class metadata with stride `0x48`. Several accessors use anchors inside the record, including the historical `D_80187C62` (`record+0x2E`) and `D_80187C79` (`record+0x45`).

The important safety lesson is that these accessors serve multiple gameplay/UI consumers. We must not redirect an entire Danika record to Dragoon just because a particular field is useful for player-side compatibility.

## False lead eliminated: `func_8017FC48` is text formatting

The deeper bridge tracer conclusively rules out `func_8017FC48` as the battle graphics loader.

Evidence includes string-length/copy behavior, zero-terminated output construction, control-code parsing and selection of `0x01DE....` banks that feed text bytes.

The following addresses in that path are therefore classified as text/string-resource banks, not sprite pointers:

- `0x01DE6446`
- `0x01DE5B60`
- `0x01DE7098`
- `0x01DE365E`
- `0x01DE2E4E`
- `0x01DE4258`

This closed a dangerous false path before any graphics patch was attempted.

## Real renderer path discovered

The search has reached real N64 display-list construction.

`func_801AD6C4`:

- participates in display-list rendering;
- touches the graphics state/global path including `D_800E9BA0`;
- receives a battle object whose descriptor is reached through `object+0x34`;
- reads class IDs from descriptor fields `+0x4B` and `+0x4F`;
- calls a class-field accessor during rendering.

One accessor used there resolves true `record+0x04`. For `0x14`, `0x71` and `0x9C` that field is `0x01`; the renderer only special-cases value `2`, consistent with scale/size handling rather than sprite selection. This field is therefore not our missing rear-sprite selector.

`func_801AD6C4` has a single identified caller, `func_801B3868`, which is now a high-value upstream target for tracing how the battle descriptor and visual resources are prepared.

## Battle object class selectors

The current rendering investigation follows the chain:

`battle object` -> `object+0x34 descriptor` -> class IDs at `descriptor+0x4B/+0x4F` -> renderer

This is substantially closer to the missing player-side resource lookup than the eliminated text path.

## Greatsword decision: Dragoon is the compatibility baseline

The allied Knight of Danika will use a **greatsword / large-sword weapon family**.

Player Dragoon `0x14` is the structural donor for weapon compatibility because it provides a known player-side humanoid sword-user baseline and is already our preferred pose/animation reference for the restored rear presentation.

This does **not** mean replacing Danika with Dragoon.

What may be inherited only after data-flow proof:

1. player-side stance skeleton;
2. rear-facing attack frame sequencing;
3. weapon hand/anchor offsets;
4. greatsword-compatible animation timing/events;
5. equipment-family eligibility if class `0x71` lacks a safe player-side entry;
6. side-specific animation metadata needed to prevent invalid resource access.

What remains Danika-specific:

- class ID `0x71`;
- original enemy/front presentation;
- armor, helmet, palette and silhouette;
- class identity/name;
- Danika stats/behavior unless separately redesigned later.

`tools/scan_danika_weapon_compat.py` now ranks fields where player Dragoon `0x14` and hidden Dragoon `0x9C` agree while Danika `0x71` differs, then correlates those offsets with known accessors and callers. Those matches are candidates only; unknown fields are never automatically copied.

See `mods/playable-knight-of-danika/WEAPON-RESTORATION.md` for the weapon safety contract.

## Why `0x9C` still matters

The hidden Dragoon-like entry provides a second reference for identifying structural values shared with playable Dragoon. If `0x14 == 0x9C != 0x71`, that is useful evidence that a field may belong to a Dragoon-compatible subsystem.

It is not enough by itself to prove weapon or graphics semantics. Downstream consumers must still be identified.

## Restoration strategy

1. Continue tracing `func_801B3868` and the battle descriptor construction path.
2. Prove the player/enemy-side resource selection used by `0x14`, `0x71` and `0x9C`.
3. Preserve the original Knight of Danika enemy/front path unchanged.
4. Build the missing allied/rear resource set for `0x71`, using Dragoon as the pose/animation skeleton where compatible.
5. Preserve Knight of Danika armor, helmet, sword design, silhouette and palette rather than simply showing a Dragoon.
6. Trace greatsword equipment acceptance and animation consumers before enabling the family for `0x71`.
7. Patch only class-specific player-side paths needed by `0x71`.
8. Audit formation, menu, equipment, attack, save/load and post-battle paths for enemy-only assumptions.

## Automated evidence

Current research tooling includes:

- `tools/audit_knight_of_danika.py` — locks IDs, true table base/stride and field anchors;
- `tools/audit_danika_class_layout.py` — extracts aligned 0x48-byte records and maps accessors to true offsets;
- `tools/scan_danika_battle_lookup.py` — searches class lookup consumers;
- `tools/trace_danika_asset_bridge.py` — permanently classifies the old `func_8017FC48` route as text;
- `tools/scan_danika_gfx_candidates.py` — ranks graphics-path candidates;
- `tools/trace_danika_gfx_pipeline.py` — deep-traces renderer candidates;
- `tools/scan_danika_renderer_accessors.py` — correlates class fields with renderer paths;
- `tools/scan_danika_battle_object_class_reads.py` — tracks battle-object class selectors;
- `tools/scan_danika_weapon_compat.py` — ranks Dragoon-compatible weapon/animation field candidates.

`.github/workflows/danika-research.yml` executes the research probes and publishes their reports as CI artifacts.

## Safety rules

- Never overwrite global Dragoon resources to make Danika work.
- Never replace the entire Danika class record with Dragoon's record.
- Never redirect all enemy-only classes to one player sprite.
- Do not assume class metadata fields are direct graphics pointers without data-flow proof.
- Do not patch `0x01DE....` text banks as graphics.
- Do not equip a greatsword by blindly forcing an item ID.
- Greatsword enablement requires a valid equipment path, player-side animation, weapon anchor and resource set.
- Preserve enemy/front Danika behavior.
- Prefer a class-specific allied-side override over broad renderer changes.
- Unsupported paths must fail closed to known-safe/vanilla behavior rather than dereference guessed data.

## Current milestone

Completed:

- class identities locked;
- true class-record origin corrected and CI-verified;
- old text-resource false path eliminated;
- real display-list renderer reached;
- battle descriptor class-byte path identified;
- Dragoon selected and documented as the greatsword/animation compatibility baseline;
- weapon compatibility scanner added to CI.

Next blocking discovery:

Trace the unique upstream renderer caller and descriptor/resource construction until the exact player-side visual/animation resource selector is proven. In parallel, use the new weapon compatibility report to isolate the smallest Dragoon-derived fields required for a crash-safe greatsword path.
