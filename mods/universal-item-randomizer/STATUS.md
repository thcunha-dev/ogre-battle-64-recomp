# Universal Item Randomizer 0.3.1 — engineering status

Status: **feature-complete for the currently safe acquisition model; real campaign QA pending**.

Current host verification: **18 tests** through `python3 tools/test_universal_randomizer_all.py`. Latest hardening includes map-generation invalidation for Table-O, full-generation fail-closed validation for Table-O/Table-P/reward queue, invalid-ID rejection in both grant replacements, deterministic golden seed vectors, release/pipeline/version/config contracts, 5,000 modeled ON -> OFF -> ON save sequences, and boundary models for shops, capacity and transient use counts.

The current artifact pipeline also validates critical MIPS ELF sections/symbols before packaging. Native save remains free of randomizer metadata, existing inventory is never rerandomized on load, and shops/starting/key-item randomization remain OFF by default.

## Remaining 1.0 blocker

Real Rev-A gameplay/save/post-game QA remains mandatory before leaving draft: UI vs delivered item, map transitions, battle rewards, post-battle bookkeeping, shop consistency, starting/setup behavior, ON -> OFF -> ON native-save transitions, seed changes after full restart and ending/post-game reopen tests.

See `TESTING.md` and `QA-CHECKLIST.md`.
