# Knight of Danika — Battle Probe

This package is a **read-only diagnostic** for the playable Knight of Danika project. It does not make Danika playable by itself and it does not alter classes, graphics, equipment, battle state, inventory or save data.

## Why this exists

Static reverse engineering has now proven the battle visual path:

- `battle_record+0x00` is the per-participant visual asset selector;
- `battle_record+0x02` carries the class word; its low byte is the class ID;
- class `0x71` is Knight of Danika and must remain `0x71`;
- `battle_record+0x0C` supplies renderer-context bits, but static analysis has **not** proved that those bits mean allied/enemy or front/rear;
- `D_801BA72D` is a multi-mode resource-group selector, not an ownership flag.

The remaining safe requirement is to correlate real battle records with participants whose ownership is known from gameplay. Once that correlation is proven, the final mod can substitute only the allied Danika visual selector while leaving enemy Danika untouched.

## What the probe logs

Whenever a new battle table/resource group becomes active, every plausible participant record is emitted once as a snapshot:

`DANIKA_SNAPSHOT g=3E slot=00 sel=0012 class=0071 id=71 f04=.... f06=.... f08=.... f0A=.... flags=.... f0E=.... f10=....`

After that, a record is emitted again only if its tracked contents change:

`DANIKA_PROBE g=3E slot=00 sel=0012 class=0071 id=71 f04=.... f06=.... f08=.... f0A=.... flags=.... f0E=.... f10=....`

Zero/empty selectors and class IDs `00`/`FF` are ignored. Logging is therefore bounded and focused on plausible live combatant records instead of dumping arbitrary table padding every frame.

Important fields:

- `g`: current resource-group selector;
- `slot`: record index inside that group;
- `sel`: visual asset selector used by `func_801AD13C` / package `0x3B6CD0`;
- `class`: complete class word;
- `id`: low-byte class ID;
- `flags`: record `+0x0C`, the two known renderer-context bits plus any other bits;
- `f04..f10`: neighboring record fields retained so allied/enemy correlation can be proven instead of guessed.

Relevant class IDs for this project:

- `14` — Dragoon;
- `71` — Knight of Danika / Gatekeeper;
- `9C` — hidden Dragoon variant.

## Automatic log analysis

Save the port output to a text file and run:

`python3 tools/analyze_danika_probe_log.py ogrebattle64.log -o danika-analysis.txt`

The analyzer reports:

- all observed selectors for Dragoon, Danika and hidden Dragoon;
- the group/slot locations where each appeared;
- field variance for `f04`, `f06`, `f08`, `f0A`, `flags`, `f0E` and `f10`;
- initial snapshots separately from later record changes.

The analyzer deliberately **does not infer allied/enemy ownership**. A visible, known player-side participant still has to be correlated with one record before an ownership signature can be promoted into the final gate.

## Minimum capture that will unlock the next patch

1. Enable **Knight of Danika - Battle Probe** and start a normal battle where you can unambiguously identify your own units and the enemy unit.
2. Keep the port log from battle entry through the first attack.
3. Ideally capture a battle containing a normal Dragoon (`id=14`) on the player's side. That reveals the donor `sel` we need for the temporary playable-Danika rear pose.
4. Capture the original enemy Knight of Danika (`id=71`) if available. This establishes the enemy/front signature that the final patch must never replace.
5. Later, place a test Danika in a player unit and capture the same fields. Comparing the records will identify the independently proven allied-side discriminator.

A short video of the battlefield together with the corresponding `DANIKA_SNAPSHOT` / `DANIKA_PROBE` lines is enough to map visible participants to records.

## Safety design

The probe hooks only `func_80072944`, the already-established base per-frame hook used by other working mods. It performs bounds-checked reads from the battle resource table and calls `recomp_log`. There are no volatile writes, `RECOMP_PATCH` functions, save hooks or asset replacements.

If the resource pointer or any derived record address is outside N64 RDRAM, the probe does nothing. Unknown state therefore fails closed.
