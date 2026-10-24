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
| `universal-item-randomizer: Bank-R starting/setup grant recognized` | One of the **40 audited literal a1=0** Bank-R starter grants (`RA 0x80217070..<0x8021724C`) reached the central grant patch. This no longer includes the two unit/loadout-coupled a1=1 callers. |
| `universal-item-randomizer: starting/setup direct grant mapped` | `STARTING ITEMS = ON` changed one of those safe literal starter grants. |
| `universal-item-randomizer: post-battle equipment add mapped` | The independent `func_80172820(id,count)` post-battle acquisition path executed. |
| `universal-item-randomizer: coupled Bank-R unit/setup grant left vanilla` | One of the two Rev-A a1=1 unit/setup grants (`RA 0x80215BF4` or `0x80216D98`) was recognized and intentionally preserved vanilla because the game also writes/maintains the matching unit loadout reference. |

## Important interpretation rule

The source messages containing `mapped` are emitted only when the deterministic
permutation actually changes that source id. For the current Sattolo pools, pools
larger than one have no fixed points; identity remains possible only for sources
that are intentionally outside a mapped pool (for example protected/unknown
classes). Use visible reward/pickup behavior plus repeated cases when validating a
route.

The two classification messages — `Bank-R starting/setup grant recognized` and
`coupled Bank-R unit/setup grant left vanilla` — do not depend on the replacement
id changing and are therefore direct caller-observation diagnostics.

The post-battle diagnostic also logs the route invocation even if a future policy
leaves a particular equipment id unchanged.

## Bank-R classification proof

Whole-cart Rev-A analysis accounts for all 46 calls to `func_ovlN_801DC740`.
Exactly two callers pass `a1=1`:

- ROM `0x19607C`, RA `0x80215BF4`;
- ROM `0x197220`, RA `0x80216D98`.

Both are coupled to a unit's ten-byte consumable loadout at `unit+0x0D` and are
therefore always vanilla/fail-closed. The only `STARTING ITEMS` opt-in surface is
the later literal block of 40 calls at ROM `0x1974F8..0x1976D4` / RA
`0x80217070..<0x8021724C`. Every one of those calls passes `a1=0`, and the audited
straight-line block contains no store instruction that could couple a unit
reference to the raw item id.

With `LOG = ON`, a disposable New Game should therefore show two distinct kinds
of evidence: safe starter recognition/mapping for the literal block, and
`coupled ... left vanilla` when either unit/setup route is exercised. Seeing the
coupled diagnostic is expected and is **not** a missing-randomization bug.

## Battle reward queue lifecycle

The reward source at `0x801936D8` is a persisted block of 20 `u16` reward words.
Observed gameplay from the upstream reverse-engineering work has shown real
reward entries in multiple positions (including indices 0, 2, 3 and 4), so this
is not a single-value generation blob and QA must **not** require the whole block
to become zero between battles.

Shadow safety is **per-slot**. In the mod, when one live reward word becomes zero,
only that slot's `s_reward_valid[]` / `s_reward_written[]` state is cleared. A
later non-zero value in that slot is then mapped as a fresh source value.

The primary consumption path is statically proven in Bank N:

- `0x801E5230` reads the primary word at `0x801936D8`;
- `0x801E5254` reads `0x801936DA` as its fallback;
- `0x801E53DC` calls the central grant;
- `0x801E53F4` executes the native post-grant clear of `0x801936D8`.

That `0x801E53F4` clear gives the primary slot a concrete native reuse boundary;
it is not an invented battle-generation address.

Before release/1.0, exercise repeated item rewards with `LOG = ON` and, when a
debugger/memory viewer is available, watch the 20 words beginning at
`0x801936D8`. Verify that a consumed/reused slot passes through zero or otherwise
changes away from the mod-written replacement before it is repopulated. It is
fine for *other* reward slots to remain non-zero because they may represent other
pending rewards.

If QA ever observes the same physical slot being reused for a new vanilla reward
without a zero/change boundary, treat that specific slot lifecycle as unresolved
and do not promote the build until a proven queue-advance/generation state is
identified. Do not replace the per-slot rule with a guessed global generation key.

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
3. Run repeated item-reward battles and, when possible, observe slot reuse in the
   reward queue. Confirm the per-slot zero/change boundary; do **not** require the
   entire queue to clear globally.
4. Exercise a post-battle equipment-add case when available.
5. On a disposable New Game, test `STARTING ITEMS = OFF`, then ON. With ON, only
   the safe 40-call literal block may map.
6. Confirm both coupled Bank-R a1=1 unit/setup routes remain vanilla and aligned
   with their unit loadout references.
7. Save, close completely, reopen, load, then repeat with the mod disabled.
8. Existing inventory must remain byte-for-byte equivalent in item id/count
   across load-only transitions; only future acquisitions may use the mapper.

For the full campaign/save matrix, see `TESTING.md`.
