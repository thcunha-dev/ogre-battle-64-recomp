# Gatekeeper Visual Shell v1 — test protocol

This build is the first presentation-only bridge built on the proven stable Dragoon combat baseline.

## What it does

- Finds the **second** Fighter (`0x02`) in the player's persistent roster.
- Applies the four real default equipment IDs from playable Dragoon (`0x14`).
- Converts that roster entry to real playable Dragoon (`0x14`).
- Keeps Dragoon class/motion/2H weapon logic coherent through the entire battle pipeline.
- Does **not** write live participant class memory.
- After the battle visual table is loaded, scans the known visual resource groups.
- For each group, discovers Gatekeeper (`0x71`) visual selectors and Dragoon (`0x14`) render records.
- Changes **only** `record+0x00` (visual selector) on Dragoon records when the Gatekeeper mapping is unambiguous.
- Never writes `record+0x02` (class word).

## Why

The stable bridge proved that a full Dragoon package enters Training and fights normally. Previous builds black-screened when Gatekeeper `0x71` was used as a runtime class or mixed with Dragoon participant state. This build avoids that mixed identity completely: Dragoon remains the logical class and only the body selector is changed.

The goal is to test whether the original Gatekeeper body resource can be loaded over the safe Dragoon player-side skeleton/motion while the equipped weapon remains part of the normal dynamic equipment pipeline.

## Safety / limitations

- Disable **all** older Danika/Gatekeeper development mods.
- Use a backup/copy save; do not overwrite an important save.
- For this prototype, avoid placing any additional Dragoons in the test battle. Visual selector changes currently target Dragoon render records in the loaded groups, not a single roster identity.
- Gatekeeper enemy records are not modified.
- If a resource group has an ambiguous Gatekeeper selector mapping, the mod fails closed and leaves that group untouched.

## What to observe

1. Does the second Fighter still become Dragoon in the menu with Dragoon default equipment?
2. Does Training load normally, as it did with Stable Bridge?
3. In the battlefield, does the body become green/white Gatekeeper, remain Dragoon, become partially mixed, or black-screen?
4. Is Tiamat/current equipped weapon still visible separately?
5. Does the unit keep the Dragoon two-handed attack motion?
6. Send a screenshot/video of idle rear view and one attack if possible.

### Interpretation

- **Gatekeeper body + Dragoon 2H motion + visible weapon:** major milestone; original Gatekeeper selector is compatible with the player-side Dragoon skeleton.
- **Dragoon body, battle works:** the selector table is not the final body-selection stage for that context; continue deeper into descriptor/resource binding.
- **Black screen:** original Gatekeeper selector itself is not player-side compatible; next route is custom/reconstructed asset injection rather than direct selector reuse.
