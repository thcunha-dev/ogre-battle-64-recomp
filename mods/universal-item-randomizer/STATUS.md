# Universal Item Randomizer 0.3.1 — engineering status

Status: **feature-complete for the currently safe acquisition model; real campaign QA pending**.

Current host verification: **23 tests** through `python3 tools/test_universal_randomizer_all.py`. Latest hardening includes map-generation invalidation for Table-O, full-generation fail-closed validation for Table-O/Table-P/reward queue, invalid-ID rejection in both grant replacements, deterministic golden seed vectors, release/pipeline/version/config contracts, 5,000 modeled ON -> OFF -> ON save sequences, shared MIPS ELF verification, Rev-A RAM table-layout contracts, class-id `0xFF` fail-closed handling and the Table-P physical-capacity fix from an unsafe assumed 64 ids to the real **16 u16 slots** at `0x801F1004..0x801F1023`.

The transient `+0x02` used-count repair mirrors native `func_8016B774` semantics: roster fields are **owned-list slot references**, not item-definition IDs. Equipment uses slot `<278`, consumables use slot `<40`, and the rebuilt byte is written by owned-list slot. Partial load/map setup is fail-closed: the repair requires both character and unit rosters to be populated, clears its shadow-ready state while either side is missing, then forces a complete rebuild on the first fully ready frame. The QA manifest marks this as `use_repair=native_slot_indexed` and `VERIFY-QA.ps1` rejects artifacts that lose the marker.

Battle-reward shadowing is documented and tested as **per-slot**, matching the persisted 20-u16 queue model. Multiple slots have been observed carrying real rewards, so a whole-queue all-zero boundary is not required. The primary slot lifecycle has static Bank-N proof: `0x801E53DC` grants the item and `0x801E53F4` clears `0x801936D8` immediately afterward.

## Rev-A replacement ABI proof

Both `RECOMP_PATCH` replacements are intentionally declared `void`. This is now proven directly against the verified Rev-A ROM (`SHA-1 d26b14bee422a09581ce438d45ba9fec9783fbb8`) rather than assumed from decompilation:

- `func_ovlN_801DC740`: whole-cart scan finds exactly **46 callers**. The ABI auditor follows post-return MIPS-I control flow, including branches/jumps and delay slots, and proves every caller overwrites `$v0` or reaches another call before any `$v0` read.
- `func_80172820`: whole-cart scan finds exactly **one caller**, at ROM `0x002A4ED8` / VRAM `0x802356F8`. Its delay slot is `andi a1,a1,0xff`, and the first instruction after return is `addiu v0,s1,1`, so the original return value is discarded immediately.

The reusable auditors are `tools/audit_randomizer_grant_abi_rom.py` and `tools/audit_randomizer_post_battle_abi_rom.py`; host contracts lock their Rev-A facts into the 23-test suite. All randomizer workflows are required by pipeline policy to retrigger when either auditor changes.

The artifact pipeline validates critical MIPS ELF sections/symbols before packaging. Native save remains free of randomizer metadata, existing inventory is never rerandomized on load, and shops/starting/key-item randomization remain OFF by default.

## Remaining 1.0 blocker

Real Rev-A gameplay/save/post-game QA remains mandatory before leaving draft: UI vs delivered item, Table-O/Table-P map transitions, battle-reward per-slot reuse, **slot-indexed `+0x02` bookkeeping where item ID differs from owned-list slot**, post-battle bookkeeping, shop consistency, starting/setup behavior, full-inventory behavior, ON -> OFF -> ON native-save transitions, seed changes after full restart and ending/post-game reopen tests.

See `TESTING.md` and `QA-CHECKLIST.md`.
