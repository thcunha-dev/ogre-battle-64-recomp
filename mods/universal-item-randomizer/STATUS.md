# Universal Item Randomizer 0.3.1 — engineering status

Status: **feature-complete for the currently safe acquisition model; real campaign QA pending**.

Current host verification: **21 tests** through `python3 tools/test_universal_randomizer_all.py`. Latest hardening includes map-generation invalidation for Table-O, full-generation fail-closed validation for Table-O/Table-P/reward queue, invalid-ID rejection in both grant replacements, deterministic golden seed vectors, release/pipeline/version/config contracts, 5,000 modeled ON -> OFF -> ON save sequences, shared MIPS ELF verification, Rev-A RAM table-layout contracts, class-id `0xFF` fail-closed handling and the Table-P physical-capacity fix from an unsafe assumed 64 ids to the real **16 u16 slots** at `0x801F1004..0x801F1023`.

The transient `+0x02` used-count repair now mirrors native `func_8016B774` semantics: roster fields are **owned-list slot references**, not item-definition IDs. Equipment uses slot `<278`, consumables use slot `<40`, and the rebuilt byte is written by owned-list slot. Partial load/map setup is fail-closed: the repair requires both character and unit rosters to be populated, clears its shadow-ready state while either side is missing, then forces a complete rebuild on the first fully ready frame. The QA manifest marks this as `use_repair=native_slot_indexed` and `VERIFY-QA.ps1` rejects artifacts that lose the marker.

Battle-reward shadowing is documented and tested as **per-slot**, matching the persisted 20-u16 queue model. Multiple slots have been observed carrying real rewards, so a whole-queue all-zero boundary is not required. The primary slot lifecycle has static Bank-N proof: `0x801E53DC` grants the item and `0x801E53F4` clears `0x801936D8` immediately afterward.

The artifact pipeline validates critical MIPS ELF sections/symbols before packaging. Native save remains free of randomizer metadata, existing inventory is never rerandomized on load, and shops/starting/key-item randomization remain OFF by default.

## Remaining 1.0 blocker

Real Rev-A gameplay/save/post-game QA remains mandatory before leaving draft: UI vs delivered item, Table-O/Table-P map transitions, battle-reward per-slot reuse, **slot-indexed `+0x02` bookkeeping where item ID differs from owned-list slot**, post-battle bookkeeping, shop consistency, starting/setup behavior, full-inventory behavior, ON -> OFF -> ON native-save transitions, seed changes after full restart and ending/post-game reopen tests.

See `TESTING.md` and `QA-CHECKLIST.md`.
