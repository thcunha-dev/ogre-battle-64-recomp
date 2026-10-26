# Knight of Danika — Battle Probe

This package is a **read-only diagnostic** for the playable Knight of Danika project. It does not make Danika playable by itself and it does not alter classes, graphics, equipment, battle state, inventory or save data.

## Why this exists

Static reverse engineering has now proven the battle visual path:

- `battle_record+0x00` is the per-participant visual asset selector;
- `battle_record+0x02` carries the class word; its low byte is the class ID;
- class `0x71` is Knight of Danika and must remain `0x71`;
- `battle_record+0x0C` supplies renderer-context bits, but static analysis has **not** proved that those bits mean allied/enemy or front/rear;
- `D_801BA72D` is a multi-mode resource-group selector, not an ownership flag.

A second, independently verified path is now captured as well. The EXP-overflow restoration proved the live battle/result participant layout:

- live battle state pointer: `*(0x801CE8DC)`;
- participant stride: `0xF8`;
- participant payload: `slot + 0x1C4`;
- active marker: word at `slot + 0x20C`;
- participant `+0x31`: level;
- participant `+0x32`: EXP;
- participant `+0xF6`: persistent roster index;
- persistent character table: `0x80193BE0`, stride `0x38`, class at `+0x12`.

This gives the probe two independent views of the same battle: renderer records and roster-backed live participants. The remaining safe requirement is still to prove ownership before activating the final override. A roster link is strong identity evidence, but it is **not automatically an ally/enemy flag**.

## Dormant final visual resolver

The selector-only resolver for the future playable patch is already implemented in `danika_visual_override.h` and is intentionally dormant. Its only positive path is:

`class 0x71 + proven allied side + valid allied-Dragoon selector -> use donor visual selector`

Every other case returns the original selector unchanged. In particular:

- unknown side -> vanilla;
- enemy Danika -> vanilla;
- any class other than `0x71` -> vanilla;
- donor selector `0` or `0xFFFF` -> vanilla;
- the class word itself is never rewritten.

The resolver is exercised by a native C truth-table test and is also compiled and linked by the MIPS cross-toolchain into the diagnostic ELF through `danika_visual_contract.c`. That contract object has no runtime hook or patch and exists only to prove target-ABI compatibility before live mutation is enabled. Packaging asserts that the diagnostic ELF still contains the single read-only `func_80072944` hook and no `.recomp_patch` section.

Therefore the remaining activation inputs are exactly two independently proven values from real battle data:

1. a reliable allied/enemy discriminator for a live participant/visual record;
2. the visual selector used by a known player-side normal Dragoon.

Until both are proven, the runtime override remains disabled.

## What the probe logs

Whenever a new battle visual table/resource group becomes active, every plausible record is emitted once:

`DANIKA_SNAPSHOT g=3E slot=00 sel=0012 class=0071 id=71 f04=.... f06=.... f08=.... f0A=.... flags=.... f0E=.... f10=....`

A visual record is emitted again only if its tracked contents change:

`DANIKA_PROBE g=3E slot=00 sel=0012 class=0071 id=71 f04=.... f06=.... f08=.... f0A=.... flags=.... f0E=.... f10=....`

The live participant side of the probe now emits a bounded identity snapshot too:

`DANIKA_PART_SNAPSHOT i=00 roster=01 rclass=14 lvl=12 exp=34 head=................................ tail=................`

If the participant identity-oriented signature changes later, it is emitted as:

`DANIKA_PART i=00 roster=01 rclass=14 lvl=12 exp=34 head=................................ tail=................`

Participant fields:

- `i`: live participant index (`0..19`);
- `roster`: verified participant `+0xF6` roster index;
- `rclass`: class read independently from `0x80193BE0 + roster*0x38 + 0x12` when `roster < 100`, otherwise `FF`;
- `lvl` / `exp`: verified live participant level and EXP fields;
- `head`: first 16 raw bytes of the participant payload, retained only as diagnostic evidence;
- `tail`: participant bytes `+0xF0..+0xF7`, including the known roster-index neighborhood.

