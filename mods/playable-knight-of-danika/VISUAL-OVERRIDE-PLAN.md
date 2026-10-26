# Knight of Danika — final visual override plan

## Proven insertion point

The safest override point is the per-participant visual selector after `func_801B3D1C` has resolved the active battle record and before `func_801AD13C` consumes the descriptor.

Proven Rev-A dataflow:

```text
resource 0x315736
  -> D_801BA6D8
  -> battle record (stride 0x1A)
  -> record+0x00 visual selector
  -> func_801B3D1C return
  -> descriptor+0x50
  -> func_801AD13C arg0
  -> package 0x3B6CD0 visual pointer table
```

The class word is independent:

```text
record+0x02 -> descriptor+0x4C -> low byte descriptor+0x4F = class id
```

Knight of Danika must remain class `0x71`. The final restoration changes only the selector used for the allied/rear visual path; it must not rewrite the class word to Dragoon `0x14`.

## Activation gate

The final runtime rule is deliberately narrow:

```text
if class_id == 0x71
and ownership == independently_proven_ALLIED
and dragoon_allied_selector != 0
    selector = dragoon_allied_selector
else
    selector = original_selector
```

Unknown ownership is always vanilla/fail-closed.

## Forbidden shortcuts

Do not use any of these as an ally/enemy discriminator unless later evidence independently proves that exact semantic:

- `D_801BA72D` — already proven to be an eight-mode resource-group selector;
- `battle_record+0x0C bit0/bit1` — renderer-context inputs, ownership unproven;
- renderer facing/camera/layout state;
- class tail `+0x41..+0x46` — gameplay/class-transition metadata;
- global Dragoon asset replacement;
- global `0x71 -> 0x14` class aliasing.

## Donor policy

Dragoon is a pose/animation donor only. The restoration target remains visually Knight of Danika:

- Danika armor and helmet/crest;
- Danika silhouette;
- large sword presentation;
- green/gold/white palette;
- enemy/front Danika unchanged.

A temporary diagnostic build may use the complete allied Dragoon visual selector to prove rear animation compatibility. That diagnostic substitution is not the final art merge.

## Evidence required to enable the gate

Before the selector override can be activated, runtime evidence must establish both:

1. the selector used by a known player-side normal Dragoon (`class 0x14`);
2. a participant ownership signature proven by correlating visible player/enemy participants with battle records.

`Knight of Danika - Battle Probe` now emits `DANIKA_SNAPSHOT` records at each new table/resource group and `DANIKA_PROBE` only for later record changes. `tools/analyze_danika_probe_log.py` summarizes the observations without guessing ownership.

## Release acceptance

A playable build is acceptable only if all of the following hold:

- allied Danika renders from the intended rear/player path;
- enemy Danika remains byte-for-byte vanilla in selector/class behavior;
- class ID remains `0x71` in gameplay state;
- normal Dragoon is unchanged;
- large-sword pose/anchor has no obvious clipping or detached weapon;
- menu/status/class behavior still identifies Danika correctly;
- battle entry, attack, hit, idle, death/retreat and result transitions do not crash;
- save/reload does not mutate class identity or introduce mod metadata into native saves.
