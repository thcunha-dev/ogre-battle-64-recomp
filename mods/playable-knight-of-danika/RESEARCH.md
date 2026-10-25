# Playable Knight of Danika — research log

Goal: restore the Knight of Danika / Gatekeeper as a stable allied class with a real rear/player-side battle presentation and safe greatsword support, without replacing its identity with Dragoon or changing the original enemy/front presentation.

## Locked identities and Rev-A layout

- Player Dragoon: class ID `0x14`.
- Knight of Danika / Gatekeeper: class ID `0x71`.
- Hidden/enemy Dragoon-like entry: class ID `0x9C`.
- True class-record base: RAM `0x80187C34`.
- Class-record stride: `0x48`.
- Dragoon `0x14` record: `0x801881D4`.
- Danika `0x71` record: `0x80189BFC`.
- hidden Dragoon `0x9C` record: `0x8018A814`.
- Verified Rev-A ROM SHA-1: `d26b14bee422a09581ce438d45ba9fec9783fbb8`.

The older anchor `0x80187C62` is `record+0x2E`, not the start of a record. `D_80187C79` is `record+0x45`.

## Eliminated false path: text resources

`func_8017FC48` and the `0x01DE....` banks are text/string formatting resources, not battle graphics. They must never be patched as sprite data.

## Important correction: the `0x315736` renderer path is static scene data

Earlier research correctly proved that `func_801AD13C` is a genuine visual resource loader/cache, but incorrectly promoted one of its callers to the normal fighter sprite path.

The proven static chain is:

```text
resource 0x315736
  -> D_801BA6D8
  -> 0x1A-byte records
  -> func_801B3D1C
  -> scene descriptor
  -> func_801AD13C
  -> package 0x3B6CD0
```

Direct Rev-A ROM extraction disproves the assumption that these are normal combatant records:

- `0x315736` resolves through the generic resource base to ROM offset `0x8A9986`;
- its header size is `0x2B00`;
- the parsed `record+0x02` values do not enumerate class IDs `0x14`, `0x71` or `0x9C`;
- the record selectors are scene-style values such as `0xB7`–`0xCF`;
- the data is consistent with static/auxiliary battle-scene objects, not the player/enemy fighter roster.

`func_801AD368` is also not the normal combatant loader: its only identified caller supplies the fixed resource ID `0x109F95E` and index `0x3A`, again indicating a special scene resource.

Therefore:

- `func_801AD13C` remains a real visual loader;
- the previously traced `0x315736 -> func_801AD13C` route is **not** the place to patch playable Danika;
- `danika_visual_override.h` remains deliberately unwired/fail-closed until the true class-driven combatant visual path is proven.

This correction prevents a dangerous patch to scenery/object rendering.

## `D_801BA72D` is not an ally/enemy flag

`D_801BA72D` is an eight-mode resource-group selector sourced through `D_801B9540`. Its values include normal and high-bit-set selectors. It must not be treated as a boolean team/ownership source.

Likewise, render-context bits from the static scene-object records are real renderer inputs but are not independently proven player/enemy ownership.

## Strongest current clue: class tail metadata

The final bytes of the aligned class records contain a very strong structural relationship between the two Dragoon entries and Danika.

```text
field       Dragoon 0x14   Danika 0x71   hidden Dragoon 0x9C
record+40       1F             1F               1C
record+41       02             00               02
record+42       06             00               06
record+43       05             00               05
record+44       11             00               11
record+45       00             00               14
record+46       FF             03               04
record+47       02             02               02
```

Two facts are now locked:

1. Hidden Dragoon `0x9C` and playable Dragoon `0x14` differ at only `+0x40`, `+0x45` and `+0x46` across the entire `0x48`-byte record.
2. Hidden Dragoon explicitly stores `0x14` at `record+0x45`.

The global alias audit found many other hidden/enemy entries in the `0x89`–`0xA2` region whose `+0x45` points back to a normal class, often with the records differing only at `+0x45/+0x46` or one additional tail field. This establishes `+0x45` as a genuine class-reference/alias mechanism rather than coincidence.

However, `+0x45` is used by gameplay class accessors too, so it is **not yet safe** to set Danika `+0x45 = 0x14` globally. That could change more than presentation.

The more suspicious Danika signature is `+0x41..+0x44 = 00 00 00 00`, while both Dragoon records share `02 06 05 11`. These fields are now the highest-priority consumer-tracing targets.

## Current class-driven investigation

The project has pivoted away from ranking functions merely because they touch class metadata.

Confirmed non-graphics paths include:

