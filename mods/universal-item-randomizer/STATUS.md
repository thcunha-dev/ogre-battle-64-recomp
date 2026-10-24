# Universal Item Randomizer 0.3.1 — engineering status

Status: **feature-complete for the currently safe acquisition model; real campaign QA pending**.

The current host suite contains **18 tests** and is the single source of truth via `python3 tools/test_universal_randomizer_all.py`. Heavy artifact jobs are gated by that suite. The latest hardening adds map-generation invalidation for Table-O, full-source validation for Table-O/Table-P/reward queue, invalid-ID rejection in both grant replacements, dynamic manifest suite counts, restart-required config lifecycle, a self-verifying QA payload and more selective CI rebuild triggers.

Native save remains untouched by randomizer metadata. Existing inventory is never re-randomized on load. Shops, starting items and key-item randomization remain OFF by default. Coupled unit loadout ID 28 and class-default equipment remain vanilla until they can be transformed atomically with native references.

## Remaining 1.0 blockers

Real Rev-A gameplay/save QA remains mandatory: source UI vs inventory, post-battle bookkeeping, shops, starting/setup, ON -> OFF -> ON native-save transitions, seed changes after full restart, ending/post-game close/reopen and campaign regression.

See `TESTING.md` for the detailed protocol and `QA-CHECKLIST.md` for the short execution sheet.
