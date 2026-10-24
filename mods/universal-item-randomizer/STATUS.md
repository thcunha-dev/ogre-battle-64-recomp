# Universal Item Randomizer 0.3.1 — engineering status

Status: **feature-complete for the currently safe acquisition model; real campaign QA pending**.

Current host verification: **26 tests** through `python3 tools/test_universal_randomizer_all.py`. Latest hardening includes map-generation invalidation for Table-O, full-generation fail-closed validation for Table-O/Table-P/reward queue, invalid-ID rejection in both grant replacements, deterministic golden seed vectors, release/pipeline/version/config contracts, 5,000 modeled ON -> OFF -> ON save sequences, shared MIPS ELF verification, Rev-A RAM table-layout contracts, class-id `0xFF` fail-closed handling and the Table-P physical-capacity fix from an unsafe assumed 64 ids to the real **16 u16 slots** at `0x801F1004..0x801F1023`.

The transient `+0x02` used-count repair mirrors native `func_8016B774` semantics: roster fields are **owned-list slot references**, not item-definition IDs. Equipment uses slot `<278`, consumables use slot `<40`, and the rebuilt byte is written by owned-list slot. Partial load/map setup is fail-closed: the repair requires both character and unit rosters to be populated, clears its shadow-ready state while either side is missing, then forces a complete rebuild on the first fully ready frame. The QA manifest marks this as `use_repair=native_slot_indexed` and `VERIFY-QA.ps1` rejects artifacts that lose the marker.

Battle-reward shadowing is documented and tested as **per-slot**, matching the persisted 20-u16 queue model. Multiple slots have been observed carrying real rewards, so a whole-queue all-zero boundary is not required. The primary slot lifecycle has static Bank-N proof: `0x801E53DC` grants the item and `0x801E53F4` clears `0x801936D8` immediately afterward.

## Rev-A central-grant classification

Whole-cart Rev-A analysis accounts for **all 46 calls** to `func_ovlN_801DC740`:

- 4 Bank-N gameplay callers use source values already rewritten by the randomizer: Table-O map object A/B, Table-P ground pickup and battle reward queue;
- exactly 2 Bank-R callers pass `a1=1`, at RA `0x80215BF4` and `0x80216D98`; both also write/maintain a unit consumable-loadout reference and therefore remain **vanilla/fail-closed**;
- the remaining 40 Bank-R calls form the only `STARTING ITEMS` opt-in block, RA `0x80217070..<0x8021724C`; all pass `a1=0`, and the audited straight-line block contains no store instruction coupling a unit reference to the raw id.

The central replacement now preserves the original consumable `a1` semantics: count always grows safely to the 99 cap; when the low byte of `a1` is non-zero, consumable `+0x02` is incremented/initialized in the same grant and clamped to the resulting count. Equipment ignores `a1`, as in Rev-A.

## Rev-A replacement ABI proof

Both `RECOMP_PATCH` replacements are intentionally declared `void`. This is proven directly against the verified Rev-A ROM (`SHA-1 d26b14bee422a09581ce438d45ba9fec9783fbb8`) rather than assumed from decompilation:

- `func_ovlN_801DC740`: the 46-caller ABI auditor follows post-return MIPS-I control flow, including branches/jumps and delay slots, and proves every caller overwrites `$v0` or reaches another call before any `$v0` read;
- `func_80172820`: whole-cart scan finds exactly **one caller**, at ROM `0x002A4ED8` / VRAM `0x802356F8`; its delay slot is `andi a1,a1,0xff`, and the first instruction after return is `addiu v0,s1,1`, so the original return value is discarded immediately;
- the central grant's full-inventory tail call is also proven harmless to omit: Rev-A calls `0x80093540`, a five-instruction helper that only spills `a0..a3` into the caller stack frame and returns, with no persistent/UI/global side effect.

Reusable ROM auditors now cover central-return ABI, post-battle-return ABI, the two coupled `a1=1` callers and the safe 40-call starter block. Host contracts lock those Rev-A facts into the 26-test suite, and randomizer workflows retrigger when the ABI auditors change.

The artifact pipeline validates critical MIPS ELF sections/symbols before packaging. Native save remains free of randomizer metadata, existing inventory is never rerandomized on load, and shops/starting/key-item randomization remain OFF by default.

## Remaining 1.0 blocker

Real Rev-A gameplay/save/post-game QA remains mandatory before leaving draft: UI vs delivered item, Table-O/Table-P map transitions, battle-reward per-slot reuse, **slot-indexed `+0x02` bookkeeping where item ID differs from owned-list slot**, post-battle bookkeeping, shop consistency, `STARTING ITEMS` safe-block behavior, proof that both coupled `a1=1` unit/setup grants stay vanilla/aligned, full-inventory behavior, ON -> OFF -> ON native-save transitions, seed changes after full restart and ending/post-game reopen tests.

See `TESTING.md` and `QA-CHECKLIST.md`.
