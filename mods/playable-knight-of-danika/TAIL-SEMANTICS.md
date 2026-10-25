# Knight of Danika — class-tail semantics

## Result

The suspicious class-record tail block is no longer a viable candidate for the missing allied/rear battle presentation.

The previous strongest visual hypothesis came from this comparison:

| field | Dragoon `0x14` | Danika `0x71` | hidden Dragoon `0x9C` |
|---|---:|---:|---:|
| `+0x41` | `02` | `00` | `02` |
| `+0x42` | `06` | `00` | `06` |
| `+0x43` | `05` | `00` | `05` |
| `+0x44` | `11` | `00` | `11` |
| `+0x45` | `00` | `00` | `14` |
| `+0x46` | `FF` | `03` | `04` |

Static dataflow now narrows the meaning substantially.

## `+0x41..+0x44`: class-transition candidates

`func_8016EA54` reads `D_80187C75..D_80187C78` (`record+0x41..+0x44`) from class records and chooses among them according to gameplay conditions.

The same group is consumed by `func_8016F13C`. In that live-character mutation path, the selected byte reaches a store to `character+0x12`, the established class-ID field.

Therefore these four bytes are class-transition / class-selection metadata, not a rear-sprite descriptor.

### Safety consequence

Do **not** copy Dragoon's `02 06 05 11` into Danika `+0x41..+0x44` as a graphics fix. It would change class-transition behavior.

## `+0x45`: class alias/reference

The global alias audit already established `record+0x45` as a genuine class-reference mechanism. Hidden Dragoon `0x9C` contains `0x14` here and many other hidden/enemy records point back to normal classes in the same field.

This field also participates in gameplay class paths, so setting Danika `+0x45 = 0x14` globally remains forbidden.

## `+0x46`: companion gameplay metadata

`func_8016D274` is a direct accessor for `D_80187C7A` (`record+0x46`). `func_8016F13C` also consumes this byte and can copy it into live-character `+0x1A`.

Its exact human-readable meaning is still unresolved, but it is clearly gameplay-side metadata and not proven visual-resource identity.

## What this eliminates

The whole `+0x41..+0x46` tail area is now rejected as the direct fix for playable Danika graphics.

That is useful progress: the project no longer needs to spend time trying permutations of Dragoon tail bytes that could silently corrupt class progression or other character state.

## Current graphics direction

The true fix must be found outside this class-tail block, in the class-driven combatant presentation path that eventually selects:

1. player/enemy-facing combatant graphics;
2. animation set / pose sequencing;
3. weapon anchor / large-sword presentation;
4. a side-specific or context-specific resource that can be overridden only when `class == 0x71 && side == ally`.

The existing fail-closed contract remains unchanged:

- enemy/front Danika stays vanilla;
- Danika stays class `0x71`;
- global Dragoon assets are never overwritten;
- Dragoon is only a temporary diagnostic donor / pose skeleton;
- the final rear asset preserves Danika's armor, helmet/crest, sword, silhouette and green/gold/white palette.

## Automated lock

`tools/classify_danika_tail_semantics.py` verifies this classification in CI. If future source changes break the proven dataflow, the research workflow fails instead of allowing the project to silently fall back to the old tail-field hypothesis.
