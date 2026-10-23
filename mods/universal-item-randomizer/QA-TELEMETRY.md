# Universal Item Randomizer 0.3.1 — QA telemetry guide

Enable the mod option `LOG` only while testing. Diagnostics are deliberately
bounded to at most four messages per route and never write seed/randomizer
metadata into Ogre Battle 64's native save.

## Route messages

| Message | What it proves |
|---|---|
| `universal-item-randomizer: deterministic mapping ready` | External config was read and the deterministic mapper was initialized. |
| `universal-item-randomizer: map/drop source mapped` | A display-sensitive map/drop source was rewritten before the game consumed it. |
| `universal-item-randomizer: ground pickup source mapped` | The per-map ground pickup list was rewritten before popup/grant consumption. |
| `universal-item-randomizer: battle reward source mapped` | The battle reward queue was rewritten before reward UI/grant consumption. |
| `universal-item-randomizer: Bank-R starting/setup grant recognized` | A classified Bank-R starting/setup caller reached the central grant patch. |
| `universal-item-randomizer: starting/setup direct grant mapped` | `STARTING ITEMS = ON` mapped a classified direct Bank-R setup grant. |
| `universal-item-randomizer: post-battle equipment add mapped` | The independent `func_80172820(id,count)` post-battle acquisition path executed. |
| `universal-item-randomizer: coupled Bank-R unit loadout left vanilla` | The unsafe ID-28 unit-loadout setup was recognized and intentionally preserved atomically as vanilla. |

## Important interpretation rule

The source messages containing `mapped` are emitted only when the deterministic
permutation actually changes that source id. A permutation can legally contain a
fixed point (`map(id) == id`), so the absence of one source-specific `mapped`
message is not by itself proof that the game never visited that source. Use the
visible reward/pickup behavior plus repeated cases when validating a route.

The two classification messages — `Bank-R starting/setup grant recognized` and
`coupled Bank-R unit loadout left vanilla` — do not depend on the replacement id
changing and are therefore direct caller-observation diagnostics.

The post-battle diagnostic also logs the route invocation even if a particular
mapped equipment id happens to be a fixed point.

## Save-safety invariant

Telemetry is observational only. It must never:

- install a save-load hook to infer acquisitions;
- scan inventory deltas frame-by-frame;
- persist seed, route state or randomizer flags into the native save;
- modify item ids/counts merely for logging;
- use unbounded per-frame output.

`tools/test_randomizer_qa_telemetry.py` enforces these properties statically in
the integrated CI alongside the save-safety, mapping, runtime-coverage and
inventory-writer taxonomy contracts.

## Fast QA sequence

1. Set a known seed, enable `LOG`, leave key items/shops/starting items at their
   intended test values.
2. Obtain one ground/map item and one battle reward.
3. Exercise a post-battle equipment-add case when available.
4. On a disposable New Game, test `STARTING ITEMS = OFF`, then ON.
5. Confirm the coupled Bank-R loadout diagnostic leaves its item/reference
   vanilla and aligned.
6. Save, close completely, reopen, load, then repeat with the mod disabled.
7. Existing inventory must remain byte-for-byte equivalent in item id/count
   across load-only transitions; only future acquisitions may use the mapper.

For the full campaign/save matrix, see `TESTING.md`.