- `func_8016E52C`: leads into the already eliminated text-formatting route;
- `func_8016EBC4`: character/class progression/stat logic using `unit+0x12` as class and `unit+0x13` as a counter;
- adjacent setup callers that do not reach ROM graphics loaders.

The current strategy is to trace every consumer of class-tail anchors:

- `D_80187C75` = `record+0x41`
- `D_80187C76` = `record+0x42`
- `D_80187C77` = `record+0x43`
- `D_80187C78` = `record+0x44`
- `D_80187C79` = `record+0x45`
- `D_80187C7A` = `record+0x46`

and classify each consumer as gameplay, UI, battle setup, animation, equipment, or graphics/resource loading before any field is copied from Dragoon.

## Dragoon remains the compatibility donor, not the visual replacement

For the final allied Knight of Danika:

What may be inherited only after proof:

1. player-side stance/pose skeleton;
2. rear-facing attack frame sequencing;
3. weapon-hand/anchor geometry;
4. large-sword animation timing/events;
5. narrowly scoped side-specific metadata required for a valid player presentation.

What remains Danika-specific:

- class ID `0x71`;
- original enemy/front graphics;
- armor, helmet/crest, sword design, silhouette;
- green/gold/white palette;
- class identity/name;
- Danika stats/behavior unless separately redesigned later.

The final rear sprite must look like a native rear view of the Knight of Danika, not a recolored Dragoon.

## Diagnostic patch contract

The first runtime proof-of-concept will happen only after the true fighter visual/animation path and allied ownership source are identified.

It will:

- match class `0x71` only;
- match proven allied/player-side context only;
- keep class identity `0x71`;
- temporarily borrow the known-safe player Dragoon presentation resource only as a diagnostic;
- leave enemy/front Danika untouched;
- leave every other class untouched;
- fail closed to vanilla when context or donor data is unresolved.

If that diagnostic enters battle, idles, attacks, receives damage and exits to the map safely, the missing player-side presentation path is proven. Only then will the real Danika rear asset set replace the temporary donor.

## Automated evidence

Important current tools include:

- `tools/audit_knight_of_danika.py` — locks IDs/table contracts;
- `tools/audit_danika_class_layout.py` — verifies aligned `0x48` records;
- `tools/audit_danika_class_aliases.py` — maps `record+0x45` aliases globally;
- `tools/trace_danika_tail_field_consumers.py` — inventories consumers of `+0x41..+0x46`;
- `tools/trace_danika_asset_bridge.py` — permanently eliminates the text-resource false path;
- `tools/trace_danika_dynamic_visual_loader.py` — documents why the special/static visual callers are not normal fighter loaders;
- `tools/trace_danika_class_asset_consumers.py` — starts from verified class-table users instead of renderer guesses;
- `tools/scan_danika_weapon_compat.py` — ranks Dragoon-compatible candidates without copying unknown fields;
- `tools/test_danika_gate_contract.py` — locks allied-only fail-closed gating;
- `tools/test_danika_visual_override.py` — locks class-specific visual donor safety.

The CI workflow now triggers on `tools/**`, so future reverse-engineering probes are automatically exercised and archived.

## Safety rules

- Never overwrite global Dragoon resources.
- Never replace the whole Danika record with Dragoon's record.
- Never globally set Danika `+0x45` to Dragoon until all consumers are classified.
- Never copy `+0x41..+0x46` blindly.
- Never use the static `0x315736` scenery path as the fighter sprite hook.
- Never use `D_801BA72D` or unproven render bits as ownership.
- Never patch `0x01DE....` text banks as graphics.
- Preserve enemy/front Danika behavior.
- Prefer a narrow `class 0x71 + proven allied side` hook.
- Unsupported/unresolved paths must fall back to vanilla behavior.

## Current milestone

M1 remains:

> Knight of Danika `0x71` can be placed in a player unit, rendered from the allied side with a valid rear presentation, enter battle, idle, attack, receive damage, and return to the map without a crash.

Completed toward M1:

- class IDs and true record layout locked;
- text-resource false path eliminated;
- genuine visual loader identified but its static-scene callers separated from fighter rendering;
- `D_801BA72D` prevented from being misused as ownership;
- global `+0x45` alias mechanism demonstrated;
- hidden Dragoon `0x9C -> 0x14` relationship proven;
- Danika's missing-looking `+0x41..+0x44` block isolated;
- CI now tracing the exact consumers of the suspicious tail fields.

Next blocking discovery:

**Classify `record+0x41..+0x46`, especially the shared Dragoon values `02 06 05 11`, and follow whichever consumer reaches the real combatant animation/visual loader.**
