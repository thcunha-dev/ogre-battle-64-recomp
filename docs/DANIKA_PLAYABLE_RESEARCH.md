# Playable Knight of Danika — runtime restoration notes

Status: active research branch `mod/playable-knight-of-danika`.

Goal: restore Knight of Danika / Gatekeeper (class `0x71`) as a usable allied
class without changing the original enemy encounter. The allied restoration
should keep Danika identity/visual treatment while borrowing the proven rear
battle posture, animation and weapon presentation path from playable Dragoon
(class `0x14`) where necessary.

## Proven contracts

- True class-table base: `0x80187C34`.
- True class-record stride: `0x48`.
- Dragoon class: `0x14`.
- Knight of Danika / Gatekeeper class: `0x71`.
- Hidden Dragoon reference: `0x9C`.
- The field family historically treated as a record origin is actually
  record `+0x2E`, base `0x80187C62`.
- Alias/key field anchor is record `+0x45`, base `0x80187C79`.
- Runtime battle visual selector is at `battle_record + 0x00`.
- Participant-to-persistent-roster linkage has an exact persistent-record
  stride of `0x38`.
- Bank AH mapping: ROM `0x23A370` -> RAM `0x801D0860`, size `0xE80`.

The visual selector is presentation evidence. It must **not** be used as an
ally/enemy discriminator.

## Non-negotiable preservation rule

The original enemy Knight of Danika must remain unchanged.

The eventual runtime decision is therefore fail-closed:

```text
if class_id != 0x71:
    use original path
elif ownership_side != ALLY:
    use original path
else:
    borrow presentation source from class 0x14
```

`UNKNOWN` ownership is equivalent to no permission to override.

The unit identity class remains `0x71`. Class `0x14` is only the intended
source for the missing allied/rear presentation behavior; it must not replace
Danika globally in the class table.

## Current blocker

We have a strong participant -> persistent-record bridge but we do not yet have
a proven runtime field/range that labels a participant as allied. Therefore no
RAM write and no `RECOMP_PATCH` should be enabled yet.

A structurally valid roster slot derived with stride `0x38` is useful evidence,
but it is not ownership proof until the player-roster base/range is established
independently.

## Required A/B capture to prove ownership

Use the existing read-only battle probes. Capture all compared participants in
the same build and preferably the same battle/session.

### A. Known allied Dragoon (`0x14`)

Record:

- battle participant pointer / index;
- class ID;
- `battle_record + 0x00` visual selector;
- persistent-record pointer reached by the participant bridge;
- candidate roster base;
- derived `0x38` slot index;
- every candidate side/team/formation/unit-owner field currently emitted by
  the J/C/AH probes;
- rear-view behavior, animation set and visible weapon.

### B. Second known allied unit

Repeat for a non-Dragoon allied participant. A valid ownership discriminator
must agree with sample A even though class/presentation values differ.

### C. Known enemy participant

Repeat the same capture. Candidate ownership signals must differ from both
allied samples while unrelated presentation fields are ignored.

### D. Second known enemy participant

Repeat once more. Do not promote a field/range to `ALLY`/`ENEMY` from a single
pair of samples.

## Promotion criteria for an ownership signal

A candidate can become the mod's ownership discriminator only when all of the
following hold:

1. it is stable across at least two known allied participants;
2. it is stable across at least two known enemy participants;
3. allied and enemy classifications are deterministic and non-overlapping;
4. it is not merely the class ID, visual selector, palette or animation ID;
5. a missing/out-of-range/corrupt value yields `UNKNOWN`, never `ALLY`;
6. class `0x71` enemy samples still follow the untouched original path.

## First safe runtime override after ownership proof

Once ownership is proven, implement the smallest possible presentation hook:

1. read the unit's real class ID;
2. immediately return the original result unless class is `0x71`;
3. resolve ownership;
4. immediately return the original result unless ownership is positively
   `ALLY`;
5. only for allied `0x71`, request the Dragoon `0x14` presentation source for
   rear posture / animation / weapon behavior;
6. preserve Danika identity and palette/visual fields that have already been
   shown to belong to the unit rather than the missing rear presentation;
7. never mutate the global class `0x71` entry.

## Acceptance tests for the first hook

The hook is not accepted until all of these pass:

- enemy Danika before/after binary behavior comparison: unchanged;
- ordinary allied Dragoon: unchanged;
- unrelated allied classes: unchanged;
- allied Danika front view: retains intended Danika identity;
- allied Danika rear view: no missing/broken pose;
- allied Danika attacks: valid animation and weapon presentation;
- invalid/unknown ownership: original path, no override;
- save/reload and a second battle do not change the classification result.

## Tooling guardrail

`tools/audit_knight_of_danika.py` contains executable contracts for class-table
geometry, bank AH mapping, persistent-roster stride/slot derivation and the
fail-closed presentation eligibility rule. Keep that audit passing before
activating any runtime write.
