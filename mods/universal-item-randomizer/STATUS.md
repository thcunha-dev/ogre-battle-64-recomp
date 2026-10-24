# Universal Item Randomizer 0.3.1 — engineering status

Status: **feature-complete for the currently safe acquisition model; real campaign QA pending**.

Current host verification: **30 tests** through `python3 tools/test_universal_randomizer_all.py`. Latest hardening includes map-generation invalidation for Table-O, full-generation fail-closed validation for Table-O/Table-P/reward queue, invalid-ID rejection in both grant replacements, deterministic golden seed vectors, release/pipeline/version/config contracts, 5,000 modeled ON -> OFF -> ON save sequences, **2,000 dedicated completed-game/post-ending ON -> OFF -> ON sequences**, and a **600,000-event cross-subsystem campaign stress model** (1,000 campaigns x 600 events) combining restart-required ON/OFF and seed changes, native-save round trips, Table-O/Table-P/reward lifecycles, count saturation and post-ending continuation. Shared MIPS ELF verification, Rev-A RAM table-layout contracts, class-id `0xFF` fail-closed handling, the Table-P physical-capacity fix from an unsafe assumed 64 ids to the real **16 u16 slots** at `0x801F1004..0x801F1023`, partial-roster readiness testing and an explicit policy contract for the stock-runtime QA bridge remain locked as well.

The transient `+0x02` used-count repair mirrors native `func_8016B774` semantics: roster fields are **owned-list slot references**, not item-definition IDs. Equipment uses slot `<278`, consumables use slot `<40`, and the rebuilt byte is written by owned-list slot. Partial load/map setup is fail-closed: the repair requires both character and unit rosters to be populated, clears its shadow-ready state while either side is missing, then forces a complete rebuild on the first fully ready frame. The QA manifest marks this as `use_repair=native_slot_indexed` and artifact policy rejects builds that lose the marker.

Battle-reward shadowing is documented and tested as **per-slot**, matching the persisted 20-u16 queue model. Multiple slots have been observed carrying real rewards, so a whole-queue all-zero boundary is not required. The primary slot lifecycle has static Bank-N proof: `0x801E53DC` grants the item and `0x801E53F4` clears `0x801936D8` immediately afterward.

## Traceable green QA candidate

The current QA candidate is pinned to source commit:

`bf7b34afe1315efcd7e985e484512da098948af6`

All principal automated gates for this commit completed successfully:

- Universal Randomizer Mapping run `40069669854`: full 30-test host suite PASS;
- Package Universal Randomizer run `40069669866`: `.nrm` package PASS;
- Universal Randomizer Windows Test Bundle run `40069669876`: build + QA payload + self-verification PASS (the optional hosted Windows execution job is intentionally skipped unless its external runtime condition is supplied);
- Universal Randomizer Stock Runtime QA run `40069669928`: stock QA NRM + ready-to-run official-v0.8.3 Windows bundle PASS;
- Universal Randomizer Runtime Build run `40069669840`: integrated custom runtime library, MIPS ELF and Bank-N-augmented NRM PASS.

Pinned artifacts from that same source commit:

- integrated randomizer artifact `12550304852`, workflow-archive SHA-256 `8bb97387dcee21d0a934ed38157f19757eedde532197a75e682ae307a9fa5dca`;
- self-contained QA payload `12550901315`, workflow-archive SHA-256 `c886f5b31c3dba09be1b81aa3633034f5807510c4141367f433824850c4c945c`;
- stock-runtime QA artifact `12550249882`, workflow-archive SHA-256 `fa8d7518b0443d90c606d95d17e00ec4ca68cee5a5a2b1dd916972638d7dbc69`;
- ready-to-run official-v0.8.3 Windows stock-runtime QA bundle `12550354529`, workflow-archive SHA-256 `dbe079c04c60067b575aaa9fe5b36ed5d3787199344180120d0a17438122aafe`.

Manual QA should use artifacts from this exact commit (or a newer commit whose complete gate set is green). Do not mix an older runtime/NRM with a newer checklist or manifest.

## Rev-A central-grant classification

Whole-cart Rev-A analysis accounts for **all 46 calls** to `func_ovlN_801DC740`:

