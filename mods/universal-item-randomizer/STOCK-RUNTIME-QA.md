# Universal Item Randomizer 0.3.1 — Stock Runtime QA

This is a **QA-only** build for the official Ogre Battle 64 Recomp v0.8.3 Windows/Linux/macOS runtime.

It intentionally omits the streamed Bank-N replacement for `func_ovlN_801DC740`. The official v0.8.3 runtime cannot resolve that replacement because it does not include the custom Bank-N function registry used by the final Universal Item Randomizer runtime build.

## What this QA build can validate

- deterministic seed mapping;
- Table-O map/drop source rewriting and popup/delivery consistency;
- Table-P ground pickup source rewriting;
- persisted battle-reward source rewriting;
- post-battle `func_80172820(id,count)` equipment adds;
- shop stock rewrite with `RANDOMIZE SHOPS=ON`;
- native save compatibility with the mod enabled/disabled;
- close/reopen with the same seed;
- changing seed affects future acquisitions only;
- transient `+0x02` used-count repair, including slot-indexed semantics;
- full-inventory and count-saturation behavior on covered routes.

## What this QA build intentionally does NOT validate

- Bank-R starting/setup direct grants;
- any unclassified direct Bank-N grant path;
- the final custom-runtime Bank-N replacement itself.

Those remain requirements for the integrated build before 1.0.

## Windows — ready-to-run QA bundle

The CI produces `ogre-battle-64-v0.8.3-stock-runtime-randomizer-qa-windows`, assembled from the published official v0.8.3 Windows runtime plus this QA mod already placed in `mods/`.

The official upstream Windows archive is accepted only when its SHA-256 is exactly:

`d9c269587b2f2b224bc6203c7ac9c4f42022f6990643cd38a870cb56df243169`

The QA bundle contains **no ROM/game data**. Extract it, launch the port and provide your own Ogre Battle 64 USA Rev A ROM when the port requests it on first launch. Then open MODS and enable **Universal Item Randomizer - Stock Runtime QA**.

Recommended first-run settings:

- seed `123456`;
- `RANDOMIZE SHOPS=OFF`;
- `KEY ITEMS=OFF`;
- `LOG=ON`.

Follow `STOCK-QA-CHECKLIST.md` first. It is intentionally shorter than the final integrated checklist and marks the Bank-N-only tests that must be skipped in this variant.

## Manual install on an existing official v0.8.3 runtime

1. Copy `universal-item-randomizer-stock-qa.nrm` into the `mods/` folder beside the executable.
2. Launch the port, open MODS and enable **Universal Item Randomizer - Stock Runtime QA**.
3. Use seed `123456`, `RANDOMIZE SHOPS=OFF`, `KEY ITEMS=OFF`, `LOG=ON` for the first pass.
4. Follow `STOCK-QA-CHECKLIST.md`, then use `TESTING.md` for deeper coverage.

Do not use this QA package as a release build. Its mod id is deliberately different from the final randomizer so both packages cannot be confused by the runtime config.