The raw `head`/`tail` bytes are **not assigned ownership semantics** by the probe. They exist so repeated captures can expose stable field correlations without guessing.

Visual-record fields:

- `g`: current resource-group selector;
- `slot`: visual record index inside that group;
- `sel`: visual asset selector used by `func_801AD13C` / package `0x3B6CD0`;
- `class`: complete class word;
- `id`: low-byte class ID;
- `flags`: record `+0x0C`, renderer-context bits with no ownership meaning proven yet;
- `f04..f10`: neighboring record fields retained for correlation.

Relevant class IDs:

- `14` — Dragoon;
- `71` — Knight of Danika / Gatekeeper;
- `9C` — hidden Dragoon variant.

## Automatic log analysis

Save the port output to a text file and run:

`python3 tools/analyze_danika_probe_log.py ogrebattle64.log -o danika-analysis.txt`

The analyzer reports:

- observed selectors/locations for Dragoon, Danika and hidden Dragoon;
- field variance for the renderer records;
- live participants and whether each has a valid persistent-roster backing;
- the persistent-roster class independently recovered for each backed participant;
- conservative `BRIDGE_CANDIDATE` entries when one class appears in exactly one roster-backed participant **and** exactly one visual record in the entire capture.

Example of an automatic 1:1 bridge:

`BRIDGE_CANDIDATE class=0x14 Dragoon participant=0x00 roster=0x01 visual=g03/s00 selector=0x0012`

For Dragoon, such a bridge lets the analyzer report `candidate_roster_backed_dragoon_selectors=...`. This can recover the donor selector with much less manual slot mapping. It remains capture-local identity evidence, not a global ownership proof.

If there are two visual Dragoons, two roster-backed Dragoons, multiple selectors/locations, or any other ambiguity, the analyzer deliberately refuses the automatic bridge.

Visible gameplay labels are still supported. Locations use hexadecimal `G:SLOT` and options are repeatable:

`python3 tools/analyze_danika_probe_log.py ogrebattle64.log --ally 03:00 --ally 03:01 --enemy 03:04 -o danika-analysis.txt`

With explicit labels, the analyzer reports known allied Dragoon and enemy Danika selectors when present. It searches for ownership-field candidates only when the **same class** appears on both labeled sides. This prevents a Dragoon-vs-Danika class difference from being mistaken for an ally/enemy flag.

Even a reported ownership `CANDIDATE` is only a correlation from that capture and must be reproduced before it is accepted as the final ownership gate.

## Minimum capture that will unlock the next patch

1. Enable **Knight of Danika - Battle Probe** and enter a normal battle.
2. Keep the port log from battle entry through the first attack.
3. Prefer a battle with exactly one normal Dragoon on the player's side. The new participant/visual 1:1 bridge can often recover its donor selector automatically.
4. Capture the original enemy Knight of Danika (`id=71`) if available so its vanilla visual signature is recorded.
5. For ownership proof, the strongest capture still contains the same class on both sides. Explicit `--ally`/`--enemy` labels can then isolate same-class field differences without confusing class identity with side.
6. A later player-side test Danika can be compared against the proven ownership discriminator before the dormant override is activated.

A short video remains useful, but with the participant stream it is no longer required merely to identify every unique-class visual record by hand.

## Safety design

The probe hooks only `func_80072944`, the established base per-frame hook. It performs bounds-checked reads from both the visual battle table and the independently verified live participant/roster structures and calls `recomp_log`. There are no volatile writes, `RECOMP_PATCH` functions, save hooks or asset replacements.

Visual logging is capped at 24 records. Participant logging is capped at 20 live slots and is snapshot/change-driven. Normal level/EXP progression is deliberately excluded from the participant identity signature so attacks do not create unbounded per-frame log spam.

If a pointer or derived address is outside N64 RDRAM, the corresponding scan does nothing. Unknown state therefore fails closed.