- 4 Bank-N gameplay callers use source values already rewritten by the randomizer: Table-O map object A/B, Table-P ground pickup and battle reward queue;
- exactly 2 Bank-R callers pass `a1=1`, at RA `0x80215BF4` and `0x80216D98`; both also write/maintain a unit consumable-loadout reference and therefore remain **vanilla/fail-closed**;
- the remaining 40 Bank-R calls form the only `STARTING ITEMS` opt-in block, RA `0x80217070..<0x8021724C`; all pass `a1=0`, and the audited straight-line block contains no store instruction coupling a unit reference to the raw id.

The central replacement preserves the original consumable `a1` byte semantics. Equipment ignores `a1`, as in Rev-A. The only two `a1=1` callers are coupled Bank-R setup paths and are deliberately never randomized.

## Rev-A replacement ABI proof

Both `RECOMP_PATCH` replacements are intentionally declared `void`. This is proven directly against the verified Rev-A ROM (`SHA-1 d26b14bee422a09581ce438d45ba9fec9783fbb8`) rather than assumed from decompilation:

- `func_ovlN_801DC740`: the 46-caller ABI auditor follows post-return MIPS-I control flow, including branches/jumps and delay slots, and proves every caller overwrites `$v0` or reaches another call before any `$v0` read;
- `func_80172820`: whole-cart scan finds exactly **one caller**, at ROM `0x002A4ED8` / VRAM `0x802356F8`; its delay slot is `andi a1,a1,0xff`, and the first instruction after return is `addiu v0,s1,1`, so the original return value is discarded immediately;
- the central grant's full-inventory tail call is also proven harmless to omit: Rev-A calls `0x80093540`, a five-instruction helper that only spills `a0..a3` into the caller stack frame and returns, with no persistent/UI/global side effect.

Reusable ROM auditors cover central-return ABI, post-battle-return ABI, the two coupled `a1=1` callers and the safe 40-call starter block. Host contracts lock those Rev-A facts into the 30-test suite.

## Stock-runtime QA bridge

A separate **QA-only** mod variant now packages without the streamed Bank-N replacement and therefore runs on the official v0.8.3 port. It has a different mod id and cannot be mistaken for the release randomizer.

The stock-runtime workflow also assembles a ready-to-run Windows QA ZIP from the official v0.8.3 release asset. The upstream Windows archive is accepted only if its SHA-256 is exactly:

`d9c269587b2f2b224bc6203c7ac9c4f42022f6990643cd38a870cb56df243169`

CI then inserts `universal-item-randomizer-stock-qa.nrm` into `mods/`, verifies the resulting bundle contains no `.z64`, `.n64` or `.v64` game data, and uploads it as a distinct QA artifact.

This bridge can validate Table-O, Table-P, battle-reward source rewrites, post-battle adds, shops, seed behavior, native-save ON/OFF transitions, full inventory and slot-indexed `+0x02` repair **in the real port now**. It intentionally cannot validate `STARTING ITEMS`, unknown direct Bank-N grants or the final custom-runtime Bank-N replacement.

## Remaining 1.0 blocker

Real Rev-A gameplay/save/post-game QA remains mandatory before leaving draft: UI vs delivered item, Table-O/Table-P map transitions, battle-reward per-slot reuse, **slot-indexed `+0x02` bookkeeping where item ID differs from owned-list slot**, post-battle bookkeeping, shop consistency, full-inventory behavior, ON -> OFF -> ON native-save transitions, seed changes after full restart and ending/post-game reopen tests.

The dedicated post-game host model now locks the required persistence policy across 2,000 deterministic completed-game-style sequences, and the campaign stress model composes those persistence rules with acquisition/source-rewrite behavior across 600,000 additional events, but neither deliberately replaces the real ending/post-game acceptance pass on Rev-A.

After that stock-runtime pass, the integrated custom-runtime build still needs targeted QA for the Bank-N central replacement, `STARTING ITEMS` safe-block behavior and proof that both coupled `a1=1` unit/setup grants stay vanilla/aligned.

See `TESTING.md`, `QA-CHECKLIST.md` and `STOCK-RUNTIME-QA.md`.
