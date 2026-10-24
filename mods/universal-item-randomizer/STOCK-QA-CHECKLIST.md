# Stock Runtime QA — focused gameplay checklist

Use this checklist with **Universal Item Randomizer - Stock Runtime QA** on the official Ogre Battle 64 Recomp v0.8.3 runtime. Recommended initial settings: seed `123456`, `RANDOMIZE SHOPS=OFF`, `KEY ITEMS=OFF`, `LOG=ON`.

This variant deliberately has no Bank-N central-grant replacement. Do **not** use it to judge `STARTING ITEMS` or unknown direct Bank-N grants.

## Pass A — clean boot and deterministic sources

- [ ] Start the port, load a clean/disposable Rev-A save and confirm the Stock Runtime QA mod appears in MODS.
- [ ] Enable it with seed `123456`; no crash, hang or save warning.
- [ ] Trigger a Table-O map-object reward. Record the popup name and verify the received inventory item is the same replacement.
- [ ] Trigger a Table-P ground pickup. Record popup and inventory; they must agree.
- [ ] Obtain at least two battle rewards, preferably across two battles. Message and received item must agree; repeated use of a reward slot must not churn an already mapped source.
- [ ] Repeat one known original acquisition on a fresh/disposable state with seed `123456`; replacement must be identical.

## Pass B — post-battle and +0x02 bookkeeping

- [ ] Obtain a post-battle equipment reward routed through `func_80172820(id,count)`; verify the mapped ID and quantity.
- [ ] Verify a stack at 98 plus 1 reaches 99 and never wraps.
- [ ] Verify a 99-count stack remains 99 after another covered add.
- [ ] Inspect at least one owned item where **item-definition ID is different from the owned-list slot index**. Used/owned display and equipability must remain correct.
- [ ] Open/close item/equipment screens after acquisition; no false `1/1` lockout from stale `+0x02`.

## Pass C — shops

- [ ] With `RANDOMIZE SHOPS=OFF`, enter a known shop; stock must be vanilla.
- [ ] Close/reopen with `RANDOMIZE SHOPS=ON`; stock should be deterministically mapped.
- [ ] For at least three entries, verify displayed name, detail/category, price and purchased item all refer to the same replacement.
- [ ] Same seed after a full restart gives the same stock mapping.
- [ ] Change seed after restart; already owned items remain unchanged while future shop/source acquisitions follow the new mapping.

## Pass D — native-save isolation

Use a disposable save copy.

- [ ] Mod ON → acquire randomized items → save → close the port.
- [ ] Disable/remove the QA mod → reopen → load the same save successfully.
- [ ] Save once with the mod OFF → close → reopen OFF → load successfully again.
- [ ] Re-enable the QA mod with the original seed → existing inventory IDs remain exactly as stored; only future acquisitions are mapped.
- [ ] Repeat close/reopen with the same seed and verify no inventory churn.

## Pass E — full inventory / fail-closed edges

- [ ] With a relevant owned list full, trigger a covered acquisition. No unrelated record is overwritten and no crash occurs.
- [ ] Exercise multiple map transitions and pickups; no Table-P auxiliary data corruption or strange map state.
- [ ] Exercise maps with no/invalid pickup source for the current overlay; mod must fail closed and leave gameplay vanilla.
- [ ] With `KEY ITEMS=OFF`, progression/key items remain vanilla.

## Pass F — post-game regression

- [ ] On a disposable late-game/post-game save, load with QA mod ON.
- [ ] Save, close and reopen with QA mod ON; load succeeds and inventory is stable.
- [ ] Disable/remove the QA mod; load the same native save successfully.
- [ ] Save once OFF, close/reopen OFF, and load again.

## Integrated-build-only tests — skip here

These require the final custom runtime with Bank-N function registry:

- [ ] `STARTING ITEMS=ON` Bank-R safe-block diagnostic/behavior.
- [ ] Direct Bank-N central replacement itself.
- [ ] Unknown/unclassified direct Bank-N caller fail-closed behavior under the replacement.
- [ ] Explicit proof that the two coupled `a1=1` Bank-R setup grants remain vanilla/aligned in the integrated build.

Record failures with: seed, map/battle/shop, original item if known, displayed item, received item, inventory slot/count, and whether the issue survives a close/reopen. A short video plus the port log is ideal for any mismatch.
