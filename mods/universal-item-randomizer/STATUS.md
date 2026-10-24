# Universal Item Randomizer 0.3.1 — engineering status

Status: **feature-complete for the currently safe acquisition model; real Rev-A gameplay/save/post-game QA pending**.

## Automated verification

Current host verification is **31 tests** through `python3 tools/test_universal_randomizer_all.py`.

The suite locks:

- deterministic one-to-one mapping and seed `123456` golden vectors;
- no randomizer metadata in native saves and no rerandomization on load;
- 5,000 modeled ON -> OFF -> ON persistence sequences;
- 2,000 dedicated completed-game/post-ending ON -> OFF -> ON sequences;
- 1,000 simulated campaigns x 600 events = **600,000 cross-subsystem events**;
- Table-O/Table-P/reward generation boundaries and fail-closed validation;
- Table-P physical capacity of exactly 16 `u16` IDs at `0x801F1004..0x801F1023`;
- count saturation at 99 and full-inventory no-overwrite behavior;
- native slot-indexed `+0x02` used-count repair, including item-ID != owned-slot cases;
- class `0xFF`, partial-roster readiness and Rev-A table/list boundaries;
- all 46 central-grant caller classifications and both replacement ABI contracts;
- safe 40-call STARTING ITEMS block and two coupled `a1=1` callers fail-closed;
- package/runtime/Windows/stock QA pipeline policy;
- **artifact manifest parity across all four artifact families**.

The package-only workflow now uploads `BUILD-MANIFEST.txt` beside the `.nrm`, with source commit, NRM SHA-256/size, host-suite count and the same persistence/use-repair/ABI safety markers carried by the larger QA artifacts. The parity test prevents these manifests from silently drifting apart.

## Core Rev-A behavior

Whole-cart Rev-A analysis accounts for all 46 calls to `func_ovlN_801DC740`:

- 4 Bank-N gameplay callers already consume source-rewritten values: Table-O A/B, Table-P ground pickup and battle reward;
- exactly 2 Bank-R callers pass `a1=1`, at RA `0x80215BF4` and `0x80216D98`; both maintain coupled unit consumable references and remain vanilla/fail-closed;
- the remaining 40 Bank-R calls form the audited STARTING ITEMS opt-in range `0x80217070..<0x8021724C`, all literal `a1=0` with no matching unit-reference store.

The transient `+0x02` repair mirrors native `func_8016B774`: roster fields are **owned-list slot references**, not item definition IDs. Equipment refs must be `<278`, consumable refs `<40`, and partial roster initialization is fail-closed until both character and unit rosters are ready.

Battle-reward shadowing is per physical slot in the 20-u16 queue at `0x801936D8`; the primary slot is statically proven to be granted at `0x801E53DC` and cleared at `0x801E53F4`.

## Build state

The previous traceable green QA candidate at `bf7b34afe1315efcd7e985e484512da098948af6` passed mapping, package, Windows QA, stock-runtime QA and the integrated custom-runtime build. The current branch head supersedes it with package-provenance and manifest-parity hardening; use the newest head only after its complete gate set is green.

The stock-runtime QA bridge packages a distinct QA-only mod for official v0.8.3 and a ready-to-run Windows bundle. The official upstream archive is accepted only with SHA-256:

`d9c269587b2f2b224bc6203c7ac9c4f42022f6990643cd38a870cb56df243169`

No `.z64`, `.n64` or `.v64` game data is bundled.

## Remaining 1.0 blocker

The automated/code side is release-candidate grade. **Real gameplay evidence is still mandatory before 1.0** because it is the only way to validate visual/runtime integration and, especially, the old randomizer's post-ending save failure mode.

Required real-game acceptance still includes:

- Table-O popup vs delivered item and Table-P pickup;
- battle reward UI/inventory plus repeated physical-slot reuse;
- real `+0x02` case where item-definition ID differs from owned-list slot;
- post-battle add/count;
- shops OFF/ON consistency (name/icon/detail/price/purchased ID);
- full inventory behavior;
- native save ON -> OFF -> ON;
- seed change after full restart: existing inventory stable, future acquisitions changed;
- ending/post-game save ON, reopen ON, reopen OFF, save OFF, reopen ON with IDs/counts unchanged;
- integrated custom-runtime Bank-N replacement, STARTING ITEMS safe block and the two coupled `a1=1` grants remaining aligned/vanilla;
- safe-default key item progression.

The PR stays draft until those real-game checks pass.

See `TESTING.md`, `QA-CHECKLIST.md`, `STOCK-RUNTIME-QA.md` and `STOCK-QA-CHECKLIST.md`.
